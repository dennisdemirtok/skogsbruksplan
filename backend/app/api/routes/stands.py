import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.shape import from_shape, to_shape
from pydantic import BaseModel
from shapely.geometry import shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.property import Property
from app.models.stand import DataSource, ProposedAction, Stand, TargetClass
from app.models.user import User
from app.services.action_engine import ActionEngine
from app.services.economic_calculator import EconomicCalculator
from app.services.raster_service import RasterService
from app.utils.geo import (
    calculate_area_ha,
    geometry_to_geojson,
    sweref99_to_wgs84,
    wgs84_to_sweref99,
)

router = APIRouter(prefix="/stands", tags=["stands"])


class StandCreateRequest(BaseModel):
    property_id: uuid.UUID
    stand_number: int
    geometry_geojson: Optional[dict] = None
    area_ha: Optional[float] = None
    volume_m3_per_ha: Optional[float] = None
    total_volume_m3: Optional[float] = None
    mean_height_m: Optional[float] = None
    basal_area_m2: Optional[float] = None
    mean_diameter_cm: Optional[float] = None
    age_years: Optional[int] = None
    site_index: Optional[float] = None
    pine_pct: Optional[float] = 0
    spruce_pct: Optional[float] = 0
    deciduous_pct: Optional[float] = 0
    contorta_pct: Optional[float] = 0
    target_class: Optional[TargetClass] = TargetClass.PG
    proposed_action: Optional[ProposedAction] = None
    action_urgency: Optional[int] = None
    action_year: Optional[int] = None
    bark_beetle_risk: Optional[float] = None
    data_source: Optional[DataSource] = DataSource.auto
    notes: Optional[str] = None
    auto_fill: bool = True


class StandUpdateRequest(BaseModel):
    stand_number: Optional[int] = None
    geometry_geojson: Optional[dict] = None
    area_ha: Optional[float] = None
    volume_m3_per_ha: Optional[float] = None
    total_volume_m3: Optional[float] = None
    mean_height_m: Optional[float] = None
    basal_area_m2: Optional[float] = None
    mean_diameter_cm: Optional[float] = None
    age_years: Optional[int] = None
    site_index: Optional[float] = None
    pine_pct: Optional[float] = None
    spruce_pct: Optional[float] = None
    deciduous_pct: Optional[float] = None
    contorta_pct: Optional[float] = None
    target_class: Optional[TargetClass] = None
    proposed_action: Optional[ProposedAction] = None
    action_urgency: Optional[int] = None
    action_year: Optional[int] = None
    bark_beetle_risk: Optional[float] = None
    data_source: Optional[DataSource] = None
    field_verified: Optional[bool] = None
    notes: Optional[str] = None


class BulkStandUpdateRequest(BaseModel):
    stand_ids: list[uuid.UUID]
    proposed_action: Optional[ProposedAction] = None
    action_urgency: Optional[int] = None
    action_year: Optional[int] = None
    target_class: Optional[TargetClass] = None


