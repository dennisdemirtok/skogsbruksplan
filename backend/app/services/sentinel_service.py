"""Sentinel-2 satellite analysis service.

Provides NDVI calculation, change detection, and forest health monitoring
using Sentinel-2 Level-2A imagery from Earth Search AWS STAC catalog.

Key features:
  - Search for cloud-free Sentinel-2 scenes over a property
  - Calculate NDVI (Normalized Difference Vegetation Index)
  - Detect changes between two dates (storm damage, bark beetle, harvest)
  - Generate per-stand health statistics

Data source:
  Earth Search (Element84) — mirrors ESA Sentinel-2 on AWS S3.
  Free access, no authentication required. COG format (Cloud Optimized GeoTIFF).
  STAC endpoint: https://earth-search.aws.element84.com/v1
  Collection: sentinel-2-l2a
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from pyproj import Transformer
from shapely.geometry import shape, mapping, box
from shapely.ops import transform

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────

STAC_API_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"

# Sentinel-2 band names in Earth Search STAC
BAND_RED = "red"       # B04 (10m)
BAND_NIR = "nir"       # B08 (10m)
BAND_SWIR = "swir16"   # B11 (20m) — for NBR (burn/damage index)
BAND_GREEN = "green"   # B03 (10m)
BAND_SCL = "scl"       # Scene Classification Layer (20m)

# SCL classes to mask out (clouds, shadows, water, snow)
SCL_MASK_VALUES = {0, 1, 2, 3, 6, 8, 9, 10, 11}  # keep 4=vegetation, 5=bare soil, 7=low cloud probability

# NDVI thresholds for forest health classification
NDVI_CLASSES = {
    "dead_or_cleared": (-1.0, 0.15),
    "stressed": (0.15, 0.35),
    "moderate": (0.35, 0.55),
    "healthy": (0.55, 0.75),
    "very_healthy": (0.75, 1.0),
}

# Change detection thresholds
CHANGE_THRESHOLD_MAJOR = -0.15   # NDVI drop > 0.15 = major change (clearcut, storm)
CHANGE_THRESHOLD_MINOR = -0.08   # NDVI drop > 0.08 = minor change (thinning, stress)

# CRS transformers (SWEREF99 TM → WGS84 for STAC search)
_transformer_3006_to_4326 = Transformer.from_crs("EPSG:3006", "EPSG:4326", always_xy=True)
_transformer_4326_to_3006 = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True)

MAX_CLOUD_COVER = 20  # percent
STAC_TIMEOUT = 30.0


class SentinelService:
    """Service for Sentinel-2 satellite data analysis."""

    def __init__(self):
        self.stac_url = STAC_API_URL
        self.collection = COLLECTION

    # ── STAC Scene Search ────────────────────────────────────────

    async def search_scenes(
        self,
        bbox_3006: tuple[float, float, float, float],
        date_from: date,
        date_to: date,
        max_cloud_pct: int = MAX_CLOUD_COVER,
        limit: int = 10,
    ) -> list[dict]:
        """Search for Sentinel-2 scenes covering a bounding box.

        Args:
            bbox_3006: Bounding box in SWEREF99 TM (minx, miny, maxx, maxy)
            date_from: Start date for search
            date_to: End date for search
            max_cloud_pct: Maximum cloud cover percentage
            limit: Max number of results

        Returns:
            List of scene metadata dicts sorted by date (newest first)
        """
        # Transform bbox from SWEREF99 TM to WGS84
        minx, miny = _transformer_3006_to_4326.transform(bbox_3006[0], bbox_3006[1])
        maxx, maxy = _transformer_3006_to_4326.transform(bbox_3006[2], bbox_3006[3])
        bbox_4326 = [minx, miny, maxx, maxy]

        # STAC API search request
        # Note: Earth Search v1 doesn't support the `query` extension
        # for cloud cover filtering, so we fetch more results and filter client-side.
        fetch_limit = min(limit * 4, 50)  # fetch extra to filter
        search_body = {
            "collections": [self.collection],
            "bbox": bbox_4326,
            "datetime": f"{date_from.isoformat()}T00:00:00Z/{date_to.isoformat()}T23:59:59Z",
            "limit": fetch_limit,
        }

        try:
            async with httpx.AsyncClient(timeout=STAC_TIMEOUT) as client:
                resp = await client.post(
                    f"{self.stac_url}/search",
                    json=search_body,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error(f"STAC search failed: {exc}")
            return []

        # Filter by cloud cover client-side and sort by date descending
        features = data.get("features", [])
        features = [
            f for f in features
            if f.get("properties", {}).get("eo:cloud_cover", 100) <= max_cloud_pct
        ]
        features.sort(
            key=lambda f: f.get("properties", {}).get("datetime", ""),
            reverse=True,
        )
        features = features[:limit]

        scenes = []
        for feature in features:
            props = feature.get("properties", {})
            assets = feature.get("assets", {})

            scenes.append({
                "id": feature.get("id", ""),
                "datetime": props.get("datetime", ""),
                "cloud_cover": props.get("eo:cloud_cover", 0),
                "platform": props.get("platform", ""),
                "tile_id": props.get("s2:mgrs_tile", props.get("grid:code", "")),
                "bands": {
                    "red": assets.get(BAND_RED, {}).get("href"),
                    "nir": assets.get(BAND_NIR, {}).get("href"),
                    "green": assets.get(BAND_GREEN, {}).get("href"),
                    "swir16": assets.get(BAND_SWIR, {}).get("href"),
                    "scl": assets.get(BAND_SCL, {}).get("href"),
                },
                "thumbnail": assets.get("thumbnail", {}).get("href"),
            })

        return scenes

    # ── NDVI Calculation ─────────────────────────────────────────

    async def calculate_ndvi(
        self,
        scene: dict,
        geometry_3006: dict,
    ) -> dict:
        """Calculate NDVI for a geometry from a Sentinel-2 scene.

        Args:
            scene: Scene metadata dict from search_scenes()
            geometry_3006: GeoJSON geometry in SWEREF99 TM

        Returns:
            Dict with NDVI statistics and pixel-level classification
        """
        red_url = scene["bands"].get("red")
        nir_url = scene["bands"].get("nir")
        scl_url = scene["bands"].get("scl")

        if not red_url or not nir_url:
            return {"error": "Scene missing required bands (red, nir)"}

        # Transform geometry to WGS84 for reading COG
        geom_shape = shape(geometry_3006)
        geom_4326 = transform(_transformer_3006_to_4326.transform, geom_shape)
        bounds = geom_4326.bounds  # minx, miny, maxx, maxy

        try:
            # Read Red band (B04)
            red_data = self._read_band_window(red_url, bounds)
            # Read NIR band (B08)
            nir_data = self._read_band_window(nir_url, bounds)

            if red_data is None or nir_data is None:
                return {"error": "Failed to read satellite bands"}

            # Ensure same shape (NIR and Red are both 10m, should match)
            min_h = min(red_data.shape[0], nir_data.shape[0])
            min_w = min(red_data.shape[1], nir_data.shape[1])
            red_data = red_data[:min_h, :min_w].astype(np.float32)
            nir_data = nir_data[:min_h, :min_w].astype(np.float32)

            # Read SCL for cloud masking (if available)
            valid_mask = np.ones_like(red_data, dtype=bool)
            if scl_url:
                scl_data = self._read_band_window(scl_url, bounds)
                if scl_data is not None:
                    # Resample SCL to match 10m resolution (SCL is 20m)
                    from scipy.ndimage import zoom
                    scale_h = red_data.shape[0] / scl_data.shape[0]
                    scale_w = red_data.shape[1] / scl_data.shape[1]
                    scl_resampled = zoom(scl_data, (scale_h, scale_w), order=0)
                    scl_resampled = scl_resampled[:min_h, :min_w]
                    valid_mask = ~np.isin(scl_resampled, list(SCL_MASK_VALUES))

            # Calculate NDVI
            denominator = nir_data + red_data
            ndvi = np.where(
                (denominator > 0) & valid_mask,
                (nir_data - red_data) / denominator,
                np.nan,
            )

            # Filter out no-data
            ndvi_valid = ndvi[~np.isnan(ndvi)]

            if len(ndvi_valid) == 0:
                return {
                    "scene_id": scene["id"],
                    "datetime": scene["datetime"],
                    "error": "No valid pixels (fully cloud-covered)",
                    "valid_pixel_count": 0,
                }

            # Classify pixels
            classification = {}
            for class_name, (low, high) in NDVI_CLASSES.items():
                count = int(np.sum((ndvi_valid >= low) & (ndvi_valid < high)))
                pct = round(count / len(ndvi_valid) * 100, 1)
                classification[class_name] = {"count": count, "pct": pct}

            return {
                "scene_id": scene["id"],
                "datetime": scene["datetime"],
                "cloud_cover_pct": scene.get("cloud_cover", 0),
                "valid_pixel_count": int(len(ndvi_valid)),
                "total_pixel_count": int(ndvi.size),
                "cloud_masked_pct": round(
                    (1 - len(ndvi_valid) / max(ndvi.size, 1)) * 100, 1
                ),
                "ndvi_mean": round(float(np.mean(ndvi_valid)), 4),
                "ndvi_median": round(float(np.median(ndvi_valid)), 4),
                "ndvi_min": round(float(np.min(ndvi_valid)), 4),
                "ndvi_max": round(float(np.max(ndvi_valid)), 4),
                "ndvi_std": round(float(np.std(ndvi_valid)), 4),
                "classification": classification,
                "health_score": self._health_score(ndvi_valid),
            }

        except Exception as exc:
            logger.error(f"NDVI calculation failed: {exc}", exc_info=True)
            return {"error": f"NDVI calculation failed: {str(exc)}"}

    # ── Change Detection ─────────────────────────────────────────

    async def detect_changes(
        self,
        scene_before: dict,
        scene_after: dict,
        geometry_3006: dict,
    ) -> dict:
        """Detect changes between two scenes for a geometry.

        Compares NDVI between two dates to identify:
        - Clear cuts (major NDVI decrease)
        - Storm damage (major NDVI decrease)
        - Thinning (minor NDVI decrease)
        - Growth (NDVI increase)

        Returns change statistics and classification.
        """
        ndvi_before = await self.calculate_ndvi(scene_before, geometry_3006)
        ndvi_after = await self.calculate_ndvi(scene_after, geometry_3006)

        if "error" in ndvi_before or "error" in ndvi_after:
            return {
                "error": "Cannot compare — one or both scenes have errors",
                "before": ndvi_before,
                "after": ndvi_after,
            }

        ndvi_change = ndvi_after["ndvi_mean"] - ndvi_before["ndvi_mean"]

        # Classify the change
        if ndvi_change <= CHANGE_THRESHOLD_MAJOR:
            change_type = "major_decrease"
            change_label = "Stor förändring (avverkning/stormskada)"
            severity = "critical"
        elif ndvi_change <= CHANGE_THRESHOLD_MINOR:
            change_type = "minor_decrease"
            change_label = "Måttlig förändring (gallring/stress)"
            severity = "warning"
        elif ndvi_change >= 0.05:
            change_type = "increase"
            change_label = "Positiv förändring (tillväxt/återhämtning)"
            severity = "success"
        else:
            change_type = "stable"
            change_label = "Stabil (ingen signifikant förändring)"
            severity = "info"

        return {
            "date_before": ndvi_before["datetime"],
            "date_after": ndvi_after["datetime"],
            "ndvi_before": ndvi_before["ndvi_mean"],
            "ndvi_after": ndvi_after["ndvi_mean"],
            "ndvi_change": round(ndvi_change, 4),
            "change_pct": round(
                ndvi_change / max(abs(ndvi_before["ndvi_mean"]), 0.01) * 100, 1
            ),
            "change_type": change_type,
            "change_label": change_label,
            "severity": severity,
            "health_before": ndvi_before["health_score"],
            "health_after": ndvi_after["health_score"],
            "classification_before": ndvi_before["classification"],
            "classification_after": ndvi_after["classification"],
        }

    # ── Property-level Analysis ──────────────────────────────────

    async def analyze_property_health(
        self,
        property_bbox_3006: tuple[float, float, float, float],
        stand_geometries_3006: list[dict],
        stand_ids: list[int],
        reference_months_back: int = 6,
    ) -> dict:
        """Full property health analysis with change detection.

        Searches for latest + reference scenes, calculates NDVI per stand,
        and runs change detection to identify problem areas.

        Args:
            property_bbox_3006: Property bounding box in SWEREF99 TM
            stand_geometries_3006: List of stand GeoJSON geometries (EPSG:3006)
            stand_ids: List of stand numbers (matching geometries)
            reference_months_back: How many months back for the reference scene

        Returns:
            Comprehensive health analysis dict
        """
        today = date.today()

        # Search for recent scenes (last 60 days)
        recent_scenes = await self.search_scenes(
            bbox_3006=property_bbox_3006,
            date_from=today - timedelta(days=60),
            date_to=today,
            max_cloud_pct=MAX_CLOUD_COVER,
            limit=5,
        )

        # Search for reference scenes (same period last year or N months back)
        ref_date = today - timedelta(days=reference_months_back * 30)
        reference_scenes = await self.search_scenes(
            bbox_3006=property_bbox_3006,
            date_from=ref_date - timedelta(days=30),
            date_to=ref_date + timedelta(days=30),
            max_cloud_pct=MAX_CLOUD_COVER,
            limit=3,
        )

        if not recent_scenes:
            return {
                "status": "no_recent_data",
                "message": "Inga molnfria Sentinel-2-scener hittades senaste 60 dagarna.",
                "scenes_searched": 0,
            }

        latest_scene = recent_scenes[0]
        ref_scene = reference_scenes[0] if reference_scenes else None

        # Calculate NDVI per stand
        stand_results = []
        for geom, stand_num in zip(stand_geometries_3006, stand_ids):
            ndvi_result = await self.calculate_ndvi(latest_scene, geom)
            ndvi_result["stand_number"] = stand_num

            # Change detection if reference scene available
            if ref_scene:
                change = await self.detect_changes(ref_scene, latest_scene, geom)
                ndvi_result["change"] = change
            else:
                ndvi_result["change"] = None

            stand_results.append(ndvi_result)

        # Identify problem stands
        problem_stands = []
        for sr in stand_results:
            if "error" in sr:
                continue
            if sr.get("health_score", 100) < 50:
                problem_stands.append({
                    "stand_number": sr["stand_number"],
                    "health_score": sr["health_score"],
                    "ndvi_mean": sr["ndvi_mean"],
                    "issue": "low_ndvi",
                })
            change = sr.get("change")
            if change and change.get("severity") in ("critical", "warning"):
                problem_stands.append({
                    "stand_number": sr["stand_number"],
                    "change_type": change["change_type"],
                    "ndvi_change": change["ndvi_change"],
                    "issue": "negative_change",
                })

        # Overall property health
        valid_scores = [
            sr["health_score"]
            for sr in stand_results
            if "health_score" in sr
        ]
        overall_health = round(np.mean(valid_scores), 1) if valid_scores else None

        return {
            "status": "ok",
            "analysis_date": today.isoformat(),
            "latest_scene": {
                "id": latest_scene["id"],
                "datetime": latest_scene["datetime"],
                "cloud_cover": latest_scene["cloud_cover"],
                "thumbnail": latest_scene.get("thumbnail"),
            },
            "reference_scene": {
                "id": ref_scene["id"],
                "datetime": ref_scene["datetime"],
                "cloud_cover": ref_scene["cloud_cover"],
            } if ref_scene else None,
            "overall_health_score": overall_health,
            "stand_count_analyzed": len(stand_results),
            "problem_stands": problem_stands,
            "stand_results": stand_results,
            "scenes_available": len(recent_scenes),
        }

    # ── Private Helpers ──────────────────────────────────────────

    def _read_band_window(
        self,
        url: str,
        bounds_4326: tuple[float, float, float, float],
    ) -> Optional[np.ndarray]:
        """Read a window from a Cloud Optimized GeoTIFF via HTTP.

        Uses rasterio's virtual filesystem (/vsicurl/) to read only
        the pixels we need, without downloading the full tile.
        """
        try:
            env = rasterio.Env(
                GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
                GDAL_HTTP_MULTIPLEX="YES",
                GDAL_HTTP_VERSION=2,
                VSI_CACHE=True,
                VSI_CACHE_SIZE=5000000,
            )

            with env:
                with rasterio.open(url) as src:
                    # Transform bounds to the raster's CRS
                    src_crs = src.crs
                    if src_crs.to_epsg() != 4326:
                        t = Transformer.from_crs("EPSG:4326", src_crs, always_xy=True)
                        minx, miny = t.transform(bounds_4326[0], bounds_4326[1])
                        maxx, maxy = t.transform(bounds_4326[2], bounds_4326[3])
                    else:
                        minx, miny, maxx, maxy = bounds_4326

                    # Get the window for our bounds
                    window = from_bounds(minx, miny, maxx, maxy, src.transform)

                    # Read the data
                    data = src.read(1, window=window)

                    return data

        except Exception as exc:
            logger.error(f"Failed to read band from {url[:80]}...: {exc}")
            return None

    def _health_score(self, ndvi_values: np.ndarray) -> int:
        """Calculate a 0-100 health score from NDVI values.

        Scoring:
          - NDVI > 0.7 → excellent (100)
          - NDVI 0.5-0.7 → good (70-90)
          - NDVI 0.3-0.5 → moderate (40-70)
          - NDVI < 0.3 → poor (0-40)
        """
        if len(ndvi_values) == 0:
            return 0

        mean_ndvi = float(np.mean(ndvi_values))

        if mean_ndvi >= 0.7:
            return min(100, int(70 + (mean_ndvi - 0.7) * 100))
        elif mean_ndvi >= 0.5:
            return int(50 + (mean_ndvi - 0.5) * 100)
        elif mean_ndvi >= 0.3:
            return int(25 + (mean_ndvi - 0.3) * 125)
        else:
            return max(0, int(mean_ndvi * 83))
