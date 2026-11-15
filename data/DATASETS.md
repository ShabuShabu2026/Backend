# Lunar datasets

This inventory describes the local files checked on 2026-11-15. Paths are
relative to the repository root. File sizes and SHA-256 hashes identify the
local copies; they are not publisher-provided checksums. Data and generated
artifacts are excluded from Git and must be provisioned separately for deployment.

## Source datasets

| Dataset | Local path | Purpose | Source |
| --- | --- | --- | --- |
| LOLA 80 m DEM | `data/dem/LDEM_80S_80MPP_ADJ.TIF` | Elevation, terrain meshes and horizon masks | [NASA PGDA 90](https://pgda.gsfc.nasa.gov/products/90) |
| Illumination baseline | `data/baseline/AVGVISIB_85S_060M_201608.LBL` and `.IMG` | Sun visibility comparison | [MIT illumination data](https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/) |
| Earth visibility baseline | `data/baseline/AVGVISIB_85S_060M_201608_EARTH.LBL` and `.IMG` | Earth visibility comparison | [MIT illumination data](https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/) |
| Permanently shadowed regions | `data/psr/LPSR_80S_20MPP_ADJ.{SHP,SHX,DBF,PRJ}` | Polar volatile objective | [NASA PGDA 90](https://pgda.gsfc.nasa.gov/products/90) |
| PSR subset, larger than 1 km² | `data/psr/LPSR_80S_20MPP_ADJ_1km2.{SHP,SHX,DBF,PRJ}` | Additional reference; the full PSR layer is used for scoring | [NASA PGDA 90](https://pgda.gsfc.nasa.gov/products/90) |
| Slope | `data/terrain/LDSM_80S_80MPP_ADJ.TIF` | Slope constraints and flatness score | [NASA PGDA 90](https://pgda.gsfc.nasa.gov/products/90) |
| Roughness | `data/terrain/LDRM_80S_50MPP_ADJ_ROUGH_100M.TIF` | Roughness score; 50 m pixels and 100 m baseline | [NASA PGDA 90](https://pgda.gsfc.nasa.gov/products/90) |
| Four 5 m site DEMs | `data/site_dem/Site01/`, `Site04/`, `Site07/`, `Site11/` | High-resolution horizon comparison; not the base production DEM | [NASA PGDA 78](https://pgda.gsfc.nasa.gov/products/78) |
| Unified Geologic Map of the Moon GIS v2 | `data/geology/Unified_Geologic_Map_of_the_Moon_GIS_v2.zip` and extracted directory | Geological-unit diversity in objective scores | [USGS archive](https://asc-astropedia.s3.us-west-2.amazonaws.com/Moon/Geology/Unified_Geologic_Map_of_the_Moon_GIS_v2.zip) |
| Lunar crater catalogue | `data/craters/goransalamuniccar_mooncraters.zip` | Large-crater proximity in impact history score | [USGS catalogue](https://astrogeology.usgs.gov/search/map/moon_crater_database_v1_salamuni_car) |

## Raster metadata

Metadata below was read from the local files with Rasterio. Extents are
`(xmin, ymin, xmax, ymax)` in projected metres. All listed GeoTIFF files use
NaN nodata. The base DEM, slope and roughness use the same IAU Moon (2015)
spherical south polar stereographic CRS: radius 1,737,400 m, origin latitude
-90 degrees and central meridian 0 degrees.

| File | Shape (rows x columns) | Pixel size (m) | Extent (m) |
| --- | ---: | ---: | --- |
| `LDEM_80S_80MPP_ADJ.TIF` | 7,600 x 7,600 | 80 x 80 | (-304000, -304000, 304000, 304000) |
| `LDSM_80S_80MPP_ADJ.TIF` | 7,600 x 7,600 | 80 x 80 | (-304000, -304000, 304000, 304000) |
| `LDRM_80S_50MPP_ADJ_ROUGH_100M.TIF` | 12,160 x 12,160 | 50 x 50 | (-304000, -304000, 304000, 304000) |
| `Site01_final_adj_5mpp_surf.tif` | 3,200 x 3,200 | 5 x 5 | (-19000, -20000, -3000, -4000) |
| `Site04_final_adj_5mpp_surf.tif` | 3,200 x 3,200 | 5 x 5 | (-9000, -15000, 7000, 1000) |
| `Site07_final_adj_5mpp_surf.tif` | 3,200 x 3,200 | 5 x 5 | (22000, -28000, 38000, -12000) |
| `Site11_final_adj_5mpp_surf.tif` | 3,200 x 3,200 | 5 x 5 | (-45000, 7000, -29000, 23000) |

The site DEMs have an unnamed datum in their CRS metadata. Their projection
parameters and lunar sphere radius match the base DEM numerically, but formal
CRS equivalence and independent registration are not established.

The DEM and both baseline labels describe south polar stereographic projection
with the same central longitude, pole and sphere radius. Their grid resolutions,
extents and CRS descriptions differ; exact CRS equivalence is not established.
The baseline labels specify the DE421 mean Earth/polar axis frame.

## Vector data

The full PSR shapefile has 506,349 features and the 1 km² subset has 1,531,
as recorded by the earlier OGR inspection. Both use Moon2000 south polar
stereographic coordinates with a 1,737,400 m sphere. Their fields are `gid`,
`area_km2` and `name`.

The extracted geology archive contains the shapefile layers `Boundary_poly`,
`GeoContacts`, `GeoUnits`, `Labels_Global`, `Linear_Features`,
`Mercator_Clip` and `Polar_Stereographic_Clip`, as well as geodatabases.
The scoring code uses `Lunar_GIS/Shapefiles/GeoUnits.shp`: 12,247 polygons,
with unit codes in `FIRST_Unit`. The available OpenFileGDB driver could not
read the compressed geodatabases.

The crater archive contains
`GoranSalamuniccar_MoonCraters/LU78287GT_GIS/LU78287GT_Moon2000.shp`,
with 78,287 points and fields `Lon_E`, `Lat`, `p`, `Name`,
`Radius_deg` and `Radius_km`. It has no age field. The application uses
crater centres with `Radius_km >= 10` (diameter >= 20 km).

## Generated analysis artifacts

| File | Description |
| --- | --- |
| `artifacts/sky_table.npz` | JPL Horizons Sun and Earth positions and angular radii, hourly from 2026-01-01 00:00 to 2028-12-31 23:00 UTC, 26,304 rows, MOON_ME frame. Generated with `python -m scripts.fetch_sky_table` using the [JPL Horizons API](https://ssd.jpl.nasa.gov/api/horizons.api). |
| `artifacts/grid.npz` | Precomputed 1 km analysis grid and sampled terrain values. |
| `artifacts/horizon_1m.npy`, `horizon_5m.npy`, `horizon_10m.npy` | Horizon masks for the three observer heights; `horizon_manifest.json` records generation settings. |
| `artifacts/roughness_reference.npy`, `reference.json` | Normalization distributions and reference values. |
| `artifacts/objective_polar_volatiles.npy`, `objective_planetary_processes.npy`, `objective_impact_history.npy` | Precomputed objective scores from the source vector datasets. |
| `artifacts/delta_calibration.json` | 5 m site DEM horizon comparison report; the Earth visibility margin remains provisional. |

The local sky table is 1,574,003 bytes; SHA-256:
`bc0d925ce770770ccdae20b480f60e55429ac06b5b1b73bf7b349b8fdbf92ee5`.
Regenerated files can have different checksums. See
[`docs/DECISIONS.md`](../docs/DECISIONS.md) for validation methods and
scientific limitations.

## Local file sizes and SHA-256

The URL for each PGDA file is the base
`https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/` plus its filename. The 5 m
site files use `https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/<Site>/<filename>`.
The baseline files use
`https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/<filename>`.
The geology archive URL is linked above; the crater archive was downloaded
from the [USGS online file link](https://astrogeology.usgs.gov/ckan/dataset/144c1f05-de7f-4e45-aa6d-5ca04622bcb1/resource/fd47a9d8-046b-406c-b160-e416fd32f5fa/download/goransalamuniccar_mooncraters.zip).

| Local file | Bytes | SHA-256 |
| --- | ---: | --- |
| `dem/LDEM_80S_80MPP_ADJ.TIF` | 189,158,392 | `82030dcbdd7c4bb0c7d858e9b4b293b9f2cda5a543ba31ec0f42784bd6beee5a` |
| `baseline/AVGVISIB_85S_060M_201608.IMG` | 51,166,728 | `82dadf321dee28f1947c1fed81858d4cf50fe8eb2aa405aae114e8ab21c1efe1` |
| `baseline/AVGVISIB_85S_060M_201608.LBL` | 4,094 | `33decce957d5d4d9608557d8d969d1e1b94056a159b2563624ade4b528a0c917` |
| `baseline/AVGVISIB_85S_060M_201608_EARTH.IMG` | 51,166,728 | `0958313069d6039b2474c875ff662f28dbcba2bd853d9ea458aa807b7948c11f` |
| `baseline/AVGVISIB_85S_060M_201608_EARTH.LBL` | 4,111 | `45a61697d779fdb9170bca2553f9e0188aeda1159811d3531c348df8f57f68bd` |
| `psr/LPSR_80S_20MPP_ADJ.DBF` | 122,030,239 | `e0a2304ab2f02b63fbd9c6019643b93ddc9c2826619d1518521a104d47a7aa00` |
| `psr/LPSR_80S_20MPP_ADJ.PRJ` | 368 | `793b80952f23fbff90f48f9e13868b6b7fc5dc07ba0b1633b124c3db52462854` |
| `psr/LPSR_80S_20MPP_ADJ.SHP` | 161,396,036 | `fe11dbc98b4054ff2f72510955b33f775f6f5b8e0a6f5ac4a03dfd8de5625606` |
| `psr/LPSR_80S_20MPP_ADJ.SHX` | 4,050,892 | `dc9e84bb280793c69ed5e4fca7422f798111efb3d629a2430804e2559aba73af` |
| `psr/LPSR_80S_20MPP_ADJ_1km2.DBF` | 369,101 | `23c3e3a01cde8d8c2114196f7430c46c24505c1a6e75fcdb522670d8efcc62da` |
| `psr/LPSR_80S_20MPP_ADJ_1km2.PRJ` | 368 | `793b80952f23fbff90f48f9e13868b6b7fc5dc07ba0b1633b124c3db52462854` |
| `psr/LPSR_80S_20MPP_ADJ_1km2.SHP` | 20,743,300 | `39a9906545188ea4d9b844d34f946de7a6721993f778076d85778650cbbfb741` |
| `psr/LPSR_80S_20MPP_ADJ_1km2.SHX` | 12,348 | `3bc10378025d62ded5805e2eebe4c016e461a8c6fe661f15367e4019f2b85827` |
| `terrain/LDSM_80S_80MPP_ADJ.TIF` | 241,594,035 | `d1270c4a69d01a8e4eb5503bd25713f0b2251dbb4ffee6c3161ef7a792c8f059` |
| `terrain/LDRM_80S_50MPP_ADJ_ROUGH_100M.TIF` | 645,351,631 | `ba1fb29c8d7ddf14a57d8a328098ccca49024c95a14dca251f9ca7c2ba33d6ea` |
| `site_dem/Site01/Site01_final_adj_5mpp_surf.tif` | 40,980,810 | `3ba7b97cb00a2bcf21189c3aeb535f65afc21207154ab9f0d43c5bdc1f7e747e` |
| `site_dem/Site04/Site04_final_adj_5mpp_surf.tif` | 40,980,806 | `38ff70dbdf2f066c2cfa94a646c3a59d653ce7f6b4528b15fc1b43ee397ce758` |
| `site_dem/Site07/Site07_final_adj_5mpp_surf.tif` | 40,980,808 | `38aaee10bb4da4d63e7427aa1ca25c79bdbc649d212079a04990e135462091f8` |
| `site_dem/Site11/Site11_final_adj_5mpp_surf.tif` | 40,980,806 | `58f3372c35bbd6baf38ffd5633c1c96b59bd89dbd252150581d12893a43136e5` |
| `geology/Unified_Geologic_Map_of_the_Moon_GIS_v2.zip` | 224,413,040 | `f3ec29803c1ad3b8c41a7fff3e9339bd66f9fbb8f63e30f13c52561b8d5559a1` |
| `craters/goransalamuniccar_mooncraters.zip` | 26,224,618 | `b9ac25611f3dc8f7e8ccb2b6488d4451476439ab05164b006996b0f345ab21b3` |

## Missing files

- None of the requested files that were to be downloaded are currently missing.

## Not downloaded due to size

- [LDSM_80S_20MPP_ADJ.TIF](https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDSM_80S_20MPP_ADJ.TIF): 3,778,056,355 bytes, above the requested 3 GB limit.

## Network errors

- The roughness download was interrupted during the original attempt, but was
  subsequently completed and verified. No outstanding network errors are recorded.
