import numpy as np
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/health", tags=["health"])
def health(request: Request) -> dict:
    artifacts = request.app.state.artifacts
    if artifacts is None or any(name not in artifacts.objectives for name in (
        "POLAR_VOLATILES", "PLANETARY_PROCESSES", "IMPACT_HISTORY"
    )):
        raise HTTPException(status_code=503, detail="Data is still loading.")
    times = artifacts.sky["time"]
    start = np.datetime_as_string(times[0].astype("datetime64[s]"), unit="s") + "Z"
    end = np.datetime_as_string(times[-1].astype("datetime64[s]"), unit="s") + "Z"
    return {"status": "ok", "dataLoaded": True, "gridPointCount": len(artifacts.grid["ids"]),
            "maskHeightsM": sorted(artifacts.masks), "skyDataRange": {"start": start, "end": end}}
