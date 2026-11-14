"""Greedy spatial selection with separation fallback."""

import math

import numpy as np
from numpy.typing import NDArray

from app.settings import SEPARATION_COEFFICIENT


def select_candidates(x: NDArray, y: NDArray, scores: NDArray, bbox: tuple[float, float, float, float],
                      limit: int, spacing_m: float) -> tuple[list[int], float]:
    xmin, ymin, xmax, ymax = bbox
    if not (xmin < xmax and ymin < ymax and limit > 0 and spacing_m > 0):
        raise ValueError("Invalid selection bounds or limit.")
    indices = np.flatnonzero(np.isfinite(scores) & (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax))
    ordered = sorted(indices.tolist(), key=lambda i: (-scores[i], i))
    separation = SEPARATION_COEFFICIENT * math.sqrt((xmax - xmin) * (ymax - ymin) / limit)
    while True:
        chosen: list[int] = []
        for i in ordered:
            if all(math.hypot(float(x[i] - x[j]), float(y[i] - y[j])) >= separation for j in chosen):
                chosen.append(i)
                if len(chosen) == limit:
                    break
        if len(chosen) >= limit or separation < spacing_m:
            return chosen, separation
        separation /= 2
