"""Analysis routes and explicit readiness failures."""

import math
from datetime import date, timedelta

import numpy as np
import rasterio
from fastapi import APIRouter, HTTPException, Query, Request
from pyproj import CRS
from pyproj.exceptions import ProjError
from rasterio.windows import Window

from app.engine.analysis import EXCLUSION_REASONS, evaluate_site
from app.engine.refined import refined_sites
from app.engine.service import build_analysis
from app.engine.service import recommendations as select_recommendations
from app.schemas import AnalysisRequest
from app.settings import GRID_SPACING_M, REFINED_MIN_SPACING_M, REFINED_TARGET_POINTS

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("", status_code=201)
def create_analysis(body: AnalysisRequest, request: Request) -> dict:
    search = timedelta(days=body.advanced.landingDateSearchRangeDays)
    try:
        start = body.landingDate - search
        end = body.landingDate + timedelta(days=body.stayDays) + search
    except OverflowError as exc:
        raise HTTPException(status_code=400, detail={"code": "DATE_OUT_OF_RANGE", "message": "Date range is outside available sky data."}) from exc
    if start < date(2026, 1, 1) or end > date(2029, 1, 1):
        raise HTTPException(status_code=400, detail={"code": "DATE_OUT_OF_RANGE", "message": "Date range is outside available sky data."})
    artifacts = request.app.state.artifacts
    if artifacts is None:
        raise HTTPException(status_code=503, detail="Analysis artifacts are not available.")
    times = artifacts.sky["time"]
    if np.datetime64(start.isoformat(), "h") < times[0] or np.datetime64(end.isoformat(), "h") > times[-1] + np.timedelta64(1, "h"):
        raise HTTPException(status_code=400, detail={"code": "DATE_OUT_OF_RANGE", "message": "Date range is outside available sky data."})
    store = request.app.state.store
    existing = store.find(body)
    if existing is not None:
        return {"analysisId": existing["analysisId"], **existing["response"]}
    try:
        result = build_analysis(body, artifacts)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    result = store.put(body, result)
    return {"analysisId": result["analysisId"], **result["response"]}


def _validate_bbox(bbox: str) -> tuple[float, float, float, float]:
    try:
        values = [float(part) for part in bbox.split(",")]
        if (len(values) != 4 or not all(math.isfinite(v) for v in values)
                or values[0] >= values[2] or values[1] >= values[3]
                or not math.isfinite((values[2] - values[0]) * (values[3] - values[1]))):
            raise ValueError
        return tuple(values)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid bounding box.") from exc


@router.get("/{analysisId}/recommendations")
def recommendations(analysisId: str, bbox: str, request: Request,
                    limit: int = Query(default=20, ge=1, le=50)) -> dict:
    bounds = _validate_bbox(bbox)
    result = _get_analysis(request, analysisId)
    spacing = _spacing(bounds)
    if spacing < GRID_SPACING_M:
        points = _refined(request, result, bounds, spacing)
        used_spacing = spacing
    else:
        points = result["sites"]
        used_spacing = GRID_SPACING_M
    sites, separation = select_recommendations(points, bounds, limit, used_spacing)
    return {"bbox": _bbox_dict(bounds), "crs": result["response"]["crs"], "limit": limit,
            "returnedCount": len(sites), "gridSpacingM": used_spacing,
            "separationM": separation, "recommendations": sites}


@router.get("/{analysisId}/grid")
def grid(analysisId: str, bbox: str, request: Request) -> dict:
    bounds = _validate_bbox(bbox)
    result = _get_analysis(request, analysisId)
    spacing = _spacing(bounds)
    if spacing < GRID_SPACING_M:
        sites = _refined(request, result, bounds, spacing)
        used_spacing = spacing
    else:
        stride = max(1, round(spacing / GRID_SPACING_M))
        sites = [s for s in result["sites"] if bounds[0] <= s["x"] <= bounds[2] and bounds[1] <= s["y"] <= bounds[3]
                 and round(s["x"] / GRID_SPACING_M) % stride == 0 and round(s["y"] / GRID_SPACING_M) % stride == 0]
        used_spacing = stride * GRID_SPACING_M
    return {"bbox": _bbox_dict(bounds), "crs": result["response"]["crs"], "gridSpacingM": used_spacing,
            "sites": {"ids": [s["siteId"] for s in sites], "x": [s["x"] for s in sites],
                      "y": [s["y"] for s in sites], "suitability": [s["suitability"] for s in sites],
                      "passed": [s["passed"] for s in sites], "exclusionCodes": [s["exclusionCodes"] for s in sites]}}


