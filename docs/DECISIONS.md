# Decisions and data inventory

## Data and coordinate system

The analysis uses lunar terrain and visibility datasets documented in
[`data/DATASETS.md`](../data/DATASETS.md). The 80 m LOLA DEM is the authority
for the analysis grid CRS and affine transform: a south polar stereographic
projection on a 1,737,400 m lunar sphere, centred at latitude -90 degrees and
longitude 0 degrees. Slope and roughness are sampled for both the base grid and
refined sites. The 80 m slope resolution can smooth smaller-scale terrain.

The baseline maps use 60 m grids and describe the DE421 mean Earth/polar axis
frame. Their projection parameters are consistent with the DEM's south polar
stereographic geometry; exact CRS equivalence has not been established, so the
baseline comparison uses coordinate transforms when needed.

The full PSR shapefile is used for polar volatiles. Geologic unit diversity is
computed from the `GeoUnits` layer within 20 km of each site. The crater
catalogue supplies crater centre positions for features at least 20 km in
diameter. Global geology is clipped south of 80 degrees before reprojection to
avoid the north-pole singularity.

## Analysis settings

The settings in `app/settings.py` define a 1,000 m base grid, observer heights
of 1, 5 and 10 m, 720 horizon azimuths, and a 100 km maximum horizon distance.
The Earth-centre visibility margin is 0.25 degrees and remains provisional.
The default required sunlight ratios for LOW, NORMAL and HIGH power are 30%,
50% and 80%, respectively.

The JPL Horizons table covers 2026-01-01 00:00 through 2028-12-31 23:00 UTC
at hourly intervals (26,304 entries). It uses the Moon-fixed `MOON_ME` frame.
The entire requested landing-date search and stay must fit within this period.
The baseline maps and Horizons products use different source epochs and
reference frame descriptions; their comparison should be interpreted accordingly.

## Storage and deployment

When `DATABASE_URL` is set, analysis snapshots and refined site data are stored
in PostgreSQL; otherwise, the application uses an in-memory LRU cache. Keep
`WEB_CONCURRENCY=1` because the local read cache and concurrent refined-grid
updates are not synchronized across workers. Source data and generated artifacts
are provisioned separately from the application image. Changing relevant inputs
or calculation code invalidates earlier analysis snapshots; a new analysis is
required.

## Validation results

A 2,000-site comparison with the Sun and Earth baseline maps produced Sun
correlation 0.984003 and mean absolute difference 0.015455, and Earth
correlation 0.979514 and mean absolute difference 0.023644. The reference maps
and calculated results represent different years and resolutions. The
comparison uses the label scale and the any-visible-disk criteria (`PARTIAL`
for Sun and `UPPER_EDGE` for Earth).

A reproducible 100-point, 1 m-height horizon sample found a maximum 5.873 degree
difference between 50 km and 100 km search distances. The application uses the
100 km distance. The full base grid contains 72,297 sites.

## 5 m site DEM horizon comparison

The four PGDA 78 files were downloaded and checked against the server's byte lengths. Each is a 3,200 × 3,200 GeoTIFF at 5 m/pixel, covering 16 × 16 km, with NaN nodata. Sources and locally calculated SHA-256 values:

| Site | Bytes | Source | SHA-256 |
| --- | ---: | --- | --- |
| Site01 | 40,980,810 | [Site01 DEM](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/Site01_final_adj_5mpp_surf.tif) | `3ba7b97cb00a2bcf21189c3aeb535f65afc21207154ab9f0d43c5bdc1f7e747e` |
| Site04 | 40,980,806 | [Site04 DEM](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site04/Site04_final_adj_5mpp_surf.tif) | `38ff70dbdf2f066c2cfa94a646c3a59d653ce7f6b4528b15fc1b43ee397ce758` |
| Site07 | 40,980,808 | [Site07 DEM](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site07/Site07_final_adj_5mpp_surf.tif) | `38aaee10bb4da4d63e7427aa1ca25c79bdbc649d212079a04990e135462091f8` |
| Site11 | 40,980,806 | [Site11 DEM](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site11/Site11_final_adj_5mpp_surf.tif) | `58f3372c35bbd6baf38ffd5633c1c96b59bd89dbd252150581d12893a43136e5` |

The fine DEM WKT has an unnamed datum and is not formally equal to the base DEM CRS. The projection method, parameters, axis units, prime meridian and spherical radius match numerically; PGDA describes both products as south-polar stereographic in the MOON_ME/DE421 frame. The comparison uses the common projected coordinates on that basis. This is not an independent registration or vertical datum accuracy assessment.

