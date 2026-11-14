import numpy as np

from app.engine.scoring import (
    communication_score,
    flatness_score,
    roughness_score,
    sunlight_score,
)
from app.engine.selection import select_candidates


def test_score_formulas() -> None:
    assert communication_score(0.5, 2, 10) == 0.65
    assert flatness_score(2.5, 5) == 0.5
    assert flatness_score(0, 0) == 1
    assert sunlight_score(0.5, 0.5, 2, 10) == 0.9
    assert np.isclose(roughness_score(2, np.array([1.0, 2, 3])), 1 / 3)


def test_selection_halves_separation_and_sorts() -> None:
    x = np.array([0, 10, 20, 30])
    y = np.zeros(4)
    selected, separation = select_candidates(x, y, np.array([2, 4, 3, 1]), (-100, -100, 100, 100), 3, 1)
    assert selected == [1, 2, 0]
    assert separation <= 10
