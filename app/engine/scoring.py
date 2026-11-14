"""Pure scoring helpers shared by the preview and analysis engine."""

import numpy as np
from numpy.typing import NDArray

from app import settings


def calculate_weights(mission_type: str, power: str, communication: str,
                      objective: str, override: list[int] | None = None) -> dict:
    has_other = next((item[2] for item in settings.OBJECTIVES if item[0] == objective), None)
    if has_other is None:
        raise ValueError("Unknown mission objective.")
    if override is not None:
        if len(override) != 5 or any(type(value) is not int or not 1 <= value <= 5 for value in override):
            raise ValueError("Importance weights must be five integers from 1 to 5.")
        importance: list[int | None] = list(override)
    else:
        try:
            importance = [settings.COMMUNICATION_IMPORTANCE[communication],
                          settings.MISSION_IMPORTANCE[mission_type],
                          settings.MISSION_IMPORTANCE[mission_type],
                          settings.POWER_IMPORTANCE[power], settings.OTHER_IMPORTANCE]
        except KeyError as exc:
            raise ValueError("Unknown mission configuration value.") from exc
    if not has_other:
        importance[4] = None
    total = sum(value for value in importance if value is not None)
    weights = [round(value / total, 4) if value is not None else None for value in importance]
    return {"importance": importance, "normalizedWeights": weights, "otherIncluded": has_other}


def communication_score(visible_ratio: float, longest_blackout: int, hours: int) -> float:
    return 0.5 * visible_ratio + 0.5 * (1 - longest_blackout / hours)


def flatness_score(slope: float, cap: float) -> float:
    return 1.0 if cap == 0 else float(np.clip(1 - slope / cap, 0, 1))


def sunlight_score(visible_ratio: float, required_ratio: float, longest_darkness: int, hours: int) -> float:
    requirement = 1.0 if required_ratio == 0 else min(1.0, visible_ratio / required_ratio)
    return 0.5 * requirement + 0.5 * (1 - longest_darkness / hours)


def roughness_score(value: float, reference: NDArray, *, sorted_reference: bool = False) -> float:
    valid = np.asarray(reference) if sorted_reference else np.sort(np.asarray(reference)[np.isfinite(reference)])
    if not len(valid):
        raise ValueError("Roughness reference distribution is empty.")
    left, right = np.searchsorted(valid, value, side="left"), np.searchsorted(valid, value, side="right")
    percentile = (left + right + (right > left)) / (2 * len(valid))
    return float(1 - percentile)
