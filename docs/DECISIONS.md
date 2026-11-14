# Decisions and data inventory

## Data inventory

`data/` is read-only. `data/DATASETS.md` was inspected; its non-ASCII text is corrupted, so the file paths, sizes and inspection results were also checked directly.

- DEM: `data/dem/LDEM_80S_80MPP_ADJ.TIF`, 80 m pixels; south polar stereographic, spherical Moon radius 1,737,400 m, central longitude 0 and latitude -90 degrees. The DEM file is the authority for its exact CRS and affine transform.
- Baselines: both `AVGVISIB_85S_060M_201608.LBL` and `_EARTH.LBL` and their IMG files exist. Labels specify polar stereographic, -90/0 degree center, 1,737.4 km sphere, and the DE421 mean Earth/polar axis frame. Their 60 m grids have different extents from the DEM. Exact CRS equivalence is not yet established; validation must reproject when needed.
- PSR: full shapefile and 1 km2 subset exist. Previous `ogrinfo -so` verification found 506,349 and 1,531 polygons respectively. Fields: `gid`, `area_km2`, `name`.
- Slope: `data/terrain/LDSM_80S_80MPP_ADJ.TIF`, 80 m; the finer 20 m product is absent. Its slope baseline is not yet verified; 80 m resolution can underestimate slope.
- Roughness: `data/terrain/LDRM_80S_50MPP_ADJ_ROUGH_100M.TIF` was completed with explicit user permission and verified against the 645,351,631-byte server size. It has 50 m pixels and a 100 m roughness baseline.
- The optional 5 m site DEMs are missing. With explicit permission, the USGS geology and crater datasets were downloaded. The global geology archive includes shapefiles and compressed geodatabases; the latter cannot be read by the available OpenFileGDB driver. The `GeoUnits.shp` polygon layer has 12,247 polygons, with unit codes in `FIRST_Unit` (49 distinct global codes). `FIRST_Un_1` holds era names and `FIRST_Un_2` holds descriptive names. The `LU78287GT_Moon2000.shp` crater layer has 78,287 points and fields `Lon_E`, `Lat`, `p`, `Name`, `Radius_deg`, `Radius_km`. It has no age field. The 20 km diameter cutoff is applied as `Radius_km >= 10`.
- Global geology is clipped in its native equirectangular CRS to south of 80 degrees before reprojection to avoid the north-pole singularity and preserve the 20 km search area around the grid south of 85 degrees. The output geometries are made valid; all distances and unit intersections are computed in the DEM CRS.

## Provisional values

All are defined in `app/settings.py`: base grid spacing 1,000 m; heights 1/5/10 m; 720 azimuths (0.5 degrees) for base and refined masks; maximum and comparison horizon distances 100 km and 50 km with 100 samples; Earth center margin 0.25 degrees; required sunlight LOW/NORMAL/HIGH 30/50/80%; geology radius 20 km and preprocessing clip latitude -80 degrees; crater diameter threshold 20 km; reference percentile 95; analysis cache size 50; target 10 seconds; separation factor 0.5; marginal threshold 0.9; refined minimum spacing 200 m and target 5,000 points; candidate limit 50; CORS all origins; and tags Good Earth visibility, Flat terrain, Low roughness, High sunlight, Objective match. Objective score definitions remain provisional as specified in the task.

## Open issues and measurements

- Base grid: 72,297 points, zero nonfinite elevation/slope/roughness values; 19.75 seconds. Reference preprocessing: 65.95 seconds. Fixed 95th percentiles: PSR distance 1,545.477 m; geological unit count 4; large-crater distance 55,596.851 m. Site DEMs are still required for 5 m horizon calibration.
- Horizons 2027 table downloaded from JPL Horizons: 8,760 hourly rows. The Moon observer output specifies MOON_ME, east-positive longitude, and a spherical 1,737.4 km target. Apparent planetodetic and planetocentric latitudes coincide for this spherical target. Maximum absolute Earth subpoint longitude/latitude: 7.768/6.847 degrees; median subsolar synodic period: 29.528 days. Horizons reports DE441 ephemerides; the specified MOON_ME frame is retained, and validation against the DE421 datasets remains outstanding.
- A reproducible 100-point 1 m-height sample gave a maximum 5.873 degrees difference between 50 km and 100 km horizon search distances; the longer distance remains in use. Full horizon masks, baseline comparisons and full analysis performance measurements are not yet available.
- Baseline comparison uses 2,000 reproducibly sampled points, the label-provided 0.00004 scaling, and the label's any-visible-disk criteria (`PARTIAL` Sun and `UPPER_EDGE` Earth). A provisional absolute mean-bias warning threshold of 0.1 is defined in settings.
- Local acquisition SHA-256 values: roughness `ba1fb29c8d7ddf14a57d8a328098ccca49024c95a14dca251f9ca7c2ba33d6ea`; geology archive `f3ec29803c1ad3b8c41a7fff3e9339bd66f9fbb8f63e30f13c52561b8d5559a1`; crater archive `b9ac25611f3dc8f7e8ccb2b6488d4451476439ab05164b006996b0f345ab21b3`. These hashes identify downloaded files; they are not compared to publisher hashes.
- Until artifact loading and the analysis engine are implemented, `/health` and a valid `POST /analyses` return 503; no synthetic analysis results are generated.
- Zero slope cap: the specified provisional rule gives passed sites flatness 1.
- Required sunlight ratio zero: the sunlight requirement term is treated as satisfied (1); the input specification permits zero but does not define division by zero.
