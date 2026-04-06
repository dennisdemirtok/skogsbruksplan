import uuid
from collections import defaultdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.property import Property
from app.models.stand import Stand
from app.models.user import User
from app.services.action_engine import ActionEngine
from app.services.economic_calculator import EconomicCalculator

router = APIRouter(prefix="/properties", tags=["analytics"])

# ---------------------------------------------------------------------------
# Service singletons
# ---------------------------------------------------------------------------
_economic_calculator = EconomicCalculator()
_action_engine = ActionEngine()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class StandEconomics(BaseModel):
    stand_id: uuid.UUID
    stand_number: int
    area_ha: float
    timber_volume_m3: float
    pulpwood_volume_m3: float
    gross_value_sek: float
    harvesting_cost_sek: float
    net_value_sek: float
    npv_10yr: float

    model_config = {"from_attributes": True}


class ActionsByYear(BaseModel):
    year: int
    action: str
    stand_count: int
    total_area_ha: float
    total_net_value_sek: float


class EconomicSummaryResponse(BaseModel):
    property_id: uuid.UUID
    total_timber_volume_m3: float
    total_pulpwood_volume_m3: float
    total_gross_value_sek: float
    total_harvesting_cost_sek: float
    total_net_value_sek: float
    total_npv_10yr: float
    stand_economics: list[StandEconomics]
    actions_by_year: list[ActionsByYear]


class StandAction(BaseModel):
    stand_id: uuid.UUID
    stand_number: int
    area_ha: float
    age_years: Optional[int] = None
    site_index: Optional[float] = None
    volume_m3_per_ha: Optional[float] = None
    target_class: Optional[str] = None
    action: str
    urgency: int
    reasoning: str
    action_year: Optional[int] = None
    timber_volume_m3: float
    pulpwood_volume_m3: float
    net_value_sek: float

    model_config = {"from_attributes": True}


class ActionsResponse(BaseModel):
    property_id: uuid.UUID
    total_stands: int
    stands_with_actions: int
    actions: list[StandAction]


class SpeciesDistribution(BaseModel):
    pine_pct: float
    spruce_pct: float
    deciduous_pct: float
    contorta_pct: float


class AgeClassDistribution(BaseModel):
    age_class: str
    area_ha: float
    stand_count: int


class TargetClassDistribution(BaseModel):
    target_class: str
    area_ha: float
    stand_count: int


class PropertySummaryResponse(BaseModel):
    property_id: uuid.UUID
    designation: str
    total_area_ha: float
    productive_forest_ha: float
    stand_count: int
    total_volume_m3sk: float
    mean_volume_per_ha: float
    mean_age_years: float
    mean_site_index: float
    species_distribution: SpeciesDistribution
    age_class_distribution: list[AgeClassDistribution]
    target_class_distribution: list[TargetClassDistribution]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _verify_property_access(
    property_id: uuid.UUID,
    db: AsyncSession,
    current_user: User,
) -> Property:
    """Load a property and verify that the current user has access."""
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
    return prop


async def _get_stands_for_property(
    property_id: uuid.UUID,
    db: AsyncSession,
) -> list[Stand]:
    """Fetch all stands belonging to a property, ordered by stand_number."""
    result = await db.execute(
        select(Stand)
        .where(Stand.property_id == property_id)
        .order_by(Stand.stand_number)
    )
    return list(result.scalars().all())


