from fastapi import APIRouter

from app import settings

router = APIRouter(tags=["config"])


@router.get("/config")
def config() -> dict:
    return {
        "defaults": {"landingDate": "2027-03-05", "stayDays": 6, "missionType": "CREWED",
                     "objective": "GENERAL", "powerRequirement": "NORMAL",
                     "communicationDependency": "NORMAL", "slopeMaxDeg": 5,
                     "requiredSunlightRatio": 50, "sunVisibilityCriterion": "HALF_DISK",
                     "earthVisibilityCriterion": "CENTER_DELTA", "heightM": 1,
                     "landingDateSearchRangeDays": 7},
        "objectives": [{"id": i, "label": label, "hasOtherScore": flag}
                       for i, label, flag in settings.OBJECTIVES],
        "requiredSunlightByPower": settings.SUNLIGHT_BY_POWER,
        "earthVisibilityMargin": {"degrees": settings.EARTH_DELTA_DEG, "provisional": True},
        "importancePresets": {
            "communicationDependency": settings.COMMUNICATION_IMPORTANCE,
            "missionType": {k: {"flatness": v, "roughness": v}
                            for k, v in settings.MISSION_IMPORTANCE.items()},
            "powerRequirement": settings.POWER_IMPORTANCE, "other": settings.OTHER_IMPORTANCE,
        },
        "limits": {"dateMin": "2026-01-01", "dateMax": "2028-12-31", "stayDaysMin": 1,
                   "slopeMaxDegRange": [0, 15], "importanceRange": [1, 5],
                   "landingDateSearchRangeDaysRange": [0, 30], "heightsM": settings.HEIGHTS_M},
    }
