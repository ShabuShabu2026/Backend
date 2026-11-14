from datetime import date

from app.engine.store import AnalysisStore
from app.schemas import AnalysisRequest


def make_request(day: int) -> AnalysisRequest:
    return AnalysisRequest(landingDate=date(2027, 3, day), stayDays=1, missionType="CREWED",
                           objective="GENERAL", powerRequirement="NORMAL", communicationDependency="NORMAL")


def test_lru_cache_and_identical_requests() -> None:
    store = AnalysisStore(capacity=2)
    first = store.put(make_request(5), {})
    assert store.put(make_request(5), {}) is first
    second = store.put(make_request(6), {})
    assert store.get(first["analysisId"]) is first
    store.put(make_request(7), {})
    assert store.get(second["analysisId"]) is None
    assert store.find(make_request(5)) is first
