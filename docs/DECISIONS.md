# Decisions and data inventory

## Data inventory

`data/` is read-only. `data/DATASETS.md` was inspected; its non-ASCII text is corrupted, so the file paths, sizes and inspection results were also checked directly.

- DEM: `data/dem/LDEM_80S_80MPP_ADJ.TIF`, 80 m pixels; south polar stereographic, spherical Moon radius 1,737,400 m, central longitude 0 and latitude -90 degrees. The DEM file is the authority for its exact CRS and affine transform.

The DEM CRS WKT as read by Rasterio is:

```text
PROJCS["Moon (2015) - Sphere / Ocentric / South Polar",GEOGCS["Moon (2015) - Sphere / Ocentric",DATUM["Moon (2015) - Sphere",SPHEROID["Moon (2015) - Sphere",1737400,0,AUTHORITY["IAU","30100"]],AUTHORITY["IAU","30100"]],PRIMEM["Reference Meridian",0,AUTHORITY["IAU","30100"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["IAU","30100"]],PROJECTION["Polar_Stereographic"],PARAMETER["latitude_of_origin",-90],PARAMETER["central_meridian",0],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",NORTH],AXIS["Northing",NORTH],AUTHORITY["IAU","30135"]]
```

- Baselines: both `AVGVISIB_85S_060M_201608.LBL` and `_EARTH.LBL` and their IMG files exist. Labels specify polar stereographic, -90/0 degree center, 1,737.4 km sphere, and the DE421 mean Earth/polar axis frame. Their 60 m grids have different extents from the DEM. Exact CRS equivalence is not yet established; validation must reproject when needed.
- PSR: full shapefile and 1 km2 subset exist. Previous `ogrinfo -so` verification found 506,349 and 1,531 polygons respectively. Fields: `gid`, `area_km2`, `name`.
- Slope: `data/terrain/LDSM_80S_80MPP_ADJ.TIF`, 80 m; the finer 20 m product is absent. Its slope baseline is not yet verified; 80 m resolution can underestimate slope.
- Roughness: `data/terrain/LDRM_80S_50MPP_ADJ_ROUGH_100M.TIF` was completed with explicit user permission and verified against the 645,351,631-byte server size. It has 50 m pixels and a 100 m roughness baseline.
- The optional 5 m site DEMs are missing. With explicit permission, the USGS geology and crater datasets were downloaded. The global geology archive includes shapefiles and compressed geodatabases; the latter cannot be read by the available OpenFileGDB driver. The `GeoUnits.shp` polygon layer has 12,247 polygons, with unit codes in `FIRST_Unit` (49 distinct global codes). `FIRST_Un_1` holds era names and `FIRST_Un_2` holds descriptive names. The `LU78287GT_Moon2000.shp` crater layer has 78,287 points and fields `Lon_E`, `Lat`, `p`, `Name`, `Radius_deg`, `Radius_km`. It has no age field. The 20 km diameter cutoff is applied as `Radius_km >= 10`.
- Global geology is clipped in its native equirectangular CRS to south of 80 degrees before reprojection to avoid the north-pole singularity and preserve the 20 km search area around the grid south of 85 degrees. The output geometries are made valid; all distances and unit intersections are computed in the DEM CRS.

## Provisional values

All are defined in `app/settings.py`: base grid spacing 1,000 m; heights 1/5/10 m; 720 azimuths (0.5 degrees) for base and refined masks; maximum and comparison horizon distances 100 km and 50 km with 100 samples; Earth center margin 0.25 degrees; required sunlight LOW/NORMAL/HIGH 30/50/80%; geology radius 20 km and preprocessing clip latitude -80 degrees; crater diameter threshold 20 km; reference percentile 95; analysis cache size 50; target 10 seconds; separation factor 0.5; marginal threshold 0.9; refined minimum spacing 200 m and target 5,000 points; candidate limit 50; CORS all origins; and tags Good Earth visibility, Flat terrain, Low roughness, High sunlight, Objective match. Objective score definitions remain provisional as specified in the task.

## Open issues and measurements