class StandResponse(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    stand_number: int
    area_ha: Optional[float] = None
    volume_m3_per_ha: Optional[float] = None
    total_volume_m3: Optional[float] = None
    mean_height_m: Optional[float] = None
    basal_area_m2: Optional[float] = None
    mean_diameter_cm: Optional[float] = None
    age_years: Optional[int] = None
    site_index: Optional[float] = None
    pine_pct: Optional[float] = None
    spruce_pct: Optional[float] = None
    deciduous_pct: Optional[float] = None
    contorta_pct: Optional[float] = None
    target_class: Optional[TargetClass] = None
    proposed_action: Optional[ProposedAction] = None
    action_urgency: Optional[int] = None
    action_year: Optional[int] = None
    timber_volume_m3: Optional[float] = None
    pulpwood_volume_m3: Optional[float] = None
    gross_value_sek: Optional[float] = None
    harvesting_cost_sek: Optional[float] = None
    net_value_sek: Optional[float] = None
    bark_beetle_risk: Optional[float] = None
    data_source: Optional[DataSource] = None
    field_verified: bool = False
    notes: Optional[str] = None
    geometry_geojson: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StandGeoJSONFeature(BaseModel):
    type: str = "Feature"
    id: uuid.UUID
    geometry: Optional[dict] = None
    properties: dict


class StandGeoJSONCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[StandGeoJSONFeature]


def stand_to_geojson_feature(stand: Stand) -> StandGeoJSONFeature:
    geojson = None
    if stand.geometry is not None:
        try:
            shp = to_shape(stand.geometry)
            wgs84_geom = sweref99_to_wgs84(shp)
            geojson = geometry_to_geojson(wgs84_geom)
        except Exception:
            geojson = None

    return StandGeoJSONFeature(
        id=stand.id,
        geometry=geojson,
        properties={
            "stand_number": stand.stand_number,
            "area_ha": stand.area_ha,
            "volume_m3_per_ha": stand.volume_m3_per_ha,
            "total_volume_m3": stand.total_volume_m3,
            "mean_height_m": stand.mean_height_m,
            "basal_area_m2": stand.basal_area_m2,
            "mean_diameter_cm": stand.mean_diameter_cm,
            "age_years": stand.age_years,
            "site_index": stand.site_index,
            "pine_pct": stand.pine_pct,
            "spruce_pct": stand.spruce_pct,
            "deciduous_pct": stand.deciduous_pct,
            "contorta_pct": stand.contorta_pct,
            "target_class": (stand.target_class if isinstance(stand.target_class, str) else stand.target_class.value) if stand.target_class else None,
            "proposed_action": (stand.proposed_action if isinstance(stand.proposed_action, str) else stand.proposed_action.value) if stand.proposed_action else None,
            "action_urgency": stand.action_urgency,
            "action_year": stand.action_year,
            "timber_volume_m3": stand.timber_volume_m3,
            "pulpwood_volume_m3": stand.pulpwood_volume_m3,
            "gross_value_sek": stand.gross_value_sek,
            "harvesting_cost_sek": stand.harvesting_cost_sek,
            "net_value_sek": stand.net_value_sek,
            "bark_beetle_risk": stand.bark_beetle_risk,
            "data_source": (stand.data_source if isinstance(stand.data_source, str) else stand.data_source.value) if stand.data_source else None,
            "field_verified": stand.field_verified,
        },
    )


def stand_to_response(stand: Stand) -> StandResponse:
    geojson = None
    if stand.geometry is not None:
        try:
            shp = to_shape(stand.geometry)
            wgs84_geom = sweref99_to_wgs84(shp)
            geojson = geometry_to_geojson(wgs84_geom)
        except Exception:
            geojson = None

    return StandResponse(
        id=stand.id,
        property_id=stand.property_id,
        stand_number=stand.stand_number,
        area_ha=stand.area_ha,
        volume_m3_per_ha=stand.volume_m3_per_ha,
        total_volume_m3=stand.total_volume_m3,
        mean_height_m=stand.mean_height_m,
        basal_area_m2=stand.basal_area_m2,
        mean_diameter_cm=stand.mean_diameter_cm,
        age_years=stand.age_years,
        site_index=stand.site_index,
        pine_pct=stand.pine_pct,
        spruce_pct=stand.spruce_pct,
        deciduous_pct=stand.deciduous_pct,
        contorta_pct=stand.contorta_pct,
        target_class=stand.target_class,
        proposed_action=stand.proposed_action,
        action_urgency=stand.action_urgency,
        action_year=stand.action_year,
        timber_volume_m3=stand.timber_volume_m3,
        pulpwood_volume_m3=stand.pulpwood_volume_m3,
        gross_value_sek=stand.gross_value_sek,
        harvesting_cost_sek=stand.harvesting_cost_sek,
        net_value_sek=stand.net_value_sek,
        bark_beetle_risk=stand.bark_beetle_risk,
        data_source=stand.data_source,
        field_verified=stand.field_verified,
        notes=stand.notes,
        geometry_geojson=geojson,
        created_at=stand.created_at,
        updated_at=stand.updated_at,
    )


async def _verify_property_access(
    property_id: uuid.UUID, user: User, db: AsyncSession
) -> Property:
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fastigheten hittades inte",
        )
    if prop.owner_id != user.id and prop.created_by != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Åtkomst nekad",
        )
    return prop


