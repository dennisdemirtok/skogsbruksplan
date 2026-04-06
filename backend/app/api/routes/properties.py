import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from shapely.geometry import mapping, shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.property import Property
from app.models.user import User
from app.services.lantmateriet_client import LantmaterietClient
from app.utils.geo import (
    calculate_area_ha,
    geometry_to_geojson,
    sweref99_to_wgs84,
    wgs84_to_sweref99,
)

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

    return property_to_response(prop)


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
