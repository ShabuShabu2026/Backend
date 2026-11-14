import os
from contextlib import contextmanager
from unittest.mock import patch
from uuid import uuid4

import numpy as np
import pytest
from psycopg import sql

from app.config import Settings
from app.database import database_connection
from app.engine.postgres_store import (
    PostgresAnalysisStore,
    decode_snapshot,
    encode_snapshot,
)
from app.schemas import AnalysisRequest


def example() -> dict:
    request = AnalysisRequest(landingDate="2027-03-05", stayDays=1, missionType="UNCREWED",
                              objective="GENERAL", powerRequirement="NORMAL", communicationDependency="NORMAL")
    site = {"siteId": "LSP-0001", "x": 0.0, "y": 0.0, "suitability": 50.0}
    refined = {"siteId": "LSP-0002", "x": 200.0, "y": 0.0, "suitability": 55.0,
               "horizon": np.arange(720, dtype=np.float32)}
    return {"request": request, "response": {"candidates": [site]}, "sites": [site],
            "byId": {site["siteId"]: site, refined["siteId"]: refined}, "nextSiteId": 3}


def test_snapshot_preserves_refined_points_and_request() -> None:
    original = example()
    restored = decode_snapshot(encode_snapshot(original), "analysis_001", "key")
    assert restored["request"] == original["request"]
    assert restored["byId"]["LSP-0001"] is restored["sites"][0]
    assert restored["refined"][(200.0, 0.0)] is restored["byId"]["LSP-0002"]
    np.testing.assert_array_equal(restored["byId"]["LSP-0002"]["horizon"], np.arange(720))
    assert restored["nextSiteId"] == 3


def test_postgres_store_survives_new_store_instance() -> None:
    if os.environ.get("RUN_DATABASE_INTEGRATION") != "1":
        pytest.skip("Set RUN_DATABASE_INTEGRATION=1 to run the PostgreSQL integration test")
    settings = Settings()
    if not settings.database_url:
        pytest.skip("No local DATABASE_URL configured")
    schema = "test_analysis_" + uuid4().hex
    with database_connection(settings) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {} ").format(sql.Identifier(schema)))
    try:
        @contextmanager
        def isolated_connection(_settings):
            with database_connection(settings) as connection:
                connection.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))
                yield connection

        with patch("app.engine.postgres_store.database_connection", isolated_connection):
            first = PostgresAnalysisStore(settings)
            first.initialize()
            stored = first.put(example()["request"], example())
            assert first.find(stored["request"]) is stored
            fresh = PostgresAnalysisStore(settings)
            loaded = fresh.get(stored["analysisId"])
            assert loaded["request"] == stored["request"]
            assert loaded["byId"]["LSP-0002"]["suitability"] == 55.0
            loaded["byId"]["LSP-0002"]["suitability"] = 42.0
            fresh.save(loaded)
            assert PostgresAnalysisStore(settings).get(stored["analysisId"])["byId"]["LSP-0002"]["suitability"] == 42.0
            changed = PostgresAnalysisStore(settings)
            changed.dataset_version = "different"
            with pytest.raises(ValueError, match="different data"):
                changed.get(stored["analysisId"])
    finally:
        with database_connection(settings) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
