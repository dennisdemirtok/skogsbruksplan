import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
import rasterio
from rasterio.mask import mask as rasterio_mask
from shapely import wkt as shapely_wkt
from shapely.geometry import mapping, shape

logger = logging.getLogger(__name__)

RASTER_FILE_MAP = {
    "volume": "volume_m3_per_ha.tif",
    "height": "mean_height_m.tif",
    "basal_area": "basal_area_m2.tif",
    "diameter": "mean_diameter_cm.tif",
    "age": "age_years.tif",
    "site_index": "site_index.tif",
    "pine": "pine_pct.tif",
    "spruce": "spruce_pct.tif",
    "deciduous": "deciduous_pct.tif",
    "contorta": "contorta_pct.tif",
}


class RasterService:
    def __init__(self, raster_base_path: str = "/data/rasters"):
        self.raster_base_path = Path(raster_base_path)

    def load_raster(self, path: str) -> rasterio.DatasetReader:
        raster_path = Path(path)
        if not raster_path.exists():
            raise FileNotFoundError(f"Rasterfilen hittades inte: {path}")
        return rasterio.open(raster_path)

    def zonal_statistics(
        self, geometry_wkt: str, raster_path: str
    ) -> dict[str, Optional[float]]:
        geom = shapely_wkt.loads(geometry_wkt)
        geom_geojson = mapping(geom)

        raster_file = Path(raster_path)
        if not raster_file.exists():
            logger.warning(f"Raster file not found: {raster_path}")
            return {"mean": None, "min": None, "max": None, "std": None, "count": 0}

        try:
            with rasterio.open(raster_file) as src:
                raster_crs = src.crs
                if raster_crs and raster_crs.to_epsg() != 3006:
                    from pyproj import Transformer
                    from shapely.ops import transform

                    transformer = Transformer.from_crs(
                        "EPSG:3006", raster_crs, always_xy=True
                    )
                    geom = transform(transformer.transform, geom)
                    geom_geojson = mapping(geom)

                raster_bounds = src.bounds
                geom_bounds = geom.bounds
                if (
                    geom_bounds[0] > raster_bounds[2]
                    or geom_bounds[2] < raster_bounds[0]
                    or geom_bounds[1] > raster_bounds[3]
                    or geom_bounds[3] < raster_bounds[1]
                ):
                    logger.warning(
                        f"Geometry is outside raster bounds for {raster_path}"
                    )
                    return {
                        "mean": None,
                        "min": None,
                        "max": None,
                        "std": None,
                        "count": 0,
                    }

                out_image, out_transform = rasterio_mask(
                    src, [geom_geojson], crop=True, nodata=src.nodata
                )

                data = out_image[0]

                nodata_value = src.nodata
                if nodata_value is not None:
                    valid_mask = ~np.isclose(data, nodata_value)
                else:
                    valid_mask = ~np.isnan(data.astype(float))

                valid_data = data[valid_mask]

                if len(valid_data) == 0:
                    return {
                        "mean": None,
                        "min": None,
                        "max": None,
                        "std": None,
                        "count": 0,
                    }

                return {
                    "mean": round(float(np.mean(valid_data)), 2),
                    "min": round(float(np.min(valid_data)), 2),
                    "max": round(float(np.max(valid_data)), 2),
                    "std": round(float(np.std(valid_data)), 2),
                    "count": int(len(valid_data)),
                }

        except rasterio.errors.RasterioError as e:
            logger.error(f"Rasterio error processing {raster_path}: {e}")
            return {"mean": None, "min": None, "max": None, "std": None, "count": 0}
        except Exception as e:
            logger.error(f"Error processing raster {raster_path}: {e}")
            return {"mean": None, "min": None, "max": None, "std": None, "count": 0}

    def get_stand_data_from_rasters(
        self, geometry_wkt: str, raster_dir: str
    ) -> Optional[dict[str, Optional[float]]]:
        raster_base = Path(raster_dir)

        # Graceful fallback: return None if raster directory is missing or has no .tif files
        if not raster_base.exists() or not raster_base.is_dir():
            logger.warning(
                f"Raster directory does not exist: {raster_dir}. "
                "Skipping raster-based stand data extraction."
            )
            return None

        tif_files = list(raster_base.glob("*.tif"))
        if not tif_files:
            logger.warning(
                f"No .tif files found in raster directory: {raster_dir}. "
                "Skipping raster-based stand data extraction."
            )
            return None

        result: dict[str, Optional[float]] = {}

        attribute_to_raster = {
            "volume_m3_per_ha": "volume",
            "mean_height_m": "height",
            "basal_area_m2": "basal_area",
            "mean_diameter_cm": "diameter",
            "age_years": "age",
            "site_index": "site_index",
            "pine_pct": "pine",
            "spruce_pct": "spruce",
            "deciduous_pct": "deciduous",
            "contorta_pct": "contorta",
        }

        for attr_name, raster_key in attribute_to_raster.items():
            raster_filename = RASTER_FILE_MAP.get(raster_key)
            if not raster_filename:
                result[attr_name] = None
                continue

            raster_path = raster_base / raster_filename
            if not raster_path.exists():
                logger.debug(f"Raster file not found: {raster_path}")
                result[attr_name] = None
                continue

            stats = self.zonal_statistics(geometry_wkt, str(raster_path))

            if stats["mean"] is not None:
                if attr_name == "age_years":
                    result[attr_name] = round(stats["mean"])
                elif attr_name in ("pine_pct", "spruce_pct", "deciduous_pct", "contorta_pct"):
                    result[attr_name] = round(max(0, min(100, stats["mean"])), 1)
                else:
                    result[attr_name] = round(stats["mean"], 1)
            else:
                result[attr_name] = None

        species_total = sum(
            result.get(k, 0) or 0
            for k in ("pine_pct", "spruce_pct", "deciduous_pct", "contorta_pct")
        )
        if species_total > 0 and species_total != 100:
            scale_factor = 100.0 / species_total
            for k in ("pine_pct", "spruce_pct", "deciduous_pct", "contorta_pct"):
                if result.get(k) is not None:
                    result[k] = round(result[k] * scale_factor, 1)

        return result
