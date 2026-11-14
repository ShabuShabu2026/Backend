"""Disk visibility and uninterrupted interval helpers."""

import numpy as np
from numpy.typing import NDArray


def sun_disk_fraction(x: NDArray) -> NDArray:
    x = np.clip(np.asarray(x, dtype=float), -1, 1)
    return 1 - (np.arccos(x) - x * np.sqrt(np.maximum(0, 1 - x * x))) / np.pi


def longest_false_run(values: NDArray) -> int:
    longest = current = 0
    for value in np.asarray(values, dtype=bool):
        current = 0 if value else current + 1
        longest = max(longest, current)
    return longest