@router.get("/{analysisId}/sites/{siteId}")
def site(analysisId: str, siteId: str, request: Request) -> dict:
    value = _get_site(_get_analysis(request, analysisId), siteId)
    return {"siteId": value["siteId"], "lat": value["lat"], "lon": value["lon"],
            "suitability": value["suitability"], "passed": value["passed"],
            "exclusionReasons": [EXCLUSION_REASONS[c] for c in value["exclusionCodes"]],
            "scores": value["scores"], "importance": value["importance"],
            "normalizedWeights": value["normalizedWeights"],
            "terrain": {"slopeDeg": value["slopeDeg"], "roughnessM": value["roughnessM"]},
            "visibility": value["visibility"], "bestLandingDate": value["bestLandingDate"]}


@router.get("/{analysisId}/sites/{siteId}/visibility")
def visibility(analysisId: str, siteId: str, request: Request, landingDate: date | None = None) -> dict:
    """Return hourly directions in degrees and terrain-occluded visibility for a site."""
    result = _get_analysis(request, analysisId)
    value = _get_site(result, siteId)
    original = result["request"]
    landing = landingDate or original.landingDate
    if abs((landing - original.landingDate).days) > original.advanced.landingDateSearchRangeDays:
        raise HTTPException(status_code=400, detail="Landing date is outside the analysis search range.")
    advanced = original.advanced.model_copy(update={"landingDateSearchRangeDays": 0})
    current = original.model_copy(update={"landingDate": landing, "advanced": advanced})
    artifacts = request.app.state.artifacts
    other = artifacts.objectives.get(current.objective)
    try:
        mask = value.get("horizon")
        score = value.get("objectiveScore")
        if mask is None:
            mask = artifacts.masks[current.advanced.heightM][value["index"]]
            score = None if other is None else float(other[value["index"]])
        computed = evaluate_site(current, value["lat"], value["lon"], value["slopeDeg"], value["roughnessM"],
                                 mask, artifacts.sky, artifacts.roughness_reference, score)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    hourly = []
    start = np.datetime64(landing.isoformat(), "h")
    for index in range(current.stayDays * 24):
        entry = {key: (bool(values[index]) if key in ("sunVisible", "earthVisible") else float(values[index]))
                 for key, values in computed["hourly"].items()}
        entry["time"] = np.datetime_as_string(start + np.timedelta64(index, "h"), unit="s") + "Z"
        entry.update({"timestamp": entry["time"], "sun_azimuth": entry["sunAzimuthDeg"],
                      "sun_elevation": entry["sunElevationDeg"], "earth_azimuth": entry["earthAzimuthDeg"],
                      "earth_elevation": entry["earthElevationDeg"], "sun_visible": entry["sunVisible"],
                      "earth_visible": entry["earthVisible"]})
        hourly.append(entry)
    return {"landingDate": landing.isoformat(), "stayDays": current.stayDays, "stepHours": 1,
            "site_id": siteId, "direction_convention": {"unit": "degrees", "azimuth": "clockwise from true north",
                                                          "elevation": "degrees above local horizontal"},
            "visibility": computed["visibility"], "passed": computed["passed"], "hourly": hourly}


