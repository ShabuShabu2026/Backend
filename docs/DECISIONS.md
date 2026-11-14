# Decisions and data inventory

## Data inventory

`data/` is read-only. `data/DATASETS.md` was inspected; its non-ASCII text is corrupted, so the file paths, sizes and inspection results were also checked directly.

- DEM: `data/dem/LDEM_80S_80MPP_ADJ.TIF`, 80 m pixels; south polar stereographic, spherical Moon radius 1,737,400 m, central longitude 0 and latitude -90 degrees. The DEM file is the authority for its exact CRS and affine transform.
- Baselines: both `AVGVISIB_85S_060M_201608.LBL` and `_EARTH.LBL` and their IMG files exist. Labels specify polar stereographic, -90/0 degree center, 1,737.4 km sphere, and the DE421 mean Earth/polar axis frame. Their 60 m grids have different extents from the DEM. Exact CRS equivalence is not yet established; validation must reproject when needed.
- PSR: full shapefile and 1 km2 subset exist. Previous `ogrinfo -so` verification found 506,349 and 1,531 polygons respectively. Fields: `gid`, `area_km2`, `name`.
- Slope: `data/terrain/LDSM_80S_80MPP_ADJ.TIF`, 80 m; the finer 20 m product is absent. Its slope baseline is not yet verified; 80 m resolution can underestimate slope.
- Roughness: the complete 50 m product is missing; the `.TIF.part` file is incomplete and must not be used. The last download failed due to a network error.
- The optional 5 m site DEMs, geology and crater datasets are missing. Geology layer/unit-code fields and crater fields are therefore unknown. No crater age field is assumed.

## Provisional values

All are defined in `app/settings.py`: base grid spacing 1,000 m; heights 1/5/10 m; 720 azimuths (0.5 degrees) for base and refined masks; maximum and comparison horizon distances 100 km and 50 km with 100 samples; Earth center margin 0.25 degrees; required sunlight LOW/NORMAL/HIGH 30/50/80%; geology radius 20 km; crater diameter threshold 20 km; reference percentile 95; analysis cache size 50; target 10 seconds; separation factor 0.5; marginal threshold 0.9; refined minimum spacing 200 m and target 5,000 points; candidate limit 50; CORS all origins; and tags Good Earth visibility, Flat terrain, Low roughness, High sunlight, Objective match. Objective score definitions remain provisional as specified in the task.

## Open issues and measurements

- Full analysis and reference artifacts cannot be produced until roughness is complete. Geology, impact history and 5 m horizon calibration require the missing datasets.
- Horizons 2027 table downloaded from JPL Horizons: 8,760 hourly rows. The Moon observer output specifies MOON_ME, east-positive longitude, and a spherical 1,737.4 km target. Apparent planetodetic and planetocentric latitudes coincide for this spherical target. Maximum absolute Earth subpoint longitude/latitude: 7.768/6.847 degrees; median subsolar synodic period: 29.528 days. Horizons reports DE441 ephemerides; the specified MOON_ME frame is retained, and validation against the DE421 datasets remains outstanding.
- Full horizon masks, reference values, baseline comparisons and performance measurements are not yet available.
- Until artifact loading and the analysis engine are implemented, `/health` and a valid `POST /analyses` return 503; no synthetic analysis results are generated.
- Zero slope cap: the specified provisional rule gives passed sites flatness 1.