The reproducible `python -m scripts.calibrate_delta` comparison uses a 2,000 m common local radius, 1 m observer height, up to 25 randomly selected 1 km base-grid locations per site, seed 2027, and 720 azimuths. These values are defined in `app/settings.py`. Each selected location has a complete finite-data disk plus a two-pixel safety margin. All four sites had 121 eligible locations; the sample has 100 distinct locations and 72,000 location/azimuth comparisons. Signed difference means fine or hybrid horizon minus coarse horizon.

| Site | Local 2 km absolute difference P95 | 100 km hybrid signed difference P95 | 100 km hybrid absolute difference P95 |
| --- | ---: | ---: | ---: |
| Site01 | 2.3531° | 2.0606° | 2.0606° |
| Site04 | 1.1985° | 0.6147° | 0.6596° |
| Site07 | 1.3849° | 0.9752° | 0.9752° |
| Site11 | 2.2032° | 1.2368° | 1.2923° |
| All sites | 1.7385° | 1.2882° | 1.3119° |

The 100 km hybrid combines 5 m terrain within 2 km with 80 m terrain farther
away. The comparison covers 100 sampled locations across four sites. Its pooled
signed and absolute P95 values are 1.2882 and 1.3119 degrees. A 300-resample
location-level bootstrap gives a signed P95 interval of 0.828 to 1.828 degrees
for this sample. Results are saved in `artifacts/delta_calibration.json`.

At those locations, changing the Earth-centre margin from 0.25 to 1.2882
degrees changed 29,931 of 876,000 hourly visibility decisions (3.42%) in the
2027 sensitivity check. These figures describe the sampled sites.

### LROC stereo cross-check

The [LROC DTM footprint index](https://data.lroc.im-ldi.com/lroc/view_rdr/SHAPEFILE_NAC_DTMS) contains 662 footprints, of which nine have a footprint extending south of 85 degrees. Five stereo-derived elevation products were downloaded separately, without changing the existing `data/` datasets: [ESALL_SR12](https://data.lroc.im-ldi.com/lroc/view_rdr_product/NAC_DTM_ESALL_SR12), [ESALL_CR1](https://data.lroc.im-ldi.com/lroc/view_rdr_product/NAC_DTM_ESALL_CR1), [SHACKRDGE02](https://data.lroc.im-ldi.com/lroc/view_rdr_product/NAC_DTM_SHACKRDGE02), [MALAPERT03](https://data.lroc.im-ldi.com/lroc/view_rdr_product/NAC_DTM_MALAPERT03), and [NOBILE01](https://data.lroc.im-ldi.com/lroc/view_rdr_product/NAC_DTM_NOBILE01). The first three overlap the near-pole region; overlap and site selection make the 45 locations a convenience sample, not a population sample. LROC stereo uses a different observation technique, but shares geodetic reference and potentially registration information with LOLA; it is not an independently registered ground truth.

The reproducible `python -m scripts.validate_independent_delta <five raster paths> --output <report.json>` check uses a 250 m disk completely covered by valid LROC pixels, applies a per-tile median vertical shift against co-located 80 m DEM samples, then combines the local stereo horizon with the 80 m DEM horizon from just outside 250 m to 100 km. This is a **hybrid**, not a 100 km stereo horizon. Horizontal co-registration and its uncertainty were not independently corrected or assessed. Raster resolution, checksums, sampled IDs, offsets and per-site statistics are in [independent_delta_report.json](independent_delta_report.json). Four points present in overlapping tiles are counted only once. Each result contains 45 locations and 720 azimuths per location.

| Observer height | Hybrid minus 80 m horizon, signed P95 | Fraction of comparisons above 0.25 degrees |
| --- | ---: | ---: |
| 1 m | 1.532 degrees | 25.4% |
| 5 m | 0.785 degrees | 16.3% |
| 10 m | 0.465 degrees | 10.9% |

These results describe a geographically clustered sample and hybrid terrain
models. They do not establish 0.25 degrees as a global 95% uncertainty bound.

- `/health` returns 503 until all required artifact files and objective scores are loaded and validated. Analysis requests for a missing objective return 503; no synthetic scores are generated.
- Zero slope cap: the rule gives passed sites flatness 1.
- Required sunlight ratio zero: the sunlight requirement term is treated as satisfied (1); the input specification permits zero but does not define division by zero.
