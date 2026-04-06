"""Sentinel-2 satellite analysis API routes.

Endpoints:
  GET /satellite/scenes/{property_id}       — Search available Sentinel-2 scenes
  GET /satellite/health/{property_id}       — Full property health analysis (NDVI + change detection)
  GET /satellite/ndvi/{property_id}         — Latest NDVI statistics per stand
"""

import json
import uuid
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis_client import cache_get, cache_set
from app.core.security import get_current_user
from app.models.property import Property
from app.models.stand import Stand
from app.models.user import User
from app.services.sentinel_service import SentinelService

router = APIRouter(prefix="/satellite", tags=["satellite"])

# Service singleton
_sentinel = SentinelService()

SCENES_CACHE_TTL = 3600       # 1 hour
HEALTH_CACHE_TTL = 7200       # 2 hours (satellite data updates slowly)
NDVI_CACHE_TTL = 7200         # 2 hours


# ── Response schemas ──────────────────────────────────────────

class SceneBands(BaseModel):
    red: Optional[str] = None
    nir: Optional[str] = None
    green: Optional[str] = None
    swir16: Optional[str] = None
    scl: Optional[str] = None


class SceneInfo(BaseModel):
    id: str
    datetime: str
    cloud_cover: float
    platform: str
    tile_id: str
    thumbnail: Optional[str] = None


class ScenesResponse(BaseModel):
    property_id: str
    scenes_found: int
    search_from: str
    search_to: str
    scenes: list[SceneInfo]


class NdviClassification(BaseModel):
    dead_or_cleared: Optional[dict] = None
    stressed: Optional[dict] = None
    moderate: Optional[dict] = None
    healthy: Optional[dict] = None
    very_healthy: Optional[dict] = None


class StandNdvi(BaseModel):
    stand_number: int
    ndvi_mean: Optional[float] = None
    ndvi_median: Optional[float] = None
    ndvi_min: Optional[float] = None
    ndvi_max: Optional[float] = None
    health_score: Optional[int] = None
    valid_pixel_count: Optional[int] = None
    classification: Optional[dict] = None
    error: Optional[str] = None


class ChangeInfo(BaseModel):
    ndvi_before: Optional[float] = None
    ndvi_after: Optional[float] = None
    ndvi_change: Optional[float] = None
    change_pct: Optional[float] = None
    change_type: Optional[str] = None
    change_label: Optional[str] = None
    severity: Optional[str] = None


class StandHealth(BaseModel):
    stand_number: int
    ndvi_mean: Optional[float] = None
    health_score: Optional[int] = None
    change: Optional[ChangeInfo] = None
    error: Optional[str] = None


class ProblemStand(BaseModel):
    stand_number: int
    issue: str
    health_score: Optional[int] = None
    ndvi_mean: Optional[float] = None
    ndvi_change: Optional[float] = None
    change_type: Optional[str] = None


class HealthAnalysisResponse(BaseModel):
    property_id: str
    status: str
    message: Optional[str] = None
    analysis_date: Optional[str] = None
    latest_scene: Optional[SceneInfo] = None
    reference_scene: Optional[SceneInfo] = None
    overall_health_score: Optional[float] = None
    stand_count_analyzed: int = 0
    problem_stands: list[ProblemStand] = []
    stand_results: list[StandHealth] = []
    scenes_available: int = 0


class NdviResponse(BaseModel):
    property_id: str
    scene_date: Optional[str] = None
    scene_id: Optional[str] = None
    cloud_cover: Optional[float] = None
    stands: list[StandNdvi] = []
    overall_ndvi_mean: Optional[float] = None
    overall_health_score: Optional[int] = None


# ── Helpers ───────────────────────────────────────────────────

async def _get_property_with_auth(
    property_id: uuid.UUID, db: AsyncSession, current_user: User
) -> Property:
    """Load property and verify ownership."""
    result = await db.execute(
        select(Property).where(Property.id == property_id)
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fastigheten hittades inte",
        )
    if prop.owner_id != current_user.id and prop.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Åtkomst nekad",
        )
    return prop


async def _get_property_bbox(
    prop: Property, db: AsyncSession
) -> Optional[tuple[float, float, float, float]]:
    """Get property bounding box in SWEREF99 TM (EPSG:3006).

    Returns (minx, miny, maxx, maxy) or None if no geometry.
    """
    if prop.geometry is None:
        return None

    try:
        result = await db.execute(
            select(
                func.ST_XMin(func.ST_Envelope(prop.geometry)).label("minx"),
                func.ST_YMin(func.ST_Envelope(prop.geometry)).label("miny"),
                func.ST_XMax(func.ST_Envelope(prop.geometry)).label("maxx"),
                func.ST_YMax(func.ST_Envelope(prop.geometry)).label("maxy"),
            )
        )
        row = result.one_or_none()
        if row and row.minx:
            return (row.minx, row.miny, row.maxx, row.maxy)
    except Exception:
        pass
    return None


