import secrets
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.plan import Certification, ForestPlan, PlanStatus
from app.models.property import Property
from app.models.stand import Stand
from app.models.user import User
# User is already imported for get_current_user dependency
from app.services.pdf_generator import PDFGenerator

router = APIRouter(prefix="/plans", tags=["plans"])


class PlanCreateRequest(BaseModel):
    property_id: uuid.UUID
    name: str
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    certification: Certification = Certification.none


class PlanUpdateRequest(BaseModel):
    name: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    certification: Optional[Certification] = None


class PlanResponse(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    name: str
    version: int
    status: PlanStatus
    created_by: uuid.UUID
    share_token: Optional[str] = None
    pdf_url: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    certification: Certification
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlanDetailResponse(PlanResponse):
    property_designation: Optional[str] = None
    stand_count: int = 0
    total_area_ha: Optional[float] = None


async def _get_plan_with_access(
    plan_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> ForestPlan:
    result = await db.execute(
        select(ForestPlan).where(ForestPlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skogsbruksplanen hittades inte",
        )
    prop_result = await db.execute(
        select(Property).where(Property.id == plan.property_id)
    )
    prop = prop_result.scalar_one_or_none()
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fastigheten hittades inte",
        )
    if prop.owner_id != user.id and prop.created_by != user.id and plan.created_by != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Åtkomst nekad",
        )
    return plan


@router.post("", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    request: PlanCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop_result = await db.execute(
        select(Property).where(Property.id == request.property_id)
    )
    prop = prop_result.scalar_one_or_none()
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

    existing_result = await db.execute(
        select(ForestPlan)
        .where(ForestPlan.property_id == request.property_id)
        .order_by(ForestPlan.version.desc())
        .limit(1)
    )
    existing = existing_result.scalar_one_or_none()
    version = (existing.version + 1) if existing else 1

    share_token = secrets.token_urlsafe(32)

    plan = ForestPlan(
        id=uuid.uuid4(),
        property_id=request.property_id,
        name=request.name,
        version=version,
        status=PlanStatus.draft,
        created_by=current_user.id,
        share_token=share_token,
        valid_from=request.valid_from,
        valid_to=request.valid_to,
        certification=request.certification,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(plan)
    await db.flush()
    await db.refresh(plan)

    return PlanResponse.model_validate(plan)


@router.get("", response_model=list[PlanDetailResponse])
async def list_plans(
    property_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(ForestPlan).where(ForestPlan.created_by == current_user.id)
    if property_id:
        query = query.where(ForestPlan.property_id == property_id)
    query = query.order_by(ForestPlan.updated_at.desc())

    result = await db.execute(query)
    plans = result.scalars().all()

    responses = []
    for plan in plans:
        prop_result = await db.execute(
            select(Property).where(Property.id == plan.property_id)
        )
        prop = prop_result.scalar_one_or_none()

        stand_result = await db.execute(
            select(Stand).where(Stand.property_id == plan.property_id)
        )
        stands = stand_result.scalars().all()

        responses.append(
            PlanDetailResponse(
                id=plan.id,
                property_id=plan.property_id,
                name=plan.name,
                version=plan.version,
                status=plan.status,
                created_by=plan.created_by,
                share_token=plan.share_token,
                pdf_url=plan.pdf_url,
                valid_from=plan.valid_from,
                valid_to=plan.valid_to,
                certification=plan.certification,
                created_at=plan.created_at,
                updated_at=plan.updated_at,
                property_designation=prop.designation if prop else None,
                stand_count=len(stands),
                total_area_ha=prop.total_area_ha if prop else None,
            )
        )

    return responses


@router.get("/shared/{share_token}", response_model=PlanDetailResponse)
async def get_shared_plan(
    share_token: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ForestPlan).where(ForestPlan.share_token == share_token)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skogsbruksplanen hittades inte",
        )
    if plan.status != PlanStatus.published:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Planen är inte publicerad",
        )

    prop_result = await db.execute(
        select(Property).where(Property.id == plan.property_id)
    )
    prop = prop_result.scalar_one_or_none()

    stand_result = await db.execute(
        select(Stand).where(Stand.property_id == plan.property_id)
    )
    stands = stand_result.scalars().all()

    return PlanDetailResponse(
        id=plan.id,
        property_id=plan.property_id,
        name=plan.name,
        version=plan.version,
        status=plan.status,
        created_by=plan.created_by,
        share_token=plan.share_token,
        pdf_url=plan.pdf_url,
        valid_from=plan.valid_from,
        valid_to=plan.valid_to,
        certification=plan.certification,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        property_designation=prop.designation if prop else None,
        stand_count=len(stands),
        total_area_ha=prop.total_area_ha if prop else None,
    )


@router.get("/{plan_id}", response_model=PlanDetailResponse)
async def get_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = await _get_plan_with_access(plan_id, current_user, db)

    prop_result = await db.execute(
        select(Property).where(Property.id == plan.property_id)
    )
    prop = prop_result.scalar_one_or_none()

    stand_result = await db.execute(
        select(Stand).where(Stand.property_id == plan.property_id)
    )
    stands = stand_result.scalars().all()

    return PlanDetailResponse(
        id=plan.id,
        property_id=plan.property_id,
        name=plan.name,
        version=plan.version,
        status=plan.status,
        created_by=plan.created_by,
        share_token=plan.share_token,
        pdf_url=plan.pdf_url,
        valid_from=plan.valid_from,
        valid_to=plan.valid_to,
        certification=plan.certification,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        property_designation=prop.designation if prop else None,
        stand_count=len(stands),
        total_area_ha=prop.total_area_ha if prop else None,
    )


@router.put("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: uuid.UUID,
    request: PlanUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = await _get_plan_with_access(plan_id, current_user, db)

    if plan.status == PlanStatus.published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Publicerade planer kan inte redigeras. Skapa en ny version.",
        )

    if request.name is not None:
        plan.name = request.name
    if request.valid_from is not None:
        plan.valid_from = request.valid_from
    if request.valid_to is not None:
        plan.valid_to = request.valid_to
    if request.certification is not None:
        plan.certification = request.certification

    plan.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(plan)

    return PlanResponse.model_validate(plan)


@router.post("/{plan_id}/publish", response_model=PlanResponse)
async def publish_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = await _get_plan_with_access(plan_id, current_user, db)

    if plan.status == PlanStatus.published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Planen är redan publicerad",
        )

    prev_result = await db.execute(
        select(ForestPlan)
        .where(
            ForestPlan.property_id == plan.property_id,
            ForestPlan.status == PlanStatus.published,
            ForestPlan.id != plan.id,
        )
    )
    for prev_plan in prev_result.scalars().all():
        prev_plan.status = PlanStatus.archived
        prev_plan.updated_at = datetime.now(timezone.utc)

    plan.status = PlanStatus.published
    plan.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(plan)

    return PlanResponse.model_validate(plan)


@router.get("/{plan_id}/pdf")
async def generate_plan_pdf(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = await _get_plan_with_access(plan_id, current_user, db)

    prop_result = await db.execute(
        select(Property).where(Property.id == plan.property_id)
    )
    prop = prop_result.scalar_one_or_none()
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fastigheten hittades inte",
        )

    stand_result = await db.execute(
        select(Stand, func.ST_AsGeoJSON(Stand.geometry).label("geojson"))
        .where(Stand.property_id == plan.property_id)
        .order_by(Stand.stand_number)
    )
    stand_rows = stand_result.all()

    # Get property boundary as GeoJSON for map rendering
    geo_result = await db.execute(
        select(func.ST_AsGeoJSON(Property.geometry))
        .where(Property.id == prop.id)
    )
    prop_geojson = geo_result.scalar_one_or_none()

    # Get planner name from creator
    creator_result = await db.execute(
        select(User).where(User.id == plan.created_by)
    )
    creator = creator_result.scalar_one_or_none()
    planner_name = creator.full_name if creator else "Okänd"

    plan_dict = {
        "id": str(plan.id),
        "name": plan.name,
        "version": plan.version,
        "status": plan.status if isinstance(plan.status, str) else plan.status.value,
        "valid_from": plan.valid_from.isoformat() if plan.valid_from else None,
        "valid_to": plan.valid_to.isoformat() if plan.valid_to else None,
        "certification": plan.certification if isinstance(plan.certification, str) else plan.certification.value,
        "created_at": plan.created_at.isoformat(),
        "planner_name": planner_name,
    }

    prop_dict = {
        "designation": prop.designation,
        "municipality": prop.municipality,
        "county": prop.county,
        "total_area_ha": prop.total_area_ha,
        "productive_forest_ha": prop.productive_forest_ha,
    }

    stands_list = []
    for row in stand_rows:
        s = row[0]
        geojson = row[1]
        stands_list.append({
            "stand_number": s.stand_number,
            "area_ha": s.area_ha,
            "volume_m3_per_ha": s.volume_m3_per_ha,
            "total_volume_m3": s.total_volume_m3,
            "mean_height_m": s.mean_height_m,
            "basal_area_m2": s.basal_area_m2,
            "mean_diameter_cm": s.mean_diameter_cm,
            "age_years": s.age_years,
            "site_index": s.site_index,
            "pine_pct": s.pine_pct,
            "spruce_pct": s.spruce_pct,
            "deciduous_pct": s.deciduous_pct,
            "contorta_pct": s.contorta_pct,
            "target_class": (s.target_class if isinstance(s.target_class, str) else s.target_class.value) if s.target_class else None,
            "proposed_action": (s.proposed_action if isinstance(s.proposed_action, str) else s.proposed_action.value) if s.proposed_action else None,
            "action_urgency": s.action_urgency,
            "action_year": s.action_year,
            "timber_volume_m3": s.timber_volume_m3,
            "pulpwood_volume_m3": s.pulpwood_volume_m3,
            "gross_value_sek": s.gross_value_sek,
            "harvesting_cost_sek": s.harvesting_cost_sek,
            "net_value_sek": s.net_value_sek,
            "bark_beetle_risk": s.bark_beetle_risk,
            "data_source": (s.data_source if isinstance(s.data_source, str) else s.data_source.value) if s.data_source else None,
            "field_verified": s.field_verified,
            "notes": s.notes,
            "geometry_geojson": geojson,
        })

    generator = PDFGenerator()
    pdf_bytes = generator.generate_plan_pdf(
        plan_dict, prop_dict, stands_list, property_geojson=prop_geojson
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="skogsbruksplan_{prop.designation.replace(" ", "_")}_{plan.version}.pdf"'
        },
    )
