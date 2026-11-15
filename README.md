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
The sky table covers hourly data from 2026-01-01 through 2028-12-31 UTC.
The complete landing-date search and stay window must fit within this range.
After updating the code, regenerate `sky_table.npz` with
`python -m scripts.fetch_sky_table` and provision the resulting file in Railway's
`ARTIFACTS_DIR` before restarting the service. The file is ignored by Git and is
not deployed automatically. Existing analysis snapshots use the old artifact
version and must be recreated after the update.
When `DATABASE_URL` is configured, startup creates `landing_analyses` if needed.
Analysis snapshots and refined site data are stored in PostgreSQL; they survive
restarts, and identical requests with the same data and code reuse the analysis.
The PostgreSQL user therefore needs permission to create this table. Keep
`WEB_CONCURRENCY=1`: the local read cache and concurrent refined-grid updates are
not synchronized across workers. With no `DATABASE_URL`, storage falls back to
an in-memory LRU and analyses disappear on restart. Database storage currently
has no automatic expiration; monitor storage and back up the PostgreSQL volume.
Startup hashes the relevant source data, artifacts and application code. If any
of these change, fetching a previous analysis returns `ANALYSIS_VERSION_CHANGED`;
run a new analysis rather than mixing old scores with new data. Hashing these
large files adds disk reads and startup time. Existing in-memory analyses from
older deployments cannot be recovered retroactively.
`calibrate_delta` additionally requires the four PGDA 78 Site DEMs. It reports a
matched 2 km comparison and a 100 km hybrid estimate, and does not change the
configured Earth margin. The 5 m tiles do not cover a full 100 km radius.

## 3D terrain and celestial directions

Create an analysis first, then request
`GET /analyses/{analysisId}/sites/{siteId}/terrain?radiusM=2000`. The radius is
in meters, defaults to 2,000 and is limited to 5,000. The response contains
`site_id`, `latitude`, `longitude`, `heights`, `resolution_m`,
`coordinate_system`, and `elevation_reference`. Previous response fields are
also retained for existing clients. `heights` is a row-major grid of elevations
in meters. Its cells can be `null` where the DEM has no data; clients must not
interpret those cells as zero elevation. A raster-edge request can be clipped.

`coordinate_system.crs_wkt` describes the DEM's actual projected CRS.
`coordinate_system.origin` is the center of the upper-left pixel. Given row `r`
and column `c`, its projected position is `origin + c * column_step + r *
row_step`; `site_position` gives the selected site's projected position, which
may not coincide with a pixel center or the center of a clipped grid. These are
projection axes, not necessarily local true east and north. For the supplied
LOLA product, elevations are relative to the 1,737,400 m lunar reference
sphere. This reference is assumed for the supplied LOLA product; the horizontal
CRS alone does not verify the vertical datum. `elevation_reference` is `null`
when the raster's CRS does not match that sphere. Product description:
[NASA PGDA 90](https://pgda.gsfc.nasa.gov/products/90).

For a time slider, `GET /analyses/{analysisId}/sites/{siteId}/visibility`
returns hourly `timestamp`, `sun_azimuth`, `sun_elevation`, `earth_azimuth`,
`earth_elevation`, `sun_visible`, and `earth_visible`, in addition to the
existing camelCase fields. Timestamps are UTC, angles are in degrees, azimuth
is clockwise from local true north, and elevation is above the local horizontal.
Visibility accounts for the site's terrain horizon and the criteria used for
the analysis; it is not a visibility calculation for every terrain mesh vertex.