@router.post("", response_model=StandResponse, status_code=status.HTTP_201_CREATED)
async def create_stand(
    request: StandCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_property_access(request.property_id, current_user, db)

    geometry_wkb = None
    area = request.area_ha

    if request.geometry_geojson:
        shp = shape(request.geometry_geojson)
        shp_3006 = wgs84_to_sweref99(shp)
        geometry_wkb = from_shape(shp_3006, srid=3006)
        if area is None:
            area = calculate_area_ha(shp_3006)

    stand = Stand(
        id=uuid.uuid4(),
        property_id=request.property_id,
        stand_number=request.stand_number,
        geometry=geometry_wkb,
        area_ha=area,
        volume_m3_per_ha=request.volume_m3_per_ha,
        total_volume_m3=request.total_volume_m3,
        mean_height_m=request.mean_height_m,
        basal_area_m2=request.basal_area_m2,
        mean_diameter_cm=request.mean_diameter_cm,
        age_years=request.age_years,
        site_index=request.site_index,
        pine_pct=request.pine_pct,
        spruce_pct=request.spruce_pct,
        deciduous_pct=request.deciduous_pct,
        contorta_pct=request.contorta_pct,
        target_class=request.target_class,
        proposed_action=request.proposed_action,
        action_urgency=request.action_urgency,
        action_year=request.action_year,
        bark_beetle_risk=request.bark_beetle_risk,
        data_source=request.data_source,
        notes=request.notes,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    if request.auto_fill and request.geometry_geojson:
        try:
            raster_svc = RasterService(settings.RASTER_DATA_PATH)
            shp_3006 = wgs84_to_sweref99(shape(request.geometry_geojson))
            raster_data = raster_svc.get_stand_data_from_rasters(
                shp_3006.wkt, settings.RASTER_DATA_PATH
            )
            if raster_data:
                if stand.volume_m3_per_ha is None and raster_data.get("volume_m3_per_ha") is not None:
                    stand.volume_m3_per_ha = raster_data["volume_m3_per_ha"]
                if stand.mean_height_m is None and raster_data.get("mean_height_m") is not None:
                    stand.mean_height_m = raster_data["mean_height_m"]
                if stand.basal_area_m2 is None and raster_data.get("basal_area_m2") is not None:
                    stand.basal_area_m2 = raster_data["basal_area_m2"]
                if stand.mean_diameter_cm is None and raster_data.get("mean_diameter_cm") is not None:
                    stand.mean_diameter_cm = raster_data["mean_diameter_cm"]
                if stand.age_years is None and raster_data.get("age_years") is not None:
                    stand.age_years = raster_data["age_years"]
                if stand.site_index is None and raster_data.get("site_index") is not None:
                    stand.site_index = raster_data["site_index"]
                if stand.pine_pct == 0 and raster_data.get("pine_pct") is not None:
                    stand.pine_pct = raster_data["pine_pct"]
                if stand.spruce_pct == 0 and raster_data.get("spruce_pct") is not None:
                    stand.spruce_pct = raster_data["spruce_pct"]
                if stand.deciduous_pct == 0 and raster_data.get("deciduous_pct") is not None:
                    stand.deciduous_pct = raster_data["deciduous_pct"]
                if stand.contorta_pct == 0 and raster_data.get("contorta_pct") is not None:
                    stand.contorta_pct = raster_data["contorta_pct"]
        except Exception:
            pass

    if stand.volume_m3_per_ha is not None and stand.area_ha is not None:
        if stand.total_volume_m3 is None:
            stand.total_volume_m3 = round(stand.volume_m3_per_ha * stand.area_ha, 1)

    stand_data = _stand_to_dict(stand)
    if stand.proposed_action is None:
        engine = ActionEngine()
        action_result = engine.propose_action(stand_data)
        stand.proposed_action = ProposedAction(action_result["action"])
        stand.action_urgency = action_result["urgency"]

    calculator = EconomicCalculator()
    economics = calculator.calculate_stand_economics(stand_data)
    stand.timber_volume_m3 = economics["timber_volume_m3"]
    stand.pulpwood_volume_m3 = economics["pulpwood_volume_m3"]
    stand.gross_value_sek = economics["gross_value_sek"]
    stand.harvesting_cost_sek = economics["harvesting_cost_sek"]
    stand.net_value_sek = economics["net_value_sek"]

    db.add(stand)
    await db.flush()
    await db.refresh(stand)

    return stand_to_response(stand)


@router.get("/property/{property_id}", response_model=StandGeoJSONCollection)
async def list_stands(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_property_access(property_id, current_user, db)

    result = await db.execute(
        select(Stand)
        .where(Stand.property_id == property_id)
        .order_by(Stand.stand_number)
    )
    stands = result.scalars().all()
    features = [stand_to_geojson_feature(s) for s in stands]
    return StandGeoJSONCollection(features=features)


@router.get("/{stand_id}", response_model=StandResponse)
async def get_stand(
    stand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Stand).where(Stand.id == stand_id))
    stand = result.scalar_one_or_none()
    if not stand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avdelningen hittades inte",
        )
    await _verify_property_access(stand.property_id, current_user, db)
    return stand_to_response(stand)


@router.put("/{stand_id}", response_model=StandResponse)
async def update_stand(
    stand_id: uuid.UUID,
    request: StandUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Stand).where(Stand.id == stand_id))
    stand = result.scalar_one_or_none()
    if not stand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avdelningen hittades inte",
        )
    await _verify_property_access(stand.property_id, current_user, db)

    update_data = request.model_dump(exclude_unset=True)
    geometry_geojson = update_data.pop("geometry_geojson", None)

    if geometry_geojson is not None:
        shp = shape(geometry_geojson)
        shp_3006 = wgs84_to_sweref99(shp)
        stand.geometry = from_shape(shp_3006, srid=3006)
        if "area_ha" not in update_data:
            stand.area_ha = calculate_area_ha(shp_3006)

    for field, value in update_data.items():
        setattr(stand, field, value)

    if stand.volume_m3_per_ha is not None and stand.area_ha is not None:
        stand.total_volume_m3 = round(stand.volume_m3_per_ha * stand.area_ha, 1)

    stand_data = _stand_to_dict(stand)
    calculator = EconomicCalculator()
    economics = calculator.calculate_stand_economics(stand_data)
    stand.timber_volume_m3 = economics["timber_volume_m3"]
    stand.pulpwood_volume_m3 = economics["pulpwood_volume_m3"]
    stand.gross_value_sek = economics["gross_value_sek"]
    stand.harvesting_cost_sek = economics["harvesting_cost_sek"]
    stand.net_value_sek = economics["net_value_sek"]

    stand.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(stand)

    return stand_to_response(stand)


