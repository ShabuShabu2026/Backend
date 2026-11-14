# Backend

## Current development status

The lunar analysis engine requires prepared offline artifacts. `GET /config` and
`GET /weights` work without them. `GET /health` reports `DATA_NOT_READY` until
the grid, horizon masks, sky table and all objective references are ready.

Run from the repository root with Python 3.12:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m scripts.fetch_sky_table
python -m scripts.precompute_grid
python -m scripts.precompute_reference
python -m scripts.precompute_masks
python -m scripts.validate_baseline
python -m scripts.calibrate_delta
uvicorn app.main:app --reload
python -m pytest
ruff check .
```

Horizon preprocessing is computationally expensive. The reference script requires
the complete roughness raster and PSR shapefile; geology and crater objective
scores additionally require their source datasets. See `docs/DECISIONS.md` for
the exact source paths, data limitations and provisional settings. Generated
`artifacts/` files are not committed. Source `data/` is read-only to the scripts.
The application reads `ARTIFACTS_DIR` (default `./artifacts`) and `DATA_DIR` to
locate the prepared files. Railway must have persistent access to both; a GitHub
deployment alone does not include ignored artifacts or source data. The current
container startup script downloads only the original DEM and baseline datasets,
so a complete deployment requires a separate artifact provisioning procedure.
Keep `WEB_CONCURRENCY=1`: the analysis cache is local to each server process.
`calibrate_delta` additionally requires the four PGDA 78 Site DEMs. It reports a
matched 2 km comparison and a 100 km hybrid estimate, and does not change the
configured Earth margin. The 5 m tiles do not cover a full 100 km radius.
