import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from app.engine.artifacts import load_artifacts
from scripts import precompute_masks


def test_incomplete_masks_do_not_report_ready(tmp_path: Path) -> None:
    grid = tmp_path / "grid.npz"
    np.savez(grid, ids=np.array(["LSP-0001"]), x=[0], y=[0], lat=[-90], lon=[0],
             elevation=[0], slope=[0], roughness=[0], crs="test")
    with pytest.raises(FileNotFoundError, match="horizon_manifest"):
        load_artifacts(tmp_path)
    with grid.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    (tmp_path / "horizon_manifest.json").write_text(json.dumps({
        "gridSha256": digest, "gridPointCount": 1, "heightsM": [1, 5, 10], "azimuthCount": 720,
    }))
    with pytest.raises(FileNotFoundError, match="sky_table"):
        load_artifacts(tmp_path)


def test_mask_completion_manifest_only_after_all_heights(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grid = tmp_path / "grid.npz"
    np.savez(grid, x=[0.0], y=[0.0], lat=[-90.0], lon=[0.0])
    dem = tmp_path / "dem.tif"
    with rasterio.open(dem, "w", driver="GTiff", height=5, width=5, count=1, dtype="float32",
                       crs="+proj=stere +lat_0=-90 +lon_0=0 +R=1737400 +units=m",
                       transform=from_origin(-200, 200, 80, 80)) as dataset:
        dataset.write(np.zeros((1, 5, 5), dtype="float32"))
    monkeypatch.setattr(precompute_masks, "horizon_masks", lambda dem, cols, rows, h, px, dist, az, offsets:
                        np.full((len(cols), az), h, dtype="float32"))
    output = tmp_path / "output"
    precompute_masks.run(grid, dem, output)
    metadata = json.loads((output / "horizon_manifest.json").read_text())
    assert metadata["heightsM"] == [1, 5, 10]
    assert not list(output.glob("*.part"))
    assert np.load(output / "horizon_10m.npy")[0, 0] == 10
