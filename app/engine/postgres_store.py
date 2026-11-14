"""Durable analysis snapshots with a bounded in-process read cache."""

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import psycopg

from app.config import Settings
from app.database import database_connection
from app.engine.store import AnalysisStore
from app.schemas import AnalysisRequest
from app.settings import EARTH_DELTA_DEG

SNAPSHOT_ALGORITHM_VERSION = "1"
ARTIFACT_FILES = ("grid.npz", "horizon_manifest.json", "horizon_1m.npy", "horizon_5m.npy",
                  "horizon_10m.npy", "sky_table.npz", "roughness_reference.npy", "reference.json",
                  "objective_polar_volatiles.npy", "objective_planetary_processes.npy",
                  "objective_impact_history.npy")
DATA_FILES = ("dem/LDEM_80S_80MPP_ADJ.TIF", "terrain/LDSM_80S_80MPP_ADJ.TIF",
              "terrain/LDRM_80S_50MPP_ADJ_ROUGH_100M.TIF",
              *(f"psr/LPSR_80S_20MPP_ADJ.{suffix}" for suffix in ("SHP", "SHX", "DBF", "PRJ")),
              *(f"geology/Unified_Geologic_Map_of_the_Moon_GIS/Lunar_GIS/Shapefiles/GeoUnits.{suffix}"
                for suffix in ("shp", "shx", "dbf", "prj", "cpg")),
              "craters/goransalamuniccar_mooncraters.zip")


