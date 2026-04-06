"""Weather forecast, warnings, and smart alerts API routes."""

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
from app.models.stand import Stand
from app.models.user import User
from app.services.smhi_client import SmhiClient
from app.services.alerts_engine import AlertsEngine

router = APIRouter(prefix="/weather", tags=["weather"])

# Service singletons
_smhi_client = SmhiClient()
_alerts_engine = AlertsEngine()

FORECAST_CACHE_TTL = 1800   # 30 minutes
WARNINGS_CACHE_TTL = 900    # 15 minutes
ALERTS_CACHE_TTL = 600      # 10 minutes


# ── Response schemas ──────────────────────────────────────────

class WeatherSummary(BaseModel):
    max_wind_speed_ms: float
    max_wind_gust_ms: float
    min_temperature_c: float
    max_temperature_c: float
    total_precipitation_mm: float
    storm_risk: bool
    frost_risk: bool
    heavy_rain_risk: bool


class ForecastPoint(BaseModel):
    time: str
    temperature: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_gust: Optional[float] = None
    wind_direction: Optional[float] = None
    precipitation: Optional[float] = None
    humidity: Optional[float] = None
    cloud_cover: Optional[float] = None
    weather_symbol: Optional[int] = None


class ForecastResponse(BaseModel):
    latitude: float
    longitude: float
    approved_time: Optional[str] = None
    source: str
    forecast_hours: int
    forecasts: list[ForecastPoint]
    summary: WeatherSummary


class WarningItem(BaseModel):
    id: str
    event: str
    event_color: str
    severity: str
    urgency: str
    certainty: str
    district_code: str
    district_name: str
    description: str
    sent: str


class WarningsResponse(BaseModel):
    warnings: list[WarningItem]
    total_count: int


class AlertItem(BaseModel):
    severity: str       # critical, warning, info, success
    category: str       # storm, bark_beetle, harvesting, etc.
    title: str
    message: str
    affected_stands: list[Optional[int]]
    data: dict
    action: Optional[str] = None


class PropertyAlertsResponse(BaseModel):
    property_id: uuid.UUID
    alert_count: int
    critical_count: int
    warning_count: int
    alerts: list[AlertItem]
    weather_source: str


# ── Helpers ───────────────────────────────────────────────────

async def _get_property_centroid(
    property_id: uuid.UUID, db: AsyncSession, current_user: User
) -> tuple[Property, float, float]:
    """Get property and estimate its centroid in WGS84.

    Returns (property, latitude, longitude).
    Falls back to Sweden center if no geometry.
    """
    from sqlalchemy import func

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

    # Try to compute centroid from geometry
    lat, lon = 62.0, 15.5  # Default: center of Sweden

    if prop.geometry is not None:
        try:
            # Transform SWEREF99 TM → WGS84 and get centroid
            centroid_result = await db.execute(
                select(
                    func.ST_Y(func.ST_Transform(
                        func.ST_Centroid(prop.geometry), 4326
                    )).label("lat"),
                    func.ST_X(func.ST_Transform(
                        func.ST_Centroid(prop.geometry), 4326
                    )).label("lon"),
                )
            )
            row = centroid_result.one_or_none()
            if row and row.lat and row.lon:
                lat = round(row.lat, 6)
                lon = round(row.lon, 6)
        except Exception:
            pass  # Fall back to default

    return prop, lat, lon


async def _get_stands_for_property(
    property_id: uuid.UUID, db: AsyncSession
) -> list[dict]:
    """Fetch stands as dicts for alerts engine."""
    result = await db.execute(
        select(Stand)
        .where(Stand.property_id == property_id)
        .order_by(Stand.stand_number)
    )
    stands = result.scalars().all()

    return [
        {
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
            "target_class": s.target_class,
            "proposed_action": s.proposed_action,
            "action_urgency": s.action_urgency,
            "action_year": s.action_year,
            "bark_beetle_risk": s.bark_beetle_risk,
            "notes": s.notes,
        }
        for s in stands
    ]


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/forecast/{property_id}", response_model=ForecastResponse)
async def get_property_forecast(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get 48-hour weather forecast for a property's location."""

    prop, lat, lon = await _get_property_centroid(property_id, db, current_user)

    # Check cache
    cache_key = f"weather:forecast:{lat:.4f}:{lon:.4f}"
    cached = await cache_get(cache_key)
    if cached:
        try:
            return ForecastResponse(**json.loads(cached))
        except Exception:
            pass

    # Fetch from SMHI
    try:
        data = await _smhi_client.get_point_forecast(lat, lon)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Kunde inte hämta väderprognos: {str(e)}",
        )

    response = ForecastResponse(
        latitude=lat,
        longitude=lon,
        approved_time=data.get("approved_time"),
        source=data.get("source", "smhi"),
        forecast_hours=data.get("forecast_hours", 0),
        forecasts=[ForecastPoint(**f) for f in data.get("forecasts", [])],
        summary=WeatherSummary(**data.get("summary", {})),
    )

    # Cache response
    try:
        await cache_set(cache_key, response.model_dump_json(), ttl=FORECAST_CACHE_TTL)
    except Exception:
        pass

    return response


@router.get("/warnings", response_model=WarningsResponse)
async def get_weather_warnings(
    current_user: User = Depends(get_current_user),
):
    """Get all current SMHI weather warnings for Sweden."""

    # Check cache
    cache_key = "weather:warnings:all"
    cached = await cache_get(cache_key)
    if cached:
        try:
            return WarningsResponse(**json.loads(cached))
        except Exception:
            pass

    try:
        warnings_data = await _smhi_client.get_warnings()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Kunde inte hämta vädervarningar: {str(e)}",
        )

    warnings = [WarningItem(**w) for w in warnings_data]
    response = WarningsResponse(
        warnings=warnings,
        total_count=len(warnings),
    )

    try:
        await cache_set(cache_key, response.model_dump_json(), ttl=WARNINGS_CACHE_TTL)
    except Exception:
        pass

    return response


@router.get("/alerts/{property_id}", response_model=PropertyAlertsResponse)
async def get_property_alerts(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get smart, proactive alerts for a property.

    Combines weather data, stand data, season, and forestry rules
    to generate actionable recommendations.
    """

    prop, lat, lon = await _get_property_centroid(property_id, db, current_user)

    # Check cache
    cache_key = f"weather:alerts:{property_id}"
    cached = await cache_get(cache_key)
    if cached:
        try:
            return PropertyAlertsResponse(**json.loads(cached))
        except Exception:
            pass

    # Fetch stands and weather
    stands = await _get_stands_for_property(property_id, db)

    weather = None
    weather_source = "unavailable"
    try:
        weather = await _smhi_client.get_point_forecast(lat, lon)
        weather_source = weather.get("source", "smhi")
    except Exception:
        weather_source = "fallback"

    # Generate alerts
    alerts = _alerts_engine.generate_alerts(
        stands=stands,
        weather=weather,
        property_data={
            "designation": prop.designation,
            "total_area_ha": prop.total_area_ha,
            "productive_forest_ha": prop.productive_forest_ha,
        },
    )

    critical_count = sum(1 for a in alerts if a["severity"] == "critical")
    warning_count = sum(1 for a in alerts if a["severity"] == "warning")

    response = PropertyAlertsResponse(
        property_id=property_id,
        alert_count=len(alerts),
        critical_count=critical_count,
        warning_count=warning_count,
        alerts=[AlertItem(**a) for a in alerts],
        weather_source=weather_source,
    )

    try:
        await cache_set(cache_key, response.model_dump_json(), ttl=ALERTS_CACHE_TTL)
    except Exception:
        pass

    return response