@router.get("/{analysisId}/sites/{siteId}/terrain")
def terrain(analysisId: str, siteId: str, request: Request,
            radiusM: int = Query(default=2000, ge=1, le=5000)) -> dict:
    """Return DEM heights in meters; null marks a missing elevation sample."""
    analysis = _get_analysis(request, analysisId)
    value = _get_site(analysis, siteId)
    path = request.app.state.settings.raster_paths["dem"]
    try:
        with rasterio.open(path) as raster:
            transform = raster.transform
            if raster.crs is None:
                raise ValueError("DEM coordinate system is unavailable.")
            dem_crs = CRS.from_wkt(raster.crs.to_wkt())
            crs_wkt = raster.crs.to_wkt()
            if transform.b != 0 or transform.d != 0 or transform.a <= 0 or transform.e != -transform.a:
                raise ValueError("DEM must have square north-up pixels.")
            size = transform.a
            col0 = max(0, math.ceil((value["x"] - radiusM - transform.c) / size - 0.5))
            col1 = min(raster.width - 1, math.floor((value["x"] + radiusM - transform.c) / size - 0.5))
            row0 = max(0, math.ceil((transform.f - value["y"] - radiusM) / size - 0.5))
            row1 = min(raster.height - 1, math.floor((transform.f - value["y"] + radiusM) / size - 0.5))
            if col0 > col1 or row0 > row1:
                raise ValueError("The requested terrain window is outside the DEM.")
            values = raster.read(1, window=Window(col0, row0, col1 - col0 + 1, row1 - row0 + 1), masked=True)
            values = values.astype(float).filled(np.nan)
            heights = [[float(v) if np.isfinite(v) else None for v in row] for row in values]
            origin_x, origin_y = raster.xy(row0, col0)
            sphere = dem_crs.ellipsoid
            is_lunar_sphere = (math.isclose(sphere.semi_major_metre, 1_737_400, abs_tol=0.001, rel_tol=0)
                               and math.isclose(sphere.semi_minor_metre, 1_737_400, abs_tol=0.001, rel_tol=0))
    except (OSError, ValueError, ProjError, rasterio.errors.RasterioError) as exc:
        raise HTTPException(status_code=503, detail="DEM terrain is unavailable.") from exc
    return {"centerLat": value["lat"], "centerLon": value["lon"], "gridSpacingM": size,
            "crs": analysis["response"]["crs"], "origin": {"x": origin_x, "y": origin_y},
            "elevationsM": heights,
            "site_id": siteId, "latitude": value["lat"], "longitude": value["lon"],
            "heights": heights, "resolution_m": size,
            "coordinate_system": {"crs_wkt": crs_wkt, "origin": {"x": origin_x, "y": origin_y},
                                  "origin_reference": "center of upper-left pixel",
                                  "column_step": {"x": size, "y": 0},
                                  "row_step": {"x": 0, "y": -size},
                                  "site_position": {"x": value["x"], "y": value["y"]},
                                  "unit": "m"},
            "elevation_reference": ({"type": "reference_sphere", "radius_m": 1_737_400,
                                     "unit": "m", "description": "Height relative to lunar reference sphere",
                                     "provenance": "Assumed for the supplied NASA LOLA DEM; vertical datum is not encoded in the raster CRS"}
                                    if is_lunar_sphere else None)}


def _get_analysis(request: Request, analysis_id: str) -> dict:
    try:
        result = request.app.state.store.get(analysis_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "ANALYSIS_VERSION_CHANGED",
                            "message": "This analysis uses different data or calculation settings. Run a new analysis."}) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return result


def _get_site(analysis: dict, site_id: str) -> dict:
    site = analysis["byId"].get(site_id)
    if site is None:
        raise HTTPException(status_code=404, detail={"code": "SITE_NOT_FOUND", "message": "Site not found."})
    return site


def _bbox_dict(bounds: tuple[float, float, float, float]) -> dict:
    return dict(zip(("xmin", "ymin", "xmax", "ymax"), bounds, strict=True))


def _spacing(bounds: tuple[float, float, float, float]) -> float:
    return max(REFINED_MIN_SPACING_M,
               math.sqrt((bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) / REFINED_TARGET_POINTS))


def _refined(request: Request, analysis: dict, bounds: tuple[float, float, float, float], spacing: float) -> list[dict]:
    try:
        with request.app.state.store.lock:
            previous_count = len(analysis.get("byId", {}))
            result = refined_sites(analysis, bounds, spacing, request.app.state.artifacts, request.app.state.settings)
            if len(analysis.get("byId", {})) != previous_count:
                request.app.state.store.save(analysis)
            return result
    except (OSError, ValueError, KeyError, ProjError) as exc:
        raise HTTPException(status_code=503, detail="Refined-grid data is unavailable.") from exc
