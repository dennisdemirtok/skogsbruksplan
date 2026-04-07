import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from shapely.geometry import mapping, shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.property import Property
from app.models.stand import Stand
from app.models.user import User
from app.services.action_engine import ActionEngine
from app.services.economic_calculator import EconomicCalculator
from app.services.forest_estimator import estimate_stand_data
from app.services.lantmateriet_client import LantmaterietClient
from app.services.raster_service import RasterService
from app.utils.geo import (
    calculate_area_ha,
    geometry_to_geojson,
    sweref99_to_wgs84,
    wgs84_to_sweref99,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/properties", tags=["properties"])


class PropertyCreateRequest(BaseModel):
    designation: str
    municipality: Optional[str] = None
    county: Optional[str] = None
    geometry_geojson: Optional[dict] = None
    owner_id: Optional[uuid.UUID] = None
    total_area_ha: Optional[float] = None
    productive_forest_ha: Optional[float] = None


class PropertyUpdateRequest(BaseModel):
    designation: Optional[str] = None
    municipality: Optional[str] = None
    county: Optional[str] = None
    geometry_geojson: Optional[dict] = None
    total_area_ha: Optional[float] = None
    productive_forest_ha: Optional[float] = None


class PropertyResponse(BaseModel):
    id: uuid.UUID
    name: str
    municipality: str
    county: str
    property_designation: str
    total_area: float
    productive_area: float
    boundary_geojson: Optional[dict] = None
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


def _geom_text_to_shape(geom_text: str):
    """Convert stored GeoJSON text to a Shapely shape."""
    return shape(json.loads(geom_text))


def _shape_to_geom_text(shp) -> str:
    """Convert a Shapely shape to GeoJSON text for storage."""
    return json.dumps(mapping(shp))


def property_to_response(prop: Property) -> PropertyResponse:
    boundary = None
    if prop.geometry is not None:
        try:
            shp = _geom_text_to_shape(prop.geometry)
            wgs84_geom = sweref99_to_wgs84(shp)
            geojson_geom = geometry_to_geojson(wgs84_geom)
            boundary = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": geojson_geom,
                    "properties": {},
                }],
            }
        except Exception:
            boundary = None

    return PropertyResponse(
        id=prop.id,
        name=prop.designation,
        municipality=prop.municipality or "",
        county=prop.county or "",
        property_designation=prop.designation,
        total_area=prop.total_area_ha or 0,
        productive_area=prop.productive_forest_ha or 0,
        boundary_geojson=boundary,
        owner_id=prop.owner_id,
        created_at=prop.created_at,
        updated_at=prop.updated_at,
    )


