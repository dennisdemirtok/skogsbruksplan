import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis_client import cache_get, cache_set
from app.core.security import get_current_user
from app.models.property import Property
from app.models.user import User
from app.services.lantmateriet_client import LantmaterietClient
from app.services.skogsstyrelsen_client import SkogsstyrelsenClient
from app.utils.geo import bbox_to_polygon, geometry_to_geojson

router = APIRouter(prefix="/geodata", tags=["geodata"])


class ForestDataResponse(BaseModel):
    bbox: list[float]
    data: dict


class PropertyLookupResponse(BaseModel):
    designation: str
    municipality: Optional[str] = None
    county: Optional[str] = None
    geometry: Optional[dict] = None
    area_ha: Optional[float] = None
    lantmateriet_id: Optional[str] = None
    last_updated: Optional[str] = None
    source: str = "mock"


class PropertySearchResult(BaseModel):
    designation: str
    municipality: str
    kommun_code: str = ""
    trakt: str = ""
    block: str = ""
    enhet: int = 0
    last_updated: str = ""


class PropertySearchResponse(BaseModel):
    query: str
    results_count: int
    results: list[PropertySearchResult]


class BarkBeetleRiskResponse(BaseModel):
    bbox: list[float]
    risk_data: dict


class SatelliteResponse(BaseModel):
    property_id: uuid.UUID
    message: str
    available: bool = False
    data: Optional[dict] = None


@router.get("/forest-data", response_model=ForestDataResponse)
async def get_forest_data(
    bbox: str = Query(
        ...,
        description="Bounding box as 'minx,miny,maxx,maxy' in EPSG:3006",
        example="600000,6600000,610000,6610000",
    ),
    current_user: User = Depends(get_current_user),
):
    try:
        coords = [float(c.strip()) for c in bbox.split(",")]
        if len(coords) != 4:
            raise ValueError("Bounding box ska innehålla exakt 4 koordinater")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ogiltig bounding box: {e}",
        )

    # Check Redis cache
    cache_key = f"geodata:forest-data:{bbox}"
    cached = await cache_get(cache_key)
    if cached:
        return ForestDataResponse(**json.loads(cached))

    polygon = bbox_to_polygon(coords)
    polygon_geojson = geometry_to_geojson(polygon)

    client = SkogsstyrelsenClient()
    try:
        data = await client.get_forest_data(polygon_geojson)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Kunde inte hämta data från Skogsstyrelsen: {str(e)}",
        )

    response = ForestDataResponse(bbox=coords, data=data)
    await cache_set(cache_key, response.model_dump_json(), ttl=3600)
    return response


@router.get("/property-lookup", response_model=PropertyLookupResponse)
async def lookup_property(
    designation: str = Query(..., description="Fastighetsbeteckning, t.ex. 'Sollefteå Billsta 9:12'"),
    current_user: User = Depends(get_current_user),
):
    # Check Redis cache
    cache_key = f"geodata:property-lookup:{designation}"
    cached = await cache_get(cache_key)
    if cached:
        return PropertyLookupResponse(**json.loads(cached))

    client = LantmaterietClient()
    try:
        result = await client.lookup_property(designation)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Kunde inte slå upp fastigheten: {str(e)}",
        )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fastigheten hittades inte",
        )

    response = PropertyLookupResponse(
        designation=designation,
        municipality=result.get("municipality"),
        county=result.get("county"),
        geometry=result.get("geometry"),
        area_ha=result.get("area_ha"),
        lantmateriet_id=result.get("lantmateriet_id"),
        last_updated=result.get("last_updated"),
        source="lantmateriet" if result.get("lantmateriet_id") else "mock",
    )
    await cache_set(cache_key, response.model_dump_json(), ttl=3600)
    return response


@router.get("/property-search", response_model=PropertySearchResponse)
async def search_properties(
    municipality: Optional[str] = Query(None, description="Kommunnamn, t.ex. 'Sollefteå'"),
    trakt: Optional[str] = Query(None, description="Traktnamn, t.ex. 'BRINGEN'"),
    limit: int = Query(20, ge=1, le=100, description="Max antal resultat"),
    current_user: User = Depends(get_current_user),
):
    """Search for properties in Lantmäteriet by municipality and/or tract name.

    Returns matching property designations that can then be looked up
    with /property-lookup to get full geometry.
    """
    if not municipality and not trakt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ange minst kommun eller trakt för att söka",
        )

    client = LantmaterietClient()
    try:
        results = await client.search_properties(
            municipality=municipality,
            trakt=trakt,
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Sökning misslyckades: {str(e)}",
        )

    query_parts = []
    if municipality:
        query_parts.append(f"kommun={municipality}")
    if trakt:
        query_parts.append(f"trakt={trakt}")

    return PropertySearchResponse(
        query=" & ".join(query_parts),
        results_count=len(results),
        results=[PropertySearchResult(**r) for r in results],
    )


@router.get("/bark-beetle-risk", response_model=BarkBeetleRiskResponse)
async def get_bark_beetle_risk(
    bbox: str = Query(
        ...,
        description="Bounding box as 'minx,miny,maxx,maxy' in EPSG:3006",
    ),
    current_user: User = Depends(get_current_user),
):
    try:
        coords = [float(c.strip()) for c in bbox.split(",")]
        if len(coords) != 4:
            raise ValueError("Bounding box ska innehålla exakt 4 koordinater")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ogiltig bounding box: {e}",
        )

    # Check Redis cache
    cache_key = f"geodata:bark-beetle-risk:{bbox}"
    cached = await cache_get(cache_key)
    if cached:
        return BarkBeetleRiskResponse(**json.loads(cached))

    polygon = bbox_to_polygon(coords)
    polygon_geojson = geometry_to_geojson(polygon)

    client = SkogsstyrelsenClient()
    try:
        risk_data = await client.get_bark_beetle_risk(polygon_geojson)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Kunde inte hämta granbarkborreriskdata: {str(e)}",
        )

    response = BarkBeetleRiskResponse(bbox=coords, risk_data=risk_data)
    await cache_set(cache_key, response.model_dump_json(), ttl=3600)
    return response


@router.get("/satellite/{property_id}", response_model=SatelliteResponse)
async def get_satellite_data(
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

    return SatelliteResponse(
        property_id=property_id,
        message="Sentinel-2 satellitdata kommer att vara tillgängligt i en framtida version. "
                "Funktionen är planerad att inkludera NDVI-analys, förändingsdetektering "
                "och stormskadekartläggning.",
        available=False,
        data=None,
    )
