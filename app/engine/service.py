"""Build and store analyses from validated offline artifacts."""

import time
from datetime import timedelta
from typing import Any

import numpy as np

from app.engine.analysis import EXCLUSION_REASONS
from app.engine.artifacts import Artifacts
from app.engine.batch import visibility_windows
from app.engine.scoring import calculate_weights
from app.engine.selection import select_candidates
from app.schemas import AnalysisRequest
from app.settings import (
    GRID_SPACING_M,
    MARGINAL_LIMIT_RATIO,
    SCORE_TAGS,
    SUNLIGHT_BY_POWER,
)


def candidate(site: dict[str, Any], rank: int) -> dict[str, Any]:
    return {"rank": rank, "siteId": site["siteId"], "lat": site["lat"], "lon": site["lon"],
            "x": site["x"], "y": site["y"], "suitability": site["suitability"],
            "passed": True, "exclusionReasons": [], "status": site["status"],
            "tags": site["tags"], "bestLandingDate": site["bestLandingDate"]}


def recommendations(sites: list[dict[str, Any]], bbox: tuple[float, float, float, float],
                    limit: int, spacing: float) -> tuple[list[dict], float]:
    x = np.asarray([s["x"] for s in sites], dtype=float)
    y = np.asarray([s["y"] for s in sites], dtype=float)
    scores = np.asarray([s["suitability"] if s["passed"] else np.nan for s in sites], dtype=float)
    indexes, separation = select_candidates(x, y, scores, bbox, limit, spacing)
    return [candidate(sites[index], rank) for rank, index in enumerate(indexes, 1)], separation