@router.post("", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    request: PropertyCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    geometry_text = None
    total_area = request.total_area_ha
    municipality = request.municipality
    county = request.county

    if request.geometry_geojson:
        shp = shape(request.geometry_geojson)
        shp_3006 = wgs84_to_sweref99(shp)
        geometry_text = _shape_to_geom_text(shp_3006)
        if total_area is None:
            total_area = calculate_area_ha(shp_3006)
    else:
        client = LantmaterietClient()
        lookup_result = await client.lookup_property(request.designation)
        if lookup_result and lookup_result.get("geometry"):
            geom = shape(lookup_result["geometry"])
            geom_3006 = wgs84_to_sweref99(geom)
            geometry_text = _shape_to_geom_text(geom_3006)
            if total_area is None:
                total_area = calculate_area_ha(geom_3006)
            if municipality is None:
                municipality = lookup_result.get("municipality", municipality)
            if county is None:
                county = lookup_result.get("county", county)

    owner_id = request.owner_id if request.owner_id else current_user.id

    prop = Property(
        id=uuid.uuid4(),
        designation=request.designation,
        municipality=municipality,
        county=county,
        geometry=geometry_text,
        total_area_ha=total_area,
        productive_forest_ha=request.productive_forest_ha,
        owner_id=owner_id,
        created_by=current_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(prop)
    await db.flush()
    await db.refresh(prop)

    # Auto-create an initial stand covering the full property
    if geometry_text and total_area and total_area > 0:
        try:
            await _create_initial_stand(
                db=db,
                prop=prop,
                geometry_text=geometry_text,
                area_ha=total_area,
                municipality=municipality,
                county=county,
                designation=request.designation,
            )
            logger.info(f"Auto-created initial stand for property {prop.designation}")
        except Exception as e:
            logger.warning(f"Failed to auto-create stand: {e}")
            # Don't fail property creation if stand creation fails

    return property_to_response(prop)


async def _create_initial_stand(
    db: AsyncSession,
    prop: Property,
    geometry_text: str,
    area_ha: float,
    municipality: str = None,
    county: str = None,
    designation: str = None,
):
    """Create an initial stand covering the full property boundary.

    Tries raster data first, falls back to regional estimates.
    Then calculates economics and proposes management actions.
    """
    # Try to get forest data from rasters first
    stand_data = None
    try:
        shp_3006 = _geom_text_to_shape(geometry_text)
        raster_svc = RasterService(settings.RASTER_DATA_PATH)
        stand_data = raster_svc.get_stand_data_from_rasters(
            shp_3006.wkt, settings.RASTER_DATA_PATH
        )
    except Exception as e:
        logger.debug(f"Raster extraction failed: {e}")

    # Fallback: estimate from regional averages
    if not stand_data or all(v is None for v in stand_data.values()):
        stand_data = estimate_stand_data(
            area_ha=area_ha,
            municipality=municipality,
            county=county,
            designation=designation,
        )
        data_source = "auto"
    else:
        data_source = "auto"

    # Convert polygon to single-part for stand (use same geometry as property)
    # Stand geometry stored in same format as property
    stand_geometry = geometry_text

    now = datetime.now(timezone.utc)
    stand = Stand(
        id=uuid.uuid4(),
        property_id=prop.id,
        stand_number=1,
        geometry=stand_geometry,
        area_ha=area_ha,
        volume_m3_per_ha=stand_data.get("volume_m3_per_ha"),
        total_volume_m3=stand_data.get("total_volume_m3"),
        mean_height_m=stand_data.get("mean_height_m"),
        basal_area_m2=stand_data.get("basal_area_m2"),
        mean_diameter_cm=stand_data.get("mean_diameter_cm"),
        age_years=stand_data.get("age_years"),
        site_index=stand_data.get("site_index"),
        pine_pct=stand_data.get("pine_pct"),
        spruce_pct=stand_data.get("spruce_pct"),
        deciduous_pct=stand_data.get("deciduous_pct"),
        contorta_pct=stand_data.get("contorta_pct"),
        target_class="PG",
        data_source=data_source,
        field_verified=False,
        created_at=now,
        updated_at=now,
    )

    # Calculate total volume if not set
    if stand.volume_m3_per_ha and stand.area_ha:
        if not stand.total_volume_m3:
            stand.total_volume_m3 = round(stand.volume_m3_per_ha * stand.area_ha, 1)

    # Propose management action
    try:
        stand_dict = {
            "area_ha": stand.area_ha,
            "volume_m3_per_ha": stand.volume_m3_per_ha,
            "total_volume_m3": stand.total_volume_m3,
            "mean_height_m": stand.mean_height_m,
            "basal_area_m2": stand.basal_area_m2,
            "mean_diameter_cm": stand.mean_diameter_cm,
            "age_years": stand.age_years,
            "site_index": stand.site_index,
            "pine_pct": stand.pine_pct or 0,
            "spruce_pct": stand.spruce_pct or 0,
            "deciduous_pct": stand.deciduous_pct or 0,
            "contorta_pct": stand.contorta_pct or 0,
            "target_class": "PG",
            "proposed_action": "ingen",
            "bark_beetle_risk": 0,
        }

        engine = ActionEngine()
        action_result = engine.propose_action(stand_dict)
        stand.proposed_action = action_result["action"]
        stand.action_urgency = action_result["urgency"]

        # Calculate economics
        calculator = EconomicCalculator()
        economics = calculator.calculate_stand_economics(stand_dict)
        stand.timber_volume_m3 = economics["timber_volume_m3"]
        stand.pulpwood_volume_m3 = economics["pulpwood_volume_m3"]
        stand.gross_value_sek = economics["gross_value_sek"]
        stand.harvesting_cost_sek = economics["harvesting_cost_sek"]
        stand.net_value_sek = economics["net_value_sek"]
    except Exception as e:
        logger.warning(f"Economics/action calculation failed: {e}")

    db.add(stand)
    await db.flush()


@router.get("", response_model=list[PropertyResponse])
async def list_properties(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Property)
        .where(
            (Property.owner_id == current_user.id)
            | (Property.created_by == current_user.id)
        )
        .order_by(Property.designation)
    )
    properties = result.scalars().all()
    return [property_to_response(p) for p in properties]


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Property).where(Property.id == property_id))
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
    return property_to_response(prop)


@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: uuid.UUID,
    request: PropertyUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Property).where(Property.id == property_id))
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

    if request.designation is not None:
        prop.designation = request.designation
    if request.municipality is not None:
        prop.municipality = request.municipality
    if request.county is not None:
        prop.county = request.county
    if request.total_area_ha is not None:
        prop.total_area_ha = request.total_area_ha
    if request.productive_forest_ha is not None:
        prop.productive_forest_ha = request.productive_forest_ha
    if request.geometry_geojson is not None:
        shp = shape(request.geometry_geojson)
        shp_3006 = wgs84_to_sweref99(shp)
        prop.geometry = _shape_to_geom_text(shp_3006)
        if request.total_area_ha is None:
            prop.total_area_ha = calculate_area_ha(shp_3006)

    prop.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(prop)

    return property_to_response(prop)


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Property).where(Property.id == property_id))
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
    await db.delete(prop)
    await db.flush()
