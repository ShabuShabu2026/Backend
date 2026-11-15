# Lunar Landing Site Analysis Backend

FastAPI backend for analysing lunar south pole landing sites, terrain, and Sun and Earth visibility.

## Requirements

- Python 3.12
- Windows PowerShell for the local commands below
- Internet access to download the source data and JPL Horizons data
- PostgreSQL 18 for persistent analysis storage (optional for local development)
- Docker for container builds and deployment

## 1. Install

Run the following commands in PowerShell from the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

For a runtime-only installation, use `python -m pip install -r requirements.txt`.

## 2. Configure the environment

Create a local environment file:

```powershell
Copy-Item .env.example .env
notepad .env
```

Replace the empty entries in `.env` with appropriate values. For local development without PostgreSQL, a minimal example is:

```dotenv
DATA_DIR=./data
ARTIFACTS_DIR=./artifacts
CORS_ORIGINS=http://localhost:3000
WEB_CONCURRENCY=1
```

Remove the empty `DATABASE_URL` line when running without PostgreSQL. To persist analyses, create a PostgreSQL database and add its connection URL:

```dotenv
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/lunar
```

Replace the username, password, host, port and database name with the values for your PostgreSQL installation. The configured PostgreSQL user must have permission to create the analysis table. Do not commit `.env`.

| Variable          | Default                 | Purpose                                                                                                                                                                       |
| ----------------- | ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DATA_DIR`        | `./data`                | Location of source datasets used by the application.                                                                                                                          |
| `ARTIFACTS_DIR`   | `./artifacts`           | Location of the precomputed grid, horizon masks and other analysis artifacts.                                                                                                 |
| `DATABASE_URL`    | Unset                   | PostgreSQL connection URL. When unset, analysis results use an in-memory cache and are lost on restart.                                                                       |
| `WEB_CONCURRENCY` | `1`                     | Uvicorn worker count in the container. Use `1` because local caches and refined-site updates are not synchronized across workers.                                             |
| `CORS_ORIGINS`    | `http://localhost:3000` | Declared setting; the current app uses the `CORS_ORIGINS` constant in `app/settings.py`, which is `("*",)`, so this environment variable does not currently restrict origins. |
| `PORT`            | `8000`                  | Port used by the container start command; Railway supplies this variable.                                                                                                     |

## 3. Prepare the source data

Download the DEM and Sun/Earth visibility baselines:

```powershell
python scripts/download_data.py
```

The download script reads `DATA_DIR` from the process environment, not from `.env`. If using a different directory, set `$env:DATA_DIR` before running it. The script downloads only the DEM and the baseline files. Prepare the following additional source data separately:

```text
data/
  dem/
    LDEM_80S_80MPP_ADJ.TIF
  baseline/
    AVGVISIB_85S_060M_201608.IMG
    AVGVISIB_85S_060M_201608.LBL
    AVGVISIB_85S_060M_201608_EARTH.IMG
    AVGVISIB_85S_060M_201608_EARTH.LBL
  terrain/
    LDSM_80S_80MPP_ADJ.TIF
    LDRM_80S_50MPP_ADJ_ROUGH_100M.TIF
  psr/
    LPSR_80S_20MPP_ADJ.SHP
    LPSR_80S_20MPP_ADJ.SHX
    LPSR_80S_20MPP_ADJ.DBF
    LPSR_80S_20MPP_ADJ.PRJ
  geology/
    Unified_Geologic_Map_of_the_Moon_GIS/Lunar_GIS/Shapefiles/GeoUnits.shp
    ... and its shapefile companion files
  craters/
    goransalamuniccar_mooncraters.zip
```

See [data/DATASETS.md](data/DATASETS.md) for source links and descriptions. These datasets are not included in Git. The optional 5 m site DEMs described there are used for horizon validation, not ordinary API startup.

## 4. Generate analysis artifacts

From the repository root, run these commands in order after preparing the source data:

```powershell
python -m scripts.fetch_sky_table
python -m scripts.precompute_grid
python -m scripts.precompute_reference
python -m scripts.precompute_masks
```

These commands write to `./artifacts` by default and use the source files under `./data`. Horizon mask generation is computationally intensive. If using a different `DATA_DIR` or `ARTIFACTS_DIR`, use the scripts' command-line options where available or provision the generated files in the configured locations. The reference and sky-table scripts use the default paths.

The sky table covers 2026-01-01 00:00 through 2028-12-31 23:00 UTC. The full landing-date search range and stay must fit within the available time range.

## 5. Start and verify

```powershell
uvicorn app.main:app --reload
```

Open:

- API documentation: http://127.0.0.1:8000/docs
- Health and loaded sky data range: http://127.0.0.1:8000/health

`/health` reports `DATA_NOT_READY` until the required analysis artifacts are loaded. A missing objective artifact also prevents analysis for that objective.

To run checks from another activated PowerShell terminal:

```powershell
python -m pytest
ruff check .
```

## Docker and Railway

Build the image from the repository root:

```powershell
docker build -t lunar-backend .
```

The image excludes `data/` and `artifacts/`. The container entrypoint runs `scripts/download_data.py` and starts Uvicorn using `PORT` and `WEB_CONCURRENCY`. It does not generate the analysis artifacts.

For Railway:

1. Deploy the repository as the Backend service and add a PostgreSQL service if persistent analysis storage is required.
2. Add a persistent volume to the Backend service at `/app/data`. Provision the source files and the generated artifacts in that volume, for example under downloads, writable by the container user.
3. Set Backend variables: Use the actual PostgreSQL service name in the Railway variable reference. Omit `DATABASE_URL` when not using PostgreSQL. See the CORS note above.

   ```dotenv
   DATA_DIR=/app/data
   ARTIFACTS_DIR=/app/data/artifacts
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   WEB_CONCURRENCY=1
   ```

4. Start or redeploy the service, then check `/health` and `/docs` on the enerated Railway domain.

When source data, artifacts or calculation code change, previous analysis snapshots may return `ANALYSIS_VERSION_CHANGED`; create a new analysis. See [docs/DECISIONS.md](docs/DECISIONS.md) for analysis settings and validation.
