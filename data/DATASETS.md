# Data used by the lunar landing site analysis

The backend combines lunar terrain, permanently shadowed regions, geological
maps, crater locations, and Sun and Earth positions to evaluate landing sites.
Source files are stored under `data/`; precomputed analysis files are stored
under `artifacts/`.

## Terrain and visibility

### LOLA digital elevation model

- **Source:** [NASA PGDA 90 - Lunar South Pole Topography](https://pgda.gsfc.nasa.gov/products/90)
- **File:** `data/dem/LDEM_80S_80MPP_ADJ.TIF`
- **Resolution:** 80 m per pixel
- **Use:** The elevation model provides the terrain grid, the 3D terrain API,
  and the horizon masks used to determine whether terrain blocks the Sun or
  Earth. Refined site analyses also sample this DEM.

The DEM uses a south polar stereographic projection with a lunar sphere radius
of 1,737,400 m. Its elevation values are treated as relative to that reference
sphere.

### Slope and roughness

- **Source:** [NASA PGDA 90](https://pgda.gsfc.nasa.gov/products/90)
- **Slope:** `data/terrain/LDSM_80S_80MPP_ADJ.TIF`, 80 m per pixel
- **Roughness:** `data/terrain/LDRM_80S_50MPP_ADJ_ROUGH_100M.TIF`, 50 m per
  pixel with a 100 m roughness baseline
- **Use:** Slope is used for the slope constraint and flatness score.
  Roughness is used for the roughness score. Both rasters are sampled for the
  base grid and for refined sites.

### Sun and Earth positions

- **Source:** [NASA JPL Horizons API](https://ssd.jpl.nasa.gov/api/horizons.api)
- **Generated file:** `artifacts/sky_table.npz`
- **Coverage:** Hourly from 2026-01-01 00:00 through 2028-12-31 23:00 UTC
- **Use:** The table stores Sun and Earth positions and angular radii in the
  Moon-fixed `MOON_ME` frame. The backend combines them with a site's horizon
  mask to calculate directions, visibility and time-based scores.

The table is generated with `python -m scripts.fetch_sky_table`. The complete
requested stay and landing-date search window must fit within its coverage.

## Mission objectives

### Permanently shadowed regions

- **Source:** [NASA PGDA 90](https://pgda.gsfc.nasa.gov/products/90)
- **Files:** `data/psr/LPSR_80S_20MPP_ADJ.SHP` and its `.SHX`, `.DBF`
  and `.PRJ` companions
- **Use:** The `POLAR_VOLATILES` objective scores sites by their distance to
  the nearest permanently shadowed region. The full layer contains 506,349
  features.

A separate `LPSR_80S_20MPP_ADJ_1km2` subset is also present for reference;
the scoring calculation uses the full layer.

### Geological units

- **Source:** [USGS Unified Geologic Map of the Moon GIS v2](https://asc-astropedia.s3.us-west-2.amazonaws.com/Moon/Geology/Unified_Geologic_Map_of_the_Moon_GIS_v2.zip)
- **File:** `data/geology/Unified_Geologic_Map_of_the_Moon_GIS/Lunar_GIS/Shapefiles/GeoUnits.shp`
  and its shapefile companions
- **Use:** The `PLANETARY_PROCESSES` score uses the number of distinct
  geological unit codes within 20 km of a site. The geology contribution is
  also used in `IMPACT_HISTORY`.

The preprocessing clips the global map to the lunar south polar region before
reprojecting it to the DEM CRS. Unit codes come from `FIRST_Unit`.

### Lunar crater catalogue

- **Source:** [USGS Moon Crater Database v1](https://astrogeology.usgs.gov/search/map/moon_crater_database_v1_salamuni_car)
- **File:** `data/craters/goransalamuniccar_mooncraters.zip`
- **Use:** The `IMPACT_HISTORY` score combines the geological-unit score with
  proximity to the centre of a crater at least 20 km in diameter.

The catalogue includes crater position and radius fields; it has no age field.

## Validation datasets

### Sun and Earth visibility baselines

- **Source:** [MIT lunar illumination products](https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/)
- **Files:** `data/baseline/AVGVISIB_85S_060M_201608.LBL` and `.IMG`,
  plus `AVGVISIB_85S_060M_201608_EARTH.LBL` and `.IMG`
- **Use:** These baseline products are used to compare precomputed
  horizon-based Sun and Earth visibility against reference maps. They are
  validation inputs, not the hourly position table used for each analysis.

### High-resolution site DEMs

- **Source:** [NASA PGDA 78](https://pgda.gsfc.nasa.gov/products/78)
- **Files:** 5 m DEMs in `data/site_dem/Site01/`, `Site04/`, `Site07/`
  and `Site11/`
- **Use:** These tiles were compared with the 80 m DEM to assess sensitivity
  of horizon estimates to terrain resolution. They do not replace the 80 m DEM
  in the production analysis.

See [`docs/DECISIONS.md`](../docs/DECISIONS.md) for the comparison method and
results. The Earth visibility margin is provisional.

## Precomputed analysis files

The backend uses the source datasets to prepare:

| Artifact | Purpose |
| --- | --- |
| `artifacts/grid.npz` | Base grid and sampled elevation, slope and roughness |
| `artifacts/horizon_1m.npy`, `horizon_5m.npy`, `horizon_10m.npy` | Terrain horizon masks for the supported observer heights |
| `artifacts/sky_table.npz` | Hourly Sun and Earth positions and angular radii |
| `artifacts/roughness_reference.npy`, `reference.json` | Reference distributions and normalization values |
| `artifacts/objective_*.npy` | Precomputed objective scores |

The application reads these artifacts at startup and uses the source data for
operations such as terrain retrieval and refined site analysis. The datasets
and generated artifacts are excluded from Git and must be provided separately
to each environment.