async def _get_stands_with_geometry(
    property_id: uuid.UUID, db: AsyncSession
) -> tuple[list[dict], list[int]]:
    """Fetch stands that have geometry. Returns (geojson_list, stand_numbers)."""
    result = await db.execute(
        select(
            Stand.stand_number,
            Stand.area_ha,
            func.ST_AsGeoJSON(Stand.geometry).label("geojson"),
        )
        .where(Stand.property_id == property_id)
        .where(Stand.geometry.isnot(None))
        .order_by(Stand.stand_number)
    )
    rows = result.all()

    geometries = []
    stand_numbers = []
    for r in rows:
        if r.geojson:
            geometries.append(json.loads(r.geojson))
            stand_numbers.append(r.stand_number)

    return geometries, stand_numbers


def _estimate_bbox_from_coords(lat: float, lon: float, area_ha: float = 100):
    """Create an approximate SWEREF99 TM bounding box from lat/lon + area.

    Used as fallback when property has no geometry.
    """
    from pyproj import Transformer

    t = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True)
    cx, cy = t.transform(lon, lat)

    # Approximate side length from area
    import math
    side = math.sqrt(area_ha * 10000) * 1.5  # 50% buffer
    return (cx - side, cy - side, cx + side, cy + side)


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/scenes/{property_id}", response_model=ScenesResponse)
async def search_scenes(
    property_id: uuid.UUID,
    days_back: int = Query(60, ge=1, le=365, description="Antal dagar bakåt att söka"),
    max_cloud: int = Query(20, ge=0, le=100, description="Max molntäcke (%)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search for available Sentinel-2 scenes over a property.

    Returns a list of scenes sorted by date (newest first),
    filtered by cloud cover.
    """
    cache_key = f"satellite:scenes:{property_id}:{days_back}:{max_cloud}"
    cached = await cache_get(cache_key)
    if cached:
        return ScenesResponse(**json.loads(cached))

    prop = await _get_property_with_auth(property_id, db, current_user)

    # Get bounding box
    bbox = await _get_property_bbox(prop, db)
    if not bbox:
        # Fallback: estimate from coordinates
        from app.api.routes.weather import _get_property_centroid
        _, lat, lon = await _get_property_centroid(property_id, db, current_user)
        bbox = _estimate_bbox_from_coords(lat, lon, prop.total_area_ha or 100)

    today = date.today()
    date_from = today - timedelta(days=days_back)

    scenes = await _sentinel.search_scenes(
        bbox_3006=bbox,
        date_from=date_from,
        date_to=today,
        max_cloud_pct=max_cloud,
        limit=20,
    )

    response = ScenesResponse(
        property_id=str(property_id),
        scenes_found=len(scenes),
        search_from=date_from.isoformat(),
        search_to=today.isoformat(),
        scenes=[
            SceneInfo(
                id=s["id"],
                datetime=s["datetime"],
                cloud_cover=s["cloud_cover"],
                platform=s["platform"],
                tile_id=s["tile_id"],
                thumbnail=s.get("thumbnail"),
            )
            for s in scenes
        ],
    )

    await cache_set(cache_key, response.model_dump_json(), SCENES_CACHE_TTL)
    return response


@router.get("/ndvi/{property_id}", response_model=NdviResponse)
async def get_ndvi(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get latest NDVI statistics per stand for a property.

    Searches for the most recent cloud-free Sentinel-2 scene and
    calculates NDVI for each stand that has geometry.
    """
    cache_key = f"satellite:ndvi:{property_id}"
    cached = await cache_get(cache_key)
    if cached:
        return NdviResponse(**json.loads(cached))

    prop = await _get_property_with_auth(property_id, db, current_user)

    # Get property bbox
    bbox = await _get_property_bbox(prop, db)
    if not bbox:
        from app.api.routes.weather import _get_property_centroid
        _, lat, lon = await _get_property_centroid(property_id, db, current_user)
        bbox = _estimate_bbox_from_coords(lat, lon, prop.total_area_ha or 100)

    # Find latest scene
    today = date.today()
    scenes = await _sentinel.search_scenes(
        bbox_3006=bbox,
        date_from=today - timedelta(days=60),
        date_to=today,
        max_cloud_pct=20,
        limit=3,
    )

    if not scenes:
        return NdviResponse(
            property_id=str(property_id),
            stands=[],
            overall_ndvi_mean=None,
            overall_health_score=None,
        )

    latest = scenes[0]

    # Get stand geometries
    geometries, stand_numbers = await _get_stands_with_geometry(property_id, db)

    if not geometries:
        return NdviResponse(
            property_id=str(property_id),
            scene_date=latest["datetime"],
            scene_id=latest["id"],
            cloud_cover=latest["cloud_cover"],
            stands=[],
            overall_ndvi_mean=None,
            overall_health_score=None,
        )

    # Calculate NDVI per stand
    stand_ndvi_list = []
    all_means = []
    all_scores = []

    for geom, stand_num in zip(geometries, stand_numbers):
        ndvi_result = await _sentinel.calculate_ndvi(latest, geom)

        sn = StandNdvi(
            stand_number=stand_num,
            ndvi_mean=ndvi_result.get("ndvi_mean"),
            ndvi_median=ndvi_result.get("ndvi_median"),
            ndvi_min=ndvi_result.get("ndvi_min"),
            ndvi_max=ndvi_result.get("ndvi_max"),
            health_score=ndvi_result.get("health_score"),
            valid_pixel_count=ndvi_result.get("valid_pixel_count"),
            classification=ndvi_result.get("classification"),
            error=ndvi_result.get("error"),
        )
        stand_ndvi_list.append(sn)

        if sn.ndvi_mean is not None:
            all_means.append(sn.ndvi_mean)
        if sn.health_score is not None:
            all_scores.append(sn.health_score)

    response = NdviResponse(
        property_id=str(property_id),
        scene_date=latest["datetime"],
        scene_id=latest["id"],
        cloud_cover=latest["cloud_cover"],
        stands=stand_ndvi_list,
        overall_ndvi_mean=round(sum(all_means) / len(all_means), 4) if all_means else None,
        overall_health_score=round(sum(all_scores) / len(all_scores)) if all_scores else None,
    )

    await cache_set(cache_key, response.model_dump_json(), NDVI_CACHE_TTL)
    return response


@router.get("/health/{property_id}", response_model=HealthAnalysisResponse)
async def get_health_analysis(
    property_id: uuid.UUID,
    reference_months: int = Query(6, ge=1, le=24, description="Månader bakåt för referensscen"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full property health analysis with change detection.

    Compares latest Sentinel-2 scene with a reference scene (default 6 months back)
    to detect changes: clearcuts, storm damage, bark beetle damage, thinning, growth.

    This is the most comprehensive endpoint — use for detailed analysis.
    The /ndvi endpoint is lighter and suitable for dashboard widgets.
    """
    cache_key = f"satellite:health:{property_id}:{reference_months}"
    cached = await cache_get(cache_key)
    if cached:
        return HealthAnalysisResponse(**json.loads(cached))

    prop = await _get_property_with_auth(property_id, db, current_user)

    bbox = await _get_property_bbox(prop, db)
    if not bbox:
        from app.api.routes.weather import _get_property_centroid
        _, lat, lon = await _get_property_centroid(property_id, db, current_user)
        bbox = _estimate_bbox_from_coords(lat, lon, prop.total_area_ha or 100)

    geometries, stand_numbers = await _get_stands_with_geometry(property_id, db)

    if not geometries:
        return HealthAnalysisResponse(
            property_id=str(property_id),
            status="no_geometry",
            message="Inga avdelningar med geometri hittades. Ladda upp shapefile eller rita avdelningar på kartan.",
        )

    analysis = await _sentinel.analyze_property_health(
        property_bbox_3006=bbox,
        stand_geometries_3006=geometries,
        stand_ids=stand_numbers,
        reference_months_back=reference_months,
    )

    # Build response
    if analysis["status"] != "ok":
        return HealthAnalysisResponse(
            property_id=str(property_id),
            status=analysis["status"],
            message=analysis.get("message", "Analys kunde inte genomföras"),
        )

    latest = analysis.get("latest_scene")
    ref = analysis.get("reference_scene")

    stand_health_list = []
    for sr in analysis.get("stand_results", []):
        change_info = None
        if sr.get("change") and "error" not in sr["change"]:
            c = sr["change"]
            change_info = ChangeInfo(
                ndvi_before=c.get("ndvi_before"),
                ndvi_after=c.get("ndvi_after"),
                ndvi_change=c.get("ndvi_change"),
                change_pct=c.get("change_pct"),
                change_type=c.get("change_type"),
                change_label=c.get("change_label"),
                severity=c.get("severity"),
            )

        stand_health_list.append(StandHealth(
            stand_number=sr.get("stand_number", 0),
            ndvi_mean=sr.get("ndvi_mean"),
            health_score=sr.get("health_score"),
            change=change_info,
            error=sr.get("error"),
        ))

    problem_list = [
        ProblemStand(**ps) for ps in analysis.get("problem_stands", [])
    ]

    response = HealthAnalysisResponse(
        property_id=str(property_id),
        status="ok",
        analysis_date=analysis.get("analysis_date"),
        latest_scene=SceneInfo(**latest) if latest else None,
        reference_scene=SceneInfo(**ref) if ref else None,
        overall_health_score=analysis.get("overall_health_score"),
        stand_count_analyzed=analysis.get("stand_count_analyzed", 0),
        problem_stands=problem_list,
        stand_results=stand_health_list,
        scenes_available=analysis.get("scenes_available", 0),
    )

    await cache_set(cache_key, response.model_dump_json(), HEALTH_CACHE_TTL)
    return response