def _json_default(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Unsupported snapshot value: {type(value).__name__}")


def encode_snapshot(result: dict[str, Any]) -> bytes:
    sites = result["sites"]
    base_ids = {site["siteId"] for site in sites}
    refined = [site for site in result.get("byId", {}).values() if site["siteId"] not in base_ids]
    snapshot = {"version": 1, "datasetVersion": result.get("_datasetVersion"),
                "request": result["request"].model_dump(mode="json"),
                "response": result["response"], "sites": sites, "refined": refined,
                "nextSiteId": result.get("nextSiteId", len(sites) + 1),
                "elapsedSeconds": result.get("elapsedSeconds", 0)}
    raw = json.dumps(snapshot, default=_json_default, separators=(",", ":"), allow_nan=False).encode()
    return gzip.compress(raw, compresslevel=1)


def decode_snapshot(payload: bytes, analysis_id: str, key: str) -> dict[str, Any]:
    snapshot = json.loads(gzip.decompress(payload))
    if snapshot.get("version") != 1:
        raise ValueError("Unsupported analysis snapshot version.")
    sites = snapshot["sites"]
    by_id = {site["siteId"]: site for site in sites}
    refined = {}
    for site in snapshot["refined"]:
        site["horizon"] = np.asarray(site["horizon"], dtype=np.float32)
        by_id[site["siteId"]] = site
        refined[(round(site["x"], 7), round(site["y"], 7))] = site
    return {"analysisId": analysis_id, "_requestKey": key, "_datasetVersion": snapshot.get("datasetVersion"),
            "request": AnalysisRequest.model_validate(snapshot["request"]),
            "response": snapshot["response"], "sites": sites, "byId": by_id,
            "refined": refined, "nextSiteId": snapshot["nextSiteId"],
            "elapsedSeconds": snapshot["elapsedSeconds"]}


class PostgresAnalysisStore(AnalysisStore):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.dataset_version = "unversioned"

    def configure_artifacts(self) -> None:
        digest = hashlib.sha256(f"{SNAPSHOT_ALGORITHM_VERSION}:{EARTH_DELTA_DEG}".encode())
        root = Path(__file__).resolve().parent.parent
        files = [("artifact/" + name, self.settings.artifacts_dir / name) for name in ARTIFACT_FILES]
        files.extend(("data/" + name, self.settings.data_dir / name) for name in DATA_FILES)
        files.extend(("code/" + path.relative_to(root).as_posix(), path) for path in sorted(root.rglob("*.py")))
        for name, path in files:
            digest.update(name.encode())
            if not path.is_file():
                digest.update(b"missing")
                continue
            with path.open("rb") as source:
                digest.update(hashlib.file_digest(source, "sha256").digest())
        self.dataset_version = digest.hexdigest()

    def request_key(self, request: AnalysisRequest) -> str:
        base = super().request_key(request)
        return hashlib.sha256(f"{self.dataset_version}:{base}".encode()).hexdigest()

    def initialize(self) -> None:
        with database_connection(self.settings) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS landing_analyses (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                request_key TEXT NOT NULL UNIQUE,
                snapshot BYTEA NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")

    def _remember(self, result: dict[str, Any]) -> dict[str, Any]:
        analysis_id = result["analysisId"]
        self._items[analysis_id] = result
        self._items.move_to_end(analysis_id)
        self._keys[result["_requestKey"]] = analysis_id
        if len(self._items) > self.capacity:
            _, oldest = self._items.popitem(last=False)
            self._keys.pop(oldest["_requestKey"], None)
        return result

    def _load_row(self, row: tuple | None) -> dict[str, Any] | None:
        if row is None:
            return None
        number, key, snapshot = row
        analysis_id = f"analysis_{number:03d}"
        cached = self._items.get(analysis_id)
        result = cached if cached is not None else decode_snapshot(snapshot, analysis_id, key)
        if result.get("_datasetVersion") != self.dataset_version:
            raise ValueError("The analysis was created with a different data or algorithm version.")
        return self._remember(result)

    def find(self, request: AnalysisRequest) -> dict[str, Any] | None:
        key = self.request_key(request)
        with self.lock:
            if key in self._keys:
                return super().get(self._keys[key])
            with database_connection(self.settings) as connection:
                row = connection.execute(
                    "SELECT id, request_key, snapshot FROM landing_analyses WHERE request_key = %s", (key,)
                ).fetchone()
            return self._load_row(row)

    def get(self, analysis_id: str) -> dict[str, Any] | None:
        with self.lock:
            cached = super().get(analysis_id)
            if cached is not None:
                return cached
            prefix = "analysis_"
            suffix = analysis_id.removeprefix(prefix)
            if not analysis_id.startswith(prefix) or not suffix.isascii() or not suffix.isdigit():
                return None
            number = int(suffix)
            if analysis_id != f"analysis_{number:03d}" or number > 9223372036854775807:
                return None
            with database_connection(self.settings) as connection:
                row = connection.execute(
                    "SELECT id, request_key, snapshot FROM landing_analyses WHERE id = %s", (number,)
                ).fetchone()
            return self._load_row(row)

    def put(self, request: AnalysisRequest, result: dict[str, Any]) -> dict[str, Any]:
        key = self.request_key(request)
        with self.lock:
            existing = self.find(request)
            if existing is not None:
                return existing
            result["_datasetVersion"] = self.dataset_version
            payload = encode_snapshot(result)
            with database_connection(self.settings) as connection:
                row = connection.execute("""INSERT INTO landing_analyses (request_key, snapshot)
                    VALUES (%s, %s) ON CONFLICT (request_key) DO NOTHING RETURNING id""", (key, payload)).fetchone()
                if row is None:
                    row = connection.execute(
                        "SELECT id, request_key, snapshot FROM landing_analyses WHERE request_key = %s", (key,)
                    ).fetchone()
                    return self._load_row(row)
            result["analysisId"] = f"analysis_{row[0]:03d}"
            result["_requestKey"] = key
            return self._remember(result)

    def save(self, result: dict[str, Any]) -> None:
        payload = encode_snapshot(result)
        with self.lock:
            try:
                with database_connection(self.settings) as connection:
                    connection.execute("UPDATE landing_analyses SET snapshot = %s WHERE id = %s",
                                       (payload, int(result["analysisId"].removeprefix("analysis_"))))
            except psycopg.Error:
                self._items.pop(result["analysisId"], None)
                self._keys.pop(result["_requestKey"], None)
                raise