@router.delete("/{stand_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stand(
    stand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Stand).where(Stand.id == stand_id))
    stand = result.scalar_one_or_none()
    if not stand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avdelningen hittades inte",
        )
    await _verify_property_access(stand.property_id, current_user, db)
    await db.delete(stand)
    await db.flush()


@router.put("/bulk/update", response_model=list[StandResponse])
async def bulk_update_stands(
    request: BulkStandUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Stand).where(Stand.id.in_(request.stand_ids))
    )
    stands = result.scalars().all()

    if len(stands) != len(request.stand_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="En eller flera avdelningar hittades inte",
        )

    verified_properties: set[uuid.UUID] = set()
    for stand in stands:
        if stand.property_id not in verified_properties:
            await _verify_property_access(stand.property_id, current_user, db)
            verified_properties.add(stand.property_id)

    updated = []
    for stand in stands:
        if request.proposed_action is not None:
            stand.proposed_action = request.proposed_action
        if request.action_urgency is not None:
            stand.action_urgency = request.action_urgency
        if request.action_year is not None:
            stand.action_year = request.action_year
        if request.target_class is not None:
            stand.target_class = request.target_class
        stand.updated_at = datetime.now(timezone.utc)
        updated.append(stand_to_response(stand))

    await db.flush()
    return updated


def _stand_to_dict(stand: Stand) -> dict:
    return {
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
        "target_class": (stand.target_class if isinstance(stand.target_class, str) else stand.target_class.value) if stand.target_class else "PG",
        "proposed_action": (stand.proposed_action if isinstance(stand.proposed_action, str) else stand.proposed_action.value) if stand.proposed_action else "ingen",
        "bark_beetle_risk": stand.bark_beetle_risk or 0,
    }
