"""Analysis routes and explicit readiness failures."""

import math
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query

from app.schemas import AnalysisRequest

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("", status_code=201)
def create_analysis(body: AnalysisRequest) -> dict:
    search = timedelta(days=body.advanced.landingDateSearchRangeDays)
    try:
        start = body.landingDate - search
        end = body.landingDate + timedelta(days=body.stayDays) + search
    except OverflowError as exc:
        raise HTTPException(status_code=400, detail={"code": "DATE_OUT_OF_RANGE", "message": "Date range is outside available sky data."}) from exc
    if start < date(2027, 1, 1) or end > date(2027, 12, 31):
        raise HTTPException(status_code=400, detail={"code": "DATE_OUT_OF_RANGE", "message": "Date range is outside available sky data."})
    raise HTTPException(status_code=503, detail="Analysis artifacts are not available.")


def _validate_bbox(bbox: str) -> None:
    try:
        values = [float(part) for part in bbox.split(",")]
        if (len(values) != 4 or not all(math.isfinite(v) for v in values)
                or values[0] >= values[2] or values[1] >= values[3]):
            raise ValueError
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid bounding box.") from exc


@router.get("/{analysis_id}/recommendations")
def recommendations(analysis_id: str, bbox: str, limit: int = Query(default=10, ge=1, le=50)) -> dict:
    _validate_bbox(bbox)
    raise HTTPException(status_code=404, detail="Analysis not found.")


@router.get("/{analysis_id}/grid")
def grid(analysis_id: str, bbox: str) -> dict:
    _validate_bbox(bbox)
    raise HTTPException(status_code=404, detail="Analysis not found.")


@router.get("/{analysis_id}/sites/{site_id}")
def site(analysis_id: str, site_id: str) -> dict:
    raise HTTPException(status_code=404, detail="Analysis not found.")


@router.get("/{analysis_id}/sites/{site_id}/visibility")
def visibility(analysis_id: str, site_id: str, landingDate: date | None = None) -> dict:
    raise HTTPException(status_code=404, detail="Analysis not found.")


@router.get("/{analysis_id}/sites/{site_id}/terrain")
def terrain(analysis_id: str, site_id: str, radiusM: int = Query(default=2000, ge=1, le=5000)) -> dict:
    raise HTTPException(status_code=404, detail="Analysis not found.")