- Base grid: 72,297 points, zero nonfinite elevation/slope/roughness values; 19.75 seconds. Reference preprocessing: 65.95 seconds before and 124.44 seconds while horizon preprocessing was also running. Fixed 95th percentiles: PSR distance 1,545.477 m; geological unit count 4; large-crater center distance 55,596.851 m.
- Horizons 2027 table downloaded from JPL Horizons: 8,760 hourly rows. The Moon observer output specifies MOON_ME, east-positive longitude, and a spherical 1,737.4 km target. Apparent planetodetic and planetocentric latitudes coincide for this spherical target. Maximum absolute Earth subpoint longitude/latitude: 7.768/6.847 degrees; median subsolar synodic period: 29.528 days. Horizons reports DE441 ephemerides; the specified MOON_ME frame is retained, and validation against the DE421 datasets remains outstanding.
- A separate timed Horizons download and parse took 10.707 seconds; it was performed in a temporary directory without replacing the retained sky artifact.
- Full 1 m, 5 m and 10 m horizon mask preprocessing took 2,090.12 seconds. A reproducible 100-point 1 m-height sample gave a maximum 5.873 degrees difference between 50 km and 100 km horizon search distances; the longer distance remains in use. All 3 masks were checked for finite values and matching grid dimensions.
- Baseline comparison on 2,000 samples: Sun correlation 0.984003, mean absolute difference 0.015455, mean bias +0.013411; Earth correlation 0.979514, mean absolute difference 0.023644, mean bias -0.002528. Neither mean bias exceeds the provisional 0.1 warning threshold. The comparison used Rasterio CRS transforms into each baseline and took 3.44 seconds; the datasets describe different years and source resolutions.
- The default 72,297-site POST analysis took 3.373 seconds on this machine including initial JIT compilation, with 1,239 passing sites and 10 candidates; an identical cached request took 0.097 seconds. A 1 km half-width refined grid matched the base site's 84.4 score and produced 10 recommendations; 2 km and 40 km half-width tests also returned 10.
- Actual PSR, planetary-processes and impact-history analyses returned 10 candidates each. At a sampled candidate, the base and refined scores matched exactly: 84.0, 85.3 and 80.6 respectively. Crater proximity uses crater center points, not crater rims.
- The Docker image was built and run as UID 10001 with the real source data and artifacts mounted read-only. `/health` returned 200 and the default analysis returned 201 with 72,297 sites and 10 candidates in 3.76 seconds in the Linux container.
- Analysis storage is an in-process LRU, so `WEB_CONCURRENCY` must remain 1 unless shared storage or sticky routing is introduced. A deployed service also needs persistent access to all source datasets and generated artifacts; the present container startup downloads only DEM and baselines.
- Baseline comparison uses 2,000 reproducibly sampled points, the label-provided 0.00004 scaling, and the label's any-visible-disk criteria (`PARTIAL` Sun and `UPPER_EDGE` Earth). A provisional absolute mean-bias warning threshold of 0.1 is defined in settings.
- Local acquisition SHA-256 values: roughness `ba1fb29c8d7ddf14a57d8a328098ccca49024c95a14dca251f9ca7c2ba33d6ea`; geology archive `f3ec29803c1ad3b8c41a7fff3e9339bd66f9fbb8f63e30f13c52561b8d5559a1`; crater archive `b9ac25611f3dc8f7e8ccb2b6488d4451476439ab05164b006996b0f345ab21b3`. These hashes identify downloaded files; they are not compared to publisher hashes.

## 5 m site DEM horizon comparison

The four PGDA 78 files were downloaded and checked against the server's byte lengths. Each is a 3,200 × 3,200 GeoTIFF at 5 m/pixel, covering 16 × 16 km, with NaN nodata. Sources and locally calculated SHA-256 values:

| Site | Bytes | Source | SHA-256 |
| --- | ---: | --- | --- |
| Site01 | 40,980,810 | [Site01 DEM](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/Site01_final_adj_5mpp_surf.tif) | `3ba7b97cb00a2bcf21189c3aeb535f65afc21207154ab9f0d43c5bdc1f7e747e` |
| Site04 | 40,980,806 | [Site04 DEM](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site04/Site04_final_adj_5mpp_surf.tif) | `38ff70dbdf2f066c2cfa94a646c3a59d653ce7f6b4528b15fc1b43ee397ce758` |
| Site07 | 40,980,808 | [Site07 DEM](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site07/Site07_final_adj_5mpp_surf.tif) | `38aaee10bb4da4d63e7427aa1ca25c79bdbc649d212079a04990e135462091f8` |
| Site11 | 40,980,806 | [Site11 DEM](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site11/Site11_final_adj_5mpp_surf.tif) | `58f3372c35bbd6baf38ffd5633c1c96b59bd89dbd252150581d12893a43136e5` |

The fine DEM WKT has an unnamed datum and is not formally equal to the base DEM CRS. The projection method, parameters, axis units, prime meridian and spherical radius match numerically; PGDA describes both products as south-polar stereographic in the MOON_ME/DE421 frame. The comparison uses the common projected coordinates on that basis. This is not an independent registration or vertical datum accuracy assessment.

The reproducible `python -m scripts.calibrate_delta` comparison uses a provisional 2,000 m common local radius, 1 m observer height, up to 25 randomly selected 1 km base-grid locations per site, seed 2027, and 720 azimuths. These provisional values are defined in `app/settings.py`. Each selected location has a complete finite-data disk plus a two-pixel safety margin. All four sites had 121 eligible locations; the sample has 100 distinct locations and 72,000 location/azimuth comparisons. Signed difference means fine or hybrid horizon minus coarse horizon.

| Site | Local 2 km absolute difference P95 | 100 km hybrid signed difference P95 | 100 km hybrid absolute difference P95 |
| --- | ---: | ---: | ---: |
| Site01 | 2.3531° | 2.0606° | 2.0606° |
| Site04 | 1.1985° | 0.6147° | 0.6596° |
| Site07 | 1.3849° | 0.9752° | 0.9752° |
| Site11 | 2.2032° | 1.2368° | 1.2923° |
| All sites | 1.7385° | 1.2882° | 1.3119° |

The 100 km hybrid uses 5 m terrain inside 2 km and 80 m terrain outside 2 km, with outer angles referenced to the 5 m observer elevation. It is not a fully independent 100 km 5 m horizon; far terrain and correlated azimuth samples remain limitations. The pooled signed and absolute 95th percentiles exceed the provisional `EARTH_DELTA_DEG = 0.25`, but the sample is limited to four regions and does not establish a globally appropriate margin. The default remains unchanged. The final run took about 5.70 seconds after data loading, and outputs `artifacts/delta_calibration.json` with sampled grid IDs and per-site summaries.
- `/health` returns 503 until all required artifact files and objective scores are loaded and validated. Analysis requests for a missing objective return 503; no synthetic scores are generated.
- Zero slope cap: the specified provisional rule gives passed sites flatness 1.
- Required sunlight ratio zero: the sunlight requirement term is treated as satisfied (1); the input specification permits zero but does not define division by zero.