def build_analysis(request: AnalysisRequest, artifacts: Artifacts) -> dict[str, Any]:
    start = time.perf_counter()
    grid = artifacts.grid
    weight_info = calculate_weights(request.missionType, request.powerRequirement,
                                    request.communicationDependency, request.objective,
                                    request.advanced.importanceWeights)
    other = artifacts.objectives.get(request.objective)
    if weight_info["otherIncluded"] and other is None:
        raise ValueError(f"The selected objective dataset is unavailable: {request.objective}.")
    if other is not None and (not np.all(np.isfinite(other)) or np.any((other < 0) | (other > 1))):
        raise ValueError("The selected objective artifact contains invalid scores.")
    slope = np.asarray(grid["slope"], dtype=float)
    roughness = np.asarray(grid["roughness"], dtype=float)
    if not np.all(np.isfinite(slope)) or not np.all(np.isfinite(roughness)):
        raise ValueError("The grid contains missing terrain values.")
    advanced = request.advanced
    search = advanced.landingDateSearchRangeDays
    start_date = request.landingDate - timedelta(days=search)
    first_hour = np.datetime64(start_date.isoformat(), "h")
    first = int(np.searchsorted(artifacts.sky["time"], first_hour))
    hours = request.stayDays * 24
    span = hours + 2 * search * 24
    last = first + span
    if first >= len(artifacts.sky["time"]) or artifacts.sky["time"][first] != first_hour or last > len(artifacts.sky["time"]):
        raise ValueError("Sky data does not cover the full analysis window.")
    sun_mode = {"PARTIAL": 0, "HALF_DISK": 1, "FULL": 2}[advanced.sunVisibilityCriterion]
    earth_mode = {"UPPER_EDGE": 0, "CENTER_DELTA": 1, "FULL": 2}[advanced.earthVisibilityCriterion]
    metrics, invalid = visibility_windows(
        grid["lat"], grid["lon"], artifacts.masks[advanced.heightM],
        artifacts.sky["r_earth"][first:last], artifacts.sky["r_sun"][first:last],
        artifacts.sky["rho_earth"][first:last], artifacts.sky["rho_sun"][first:last],
        hours, search, sun_mode, earth_mode,
    )
    if np.any(invalid):
        raise ValueError("Sky or horizon data is missing for one or more grid points.")
    sunlight, earth_ratio, darkness, blackout, violations = (metrics[:, :, i] for i in range(5))
    cap = advanced.slopeConstraint.maxDeg if advanced.slopeConstraint.enabled else 15
    slope_bad = np.broadcast_to((slope > cap)[:, None], sunlight.shape)
    crewed_bad = ((violations > 0) if request.missionType == "CREWED" and advanced.crewedSunlightConstraint.enabled
                  else np.zeros_like(sunlight, dtype=bool))
    uncrewed = advanced.uncrewedConstraints
    if request.missionType == "UNCREWED" and uncrewed.enabled:
        dark_bad = darkness > uncrewed.batteryEnduranceHours
        comm_bad = blackout > uncrewed.maxCommBlackoutHours
    else:
        dark_bad = np.zeros_like(sunlight, dtype=bool)
        comm_bad = np.zeros_like(sunlight, dtype=bool)
    passed = ~(slope_bad | crewed_bad | dark_bad | comm_bad)
    comm_score = 0.5 * earth_ratio + 0.5 * (1 - blackout / hours)
    flat_score = np.ones(len(slope)) if cap == 0 else np.clip(1 - slope / cap, 0, 1)
    reference = artifacts.roughness_reference
    left = np.searchsorted(reference, roughness, side="left")
    right = np.searchsorted(reference, roughness, side="right")
    rough_score = 1 - (left + right + (right > left)) / (2 * len(reference))
    required = (advanced.requiredSunlightRatio if advanced.requiredSunlightRatio is not None
                else SUNLIGHT_BY_POWER[request.powerRequirement]) / 100
    sunlight_term = np.ones_like(sunlight) if required == 0 else np.minimum(1, sunlight / required)
    sun_score = 0.5 * sunlight_term + 0.5 * (1 - darkness / hours)
    importance = weight_info["importance"]
    total_weight = sum(item for item in importance if item is not None)
    suitability = (importance[0] * comm_score + importance[1] * flat_score[:, None]
                   + importance[2] * rough_score[:, None] + importance[3] * sun_score)
    if importance[4] is not None:
        suitability += importance[4] * np.asarray(other)[:, None]
    suitability = np.round(100 * suitability / total_weight, 1)
    best_day = np.argmax(np.where(passed, suitability, -np.inf), axis=1)
    any_passed = np.any(passed, axis=1)
    sites: list[dict[str, Any]] = []
    for index, identifier in enumerate(grid["ids"]):
        other_score = None if other is None else float(other[index])
        current_passed = bool(passed[index, search])
        flags = (slope_bad[index, search], crewed_bad[index, search], dark_bad[index, search], comm_bad[index, search])
        codes = [code for code, flagged in zip(EXCLUSION_REASONS, flags, strict=True) if flagged]
        visibility = {"sunlightRatio": float(sunlight[index, search]), "earthVisibleRatio": float(earth_ratio[index, search]),
                      "longestDarknessHours": int(darkness[index, search]), "longestCommBlackoutHours": int(blackout[index, search])}
        scores = {"communication": float(comm_score[index, search]), "flatness": float(flat_score[index]),
                  "roughness": float(rough_score[index]), "sunlight": float(sun_score[index, search]),
                  "other": other_score if weight_info["otherIncluded"] else None}
        evaluated = {"passed": current_passed, "exclusionCodes": codes,
                     "scores": scores if current_passed else None,
                     "suitability": float(suitability[index, search]) if current_passed else None,
                     "visibility": visibility, "importance": importance,
                     "normalizedWeights": weight_info["normalizedWeights"],
                     "bestLandingDate": (start_date + timedelta(days=int(best_day[index]))).isoformat()
                     if search and any_passed[index] else None}
        if current_passed:
            ranked = sorted(((value, -i, SCORE_TAGS[i]) for i, value in enumerate(scores.values())
                             if value is not None), reverse=True)
            marginal = advanced.slopeConstraint.enabled and slope[index] >= MARGINAL_LIMIT_RATIO * cap
            if request.missionType == "UNCREWED" and uncrewed.enabled:
                marginal = (marginal or darkness[index, search] >= MARGINAL_LIMIT_RATIO * uncrewed.batteryEnduranceHours
                            or blackout[index, search] >= MARGINAL_LIMIT_RATIO * uncrewed.maxCommBlackoutHours)
            evaluated["status"] = "MARGINAL" if marginal else "FEASIBLE"
            evaluated["tags"] = [entry[2] for entry in ranked[:2]]
        evaluated.update({"siteId": str(identifier), "lat": float(grid["lat"][index]),
                          "lon": float(grid["lon"][index]), "x": float(grid["x"][index]),
                          "y": float(grid["y"][index]), "slopeDeg": float(grid["slope"][index]),
                          "roughnessM": float(grid["roughness"][index]), "index": index})
        sites.append(evaluated)
    x, y = np.asarray(grid["x"]), np.asarray(grid["y"])
    bbox = (float(x.min()), float(y.min()), float(x.max()), float(y.max()))
    selected, separation = recommendations(sites, bbox, request.limit, GRID_SPACING_M)
    code_counts = {code: sum(code in site["exclusionCodes"] for site in sites) for code in EXCLUSION_REASONS}
    passed_count = sum(site["passed"] for site in sites)
    warnings: list[str] = []
    if request.advanced.slopeConstraint.enabled and request.advanced.slopeConstraint.maxDeg > 5:
        warnings.append("Slope limit relaxed above 5 degrees.")
    if not request.advanced.slopeConstraint.enabled:
        warnings.append("Slope constraint is off; analysis is capped at 15 degrees.")
    if request.missionType == "CREWED" and not request.advanced.crewedSunlightConstraint.enabled:
        warnings.append("Crewed continuous sunlight constraint is off.")
    if request.advanced.earthVisibilityCriterion == "CENTER_DELTA":
        warnings.append("Earth visibility margin is provisional and has not been validated as a 95% uncertainty bound.")
    public = {"appliedImportance": weight_info["importance"], "normalizedWeights": weight_info["normalizedWeights"],
              "otherIncluded": weight_info["otherIncluded"], "warnings": warnings,
              "counts": {"total": len(sites), "passed": passed_count, "excluded": len(sites) - passed_count,
                         "excludedByCode": code_counts},
              "bbox": dict(zip(("xmin", "ymin", "xmax", "ymax"), bbox, strict=True)),
              "crs": str(grid["crs"].item()), "gridSpacingM": GRID_SPACING_M, "separationM": separation,
              "candidates": selected,
              "sites": {"ids": [s["siteId"] for s in sites], "lat": [s["lat"] for s in sites],
                        "lon": [s["lon"] for s in sites], "suitability": [s["suitability"] for s in sites],
                        "passed": [s["passed"] for s in sites],
                        "exclusionCodes": [s["exclusionCodes"] for s in sites]},
              "exclusionCodeLegend": EXCLUSION_REASONS}
    return {"response": public, "sites": sites, "byId": {s["siteId"]: s for s in sites},
            "request": request, "elapsedSeconds": time.perf_counter() - start}
