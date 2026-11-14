"""Evaluate one site using real precomputed sky and horizon data."""

from datetime import timedelta
from typing import Any

import numpy as np

from app.engine.scoring import (
    calculate_weights,
    communication_score,
    flatness_score,
    roughness_score,
    sunlight_score,
)
from app.engine.visibility import horizon_at_azimuth, longest_false_run, site_visibility
from app.schemas import AnalysisRequest
from app.settings import MARGINAL_LIMIT_RATIO, SCORE_TAGS, SUNLIGHT_BY_POWER

EXCLUSION_REASONS = {
    "SLOPE_EXCEEDED": "Slope exceeds the limit",
    "CREWED_SUNLIGHT_INTERRUPTED": "Sun visibility criterion not met for part of the stay (crewed continuous sunlight)",
    "BATTERY_ENDURANCE_EXCEEDED": "Longest continuous darkness exceeds battery endurance",
    "COMM_BLACKOUT_EXCEEDED": "Longest continuous communication blackout exceeds the allowed time",
}


def evaluate_site(request: AnalysisRequest, latitude: float, longitude: float,
                  slope: float, roughness: float, horizon: np.ndarray,
                  sky: dict[str, np.ndarray], roughness_reference: np.ndarray,
                  other_score: float | None = None) -> dict[str, Any]:
    """Evaluate the requested stay and alternatives without substituting missing data."""
    if not np.isfinite(slope) or not np.isfinite(roughness):
        raise ValueError("Terrain values are missing for this site.")
    weights = calculate_weights(request.missionType, request.powerRequirement,
                                request.communicationDependency, request.objective,
                                request.advanced.importanceWeights)
    if weights["otherIncluded"] and (other_score is None or not np.isfinite(other_score)):
        raise ValueError("The selected objective dataset is unavailable for this site.")
    advanced = request.advanced
    search = advanced.landingDateSearchRangeDays
    start_date = request.landingDate - timedelta(days=search)
    start = np.datetime64(start_date.isoformat(), "h")
    stop = np.datetime64((request.landingDate + timedelta(days=request.stayDays + search)).isoformat(), "h")
    times = np.asarray(sky["time"]).astype("datetime64[h]")
    first = int(np.searchsorted(times, start))
    last = int(np.searchsorted(times, stop))
    expected = request.stayDays * 24 + 2 * search * 24
    if last - first != expected or first >= len(times) or times[first] != start:
        raise ValueError("Sky data does not cover the full analysis window.")
    data = site_visibility(latitude, longitude, horizon, sky["r_earth"][first:last],
                           sky["r_sun"][first:last], sky["rho_earth"][first:last],
                           sky["rho_sun"][first:last], advanced.sunVisibilityCriterion,
                           advanced.earthVisibilityCriterion)
    required = (advanced.requiredSunlightRatio if advanced.requiredSunlightRatio is not None
                else SUNLIGHT_BY_POWER[request.powerRequirement]) / 100
    hours = request.stayDays * 24
    cap = advanced.slopeConstraint.maxDeg if advanced.slopeConstraint.enabled else 15
    static_roughness = roughness_score(roughness, roughness_reference, sorted_reference=True)

    def score_window(offset: int) -> dict[str, Any]:
        window = slice(offset, offset + hours)
        sun = data["sunVisible"][window]
        earth = data["earthVisible"][window]
        sunlight_ratio = float(np.mean(sun))
        earth_ratio = float(np.mean(earth))
        darkness = longest_false_run(sun)
        blackout = longest_false_run(earth)
        codes: list[str] = []
        if slope > cap:
            codes.append("SLOPE_EXCEEDED")
        if (request.missionType == "CREWED" and advanced.crewedSunlightConstraint.enabled
                and np.any(data["sunElevationDeg"][window] < horizon_at_azimuth(
                    horizon, data["sunAzimuthDeg"][window]))):
            codes.append("CREWED_SUNLIGHT_INTERRUPTED")
        uncrewed = advanced.uncrewedConstraints
        if request.missionType == "UNCREWED" and uncrewed.enabled:
            if darkness > uncrewed.batteryEnduranceHours:
                codes.append("BATTERY_ENDURANCE_EXCEEDED")
            if blackout > uncrewed.maxCommBlackoutHours:
                codes.append("COMM_BLACKOUT_EXCEEDED")
        visibility = {"sunlightRatio": sunlight_ratio, "earthVisibleRatio": earth_ratio,
                      "longestDarknessHours": darkness, "longestCommBlackoutHours": blackout}
        if codes:
            return {"passed": False, "exclusionCodes": codes, "scores": None,
                    "suitability": None, "visibility": visibility}
        scores = {"communication": communication_score(earth_ratio, blackout, hours),
                  "flatness": flatness_score(slope, cap),
                  "roughness": static_roughness,
                  "sunlight": sunlight_score(sunlight_ratio, required, darkness, hours),
                  "other": other_score if weights["otherIncluded"] else None}
        included = [(score, importance) for score, importance in zip(
            scores.values(), weights["importance"], strict=True) if importance is not None]
        total = sum(importance for _, importance in included)
        suitability = float(np.round(100 * sum(score * importance for score, importance in included) / total, 1))
        ranked = sorted(((score, -index, SCORE_TAGS[index]) for index, score in enumerate(scores.values())
                         if score is not None), reverse=True)
        marginal = advanced.slopeConstraint.enabled and slope >= MARGINAL_LIMIT_RATIO * cap
        if request.missionType == "UNCREWED" and uncrewed.enabled:
            marginal = (marginal or darkness >= MARGINAL_LIMIT_RATIO * uncrewed.batteryEnduranceHours
                        or blackout >= MARGINAL_LIMIT_RATIO * uncrewed.maxCommBlackoutHours)
        return {"passed": True, "exclusionCodes": [], "scores": scores, "suitability": suitability,
                "visibility": visibility, "status": "MARGINAL" if marginal else "FEASIBLE",
                "tags": [item[2] for item in ranked[:2]]}

    results = [score_window(day * 24) for day in range(2 * search + 1)]
    result = results[search]
    eligible = [(item["suitability"], i) for i, item in enumerate(results) if item["passed"]]
    result["bestLandingDate"] = ((start_date + timedelta(days=max(eligible, key=lambda item: item[0])[1])).isoformat()
                                 if result["passed"] and search and eligible else None)
    result["importance"] = weights["importance"]
    result["normalizedWeights"] = weights["normalizedWeights"]
    result["hourly"] = {key: value[search * 24:search * 24 + hours] for key, value in data.items()}
    return result
