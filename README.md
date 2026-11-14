# Backend

## Current development status

The lunar analysis engine is under development. `GET /config` and `GET /weights`
are available. `GET /health` and valid `POST /analyses` return `DATA_NOT_READY`
until the required data and analysis artifacts are available.

Run from the repository root with Python 3.12:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m scripts.fetch_sky_table
python -m scripts.precompute_grid
uvicorn app.main:app --reload
python -m pytest
ruff check .
```

The grid precomputation currently stops with a clear error because the complete
roughness raster is missing. It does not use the partial download. See
`docs/DECISIONS.md` for data availability and provisional settings. The generated
`artifacts/` directory is not committed. The source `data/` directory is read-only.