def _stand_to_data_dict(stand: Stand) -> dict:
    """Convert a Stand ORM object to a plain dict for service consumption."""
    return {
        "area_ha": stand.area_ha or 0,
        "volume_m3_per_ha": stand.volume_m3_per_ha,
        "mean_height_m": stand.mean_height_m,
        "basal_area_m2": stand.basal_area_m2,
        "mean_diameter_cm": stand.mean_diameter_cm,
        "age_years": stand.age_years,
        "site_index": stand.site_index,
        "pine_pct": stand.pine_pct,
        "spruce_pct": stand.spruce_pct,
        "deciduous_pct": stand.deciduous_pct,
        "contorta_pct": stand.contorta_pct,
        "target_class": stand.target_class,
        "bark_beetle_risk": stand.bark_beetle_risk,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/{property_id}/economics",
    response_model=EconomicSummaryResponse,
)
async def get_property_economics(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Economic summary for a property: timber values, logging costs,
    net values aggregated across all stands, with per-year action grouping."""

    prop = await _verify_property_access(property_id, db, current_user)
    stands = await _get_stands_for_property(property_id, db)

    total_timber = 0.0
    total_pulpwood = 0.0
    total_gross = 0.0
    total_harvesting = 0.0
    total_net = 0.0
    total_npv = 0.0
    stand_economics_list: list[StandEconomics] = []

    # For grouping by action year
    year_groups: dict[tuple[int, str], dict] = defaultdict(
        lambda: {"stand_count": 0, "total_area_ha": 0.0, "total_net_value_sek": 0.0}
    )

    current_year = datetime.now().year

    for stand in stands:
        data = _stand_to_data_dict(stand)
        econ = _economic_calculator.calculate_stand_economics(data)
        action_result = _action_engine.propose_action(data)

        timber = econ["timber_volume_m3"]
        pulpwood = econ["pulpwood_volume_m3"]
        gross = econ["gross_value_sek"]
        harvesting = econ["harvesting_cost_sek"]
        net = econ["net_value_sek"]
        npv = econ.get("npv_10yr", 0)

        total_timber += timber
        total_pulpwood += pulpwood
        total_gross += gross
        total_harvesting += harvesting
        total_net += net
        total_npv += npv

        stand_economics_list.append(
            StandEconomics(
                stand_id=stand.id,
                stand_number=stand.stand_number,
                area_ha=stand.area_ha or 0,
                timber_volume_m3=timber,
                pulpwood_volume_m3=pulpwood,
                gross_value_sek=gross,
                harvesting_cost_sek=harvesting,
                net_value_sek=net,
                npv_10yr=npv,
            )
        )

        # Group by action year
        action = action_result["action"]
        action_year = stand.action_year if stand.action_year else current_year
        key = (action_year, action)
        year_groups[key]["stand_count"] += 1
        year_groups[key]["total_area_ha"] += stand.area_ha or 0
        year_groups[key]["total_net_value_sek"] += net

    actions_by_year = sorted(
        [
            ActionsByYear(
                year=year,
                action=action,
                stand_count=info["stand_count"],
                total_area_ha=round(info["total_area_ha"], 2),
                total_net_value_sek=round(info["total_net_value_sek"], 0),
            )
            for (year, action), info in year_groups.items()
        ],
        key=lambda x: (x.year, x.action),
    )

    return EconomicSummaryResponse(
        property_id=property_id,
        total_timber_volume_m3=round(total_timber, 1),
        total_pulpwood_volume_m3=round(total_pulpwood, 1),
        total_gross_value_sek=round(total_gross, 0),
        total_harvesting_cost_sek=round(total_harvesting, 0),
        total_net_value_sek=round(total_net, 0),
        total_npv_10yr=round(total_npv, 0),
        stand_economics=stand_economics_list,
        actions_by_year=actions_by_year,
    )


@router.get(
    "/{property_id}/actions",
    response_model=ActionsResponse,
)
async def get_property_actions(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Proposed management actions for every stand in the property,
    including economic data per stand."""

    prop = await _verify_property_access(property_id, db, current_user)
    stands = await _get_stands_for_property(property_id, db)

    actions_list: list[StandAction] = []
    stands_with_actions = 0

    for stand in stands:
        data = _stand_to_data_dict(stand)
        action_result = _action_engine.propose_action(data)
        econ = _economic_calculator.calculate_stand_economics(data)

        action = action_result["action"]
        if action != "ingen":
            stands_with_actions += 1

        actions_list.append(
            StandAction(
                stand_id=stand.id,
                stand_number=stand.stand_number,
                area_ha=stand.area_ha or 0,
                age_years=stand.age_years,
                site_index=stand.site_index,
                volume_m3_per_ha=stand.volume_m3_per_ha,
                target_class=stand.target_class,
                action=action,
                urgency=action_result["urgency"],
                reasoning=action_result["reasoning"],
                action_year=stand.action_year,
                timber_volume_m3=econ["timber_volume_m3"],
                pulpwood_volume_m3=econ["pulpwood_volume_m3"],
                net_value_sek=econ["net_value_sek"],
            )
        )

    return ActionsResponse(
        property_id=property_id,
        total_stands=len(stands),
        stands_with_actions=stands_with_actions,
        actions=actions_list,
    )


@router.get(
    "/{property_id}/summary",
    response_model=PropertySummaryResponse,
)
async def get_property_summary(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Property summary statistics: total area, stand count, total volume,
    species distribution, age distribution, target class distribution."""

    prop = await _verify_property_access(property_id, db, current_user)
    stands = await _get_stands_for_property(property_id, db)

    total_area = 0.0
    total_volume = 0.0
    weighted_age_sum = 0.0
    weighted_si_sum = 0.0
    area_with_age = 0.0
    area_with_si = 0.0

    # Species: area-weighted
    weighted_pine = 0.0
    weighted_spruce = 0.0
    weighted_deciduous = 0.0
    weighted_contorta = 0.0

    # Age class bins (Swedish standard 20-year classes)
    age_classes: dict[str, dict] = defaultdict(
        lambda: {"area_ha": 0.0, "stand_count": 0}
    )

    # Target class bins
    target_classes: dict[str, dict] = defaultdict(
        lambda: {"area_ha": 0.0, "stand_count": 0}
    )

    for stand in stands:
        area = stand.area_ha or 0
        total_area += area

        vol_per_ha = stand.volume_m3_per_ha or 0
        total_volume += vol_per_ha * area

        if stand.age_years is not None and area > 0:
            weighted_age_sum += stand.age_years * area
            area_with_age += area

        if stand.site_index is not None and area > 0:
            weighted_si_sum += stand.site_index * area
            area_with_si += area

        # Area-weighted species
        weighted_pine += (stand.pine_pct or 0) * area
        weighted_spruce += (stand.spruce_pct or 0) * area
        weighted_deciduous += (stand.deciduous_pct or 0) * area
        weighted_contorta += (stand.contorta_pct or 0) * area

        # Age class
        age = stand.age_years
        if age is not None:
            age_label = _age_class_label(age)
        else:
            age_label = "Okänd"
        age_classes[age_label]["area_ha"] += area
        age_classes[age_label]["stand_count"] += 1

        # Target class
        tc = stand.target_class or "PG"
        target_classes[tc]["area_ha"] += area
        target_classes[tc]["stand_count"] += 1

    mean_age = (weighted_age_sum / area_with_age) if area_with_age > 0 else 0
    mean_si = (weighted_si_sum / area_with_si) if area_with_si > 0 else 0
    mean_vol = (total_volume / total_area) if total_area > 0 else 0

    species = SpeciesDistribution(
        pine_pct=round(weighted_pine / total_area, 1) if total_area > 0 else 0,
        spruce_pct=round(weighted_spruce / total_area, 1) if total_area > 0 else 0,
        deciduous_pct=round(weighted_deciduous / total_area, 1) if total_area > 0 else 0,
        contorta_pct=round(weighted_contorta / total_area, 1) if total_area > 0 else 0,
    )

    # Sort age classes by the natural age order
    age_order = [
        "0-20", "21-40", "41-60", "61-80", "81-100",
        "101-120", "121-140", "141+", "Okänd",
    ]
    age_dist = []
    for label in age_order:
        if label in age_classes:
            info = age_classes[label]
            age_dist.append(
                AgeClassDistribution(
                    age_class=label,
                    area_ha=round(info["area_ha"], 2),
                    stand_count=info["stand_count"],
                )
            )

    # Sort target classes: PG, PF, NS, NO
    tc_order = ["PG", "PF", "NS", "NO"]
    tc_dist = []
    for tc in tc_order:
        if tc in target_classes:
            info = target_classes[tc]
            tc_dist.append(
                TargetClassDistribution(
                    target_class=tc,
                    area_ha=round(info["area_ha"], 2),
                    stand_count=info["stand_count"],
                )
            )
    # Include any unexpected target classes not in the standard order
    for tc, info in target_classes.items():
        if tc not in tc_order:
            tc_dist.append(
                TargetClassDistribution(
                    target_class=tc,
                    area_ha=round(info["area_ha"], 2),
                    stand_count=info["stand_count"],
                )
            )

    return PropertySummaryResponse(
        property_id=property_id,
        designation=prop.designation,
        total_area_ha=round(prop.total_area_ha or total_area, 2),
        productive_forest_ha=round(prop.productive_forest_ha or total_area, 2),
        stand_count=len(stands),
        total_volume_m3sk=round(total_volume, 1),
        mean_volume_per_ha=round(mean_vol, 1),
        mean_age_years=round(mean_age, 1),
        mean_site_index=round(mean_si, 1),
        species_distribution=species,
        age_class_distribution=age_dist,
        target_class_distribution=tc_dist,
    )


def _age_class_label(age: int) -> str:
    """Return the Swedish-standard 20-year age class label."""
    if age <= 20:
        return "0-20"
    elif age <= 40:
        return "21-40"
    elif age <= 60:
        return "41-60"
    elif age <= 80:
        return "61-80"
    elif age <= 100:
        return "81-100"
    elif age <= 120:
        return "101-120"
    elif age <= 140:
        return "121-140"
    else:
        return "141+"
