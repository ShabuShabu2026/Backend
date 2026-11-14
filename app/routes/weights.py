from typing import Literal

from fastapi import APIRouter, HTTPException

from app.engine.scoring import calculate_weights

router = APIRouter(tags=["weights"])


@router.get("/weights")
def weights(missionType: Literal["CREWED", "UNCREWED"],
            powerRequirement: Literal["LOW", "NORMAL", "HIGH"],
            communicationDependency: Literal["INDEPENDENT", "NORMAL", "CRITICAL"],
            objective: str, importanceWeights: str | None = None) -> dict:
    try:
        values = None if importanceWeights is None else [int(x) for x in importanceWeights.split(",")]
        return calculate_weights(missionType, powerRequirement, communicationDependency, objective, values)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
