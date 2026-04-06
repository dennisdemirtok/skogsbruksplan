"""SMHI Open Data API client for weather forecasts and warnings.

SMHI (Swedish Meteorological and Hydrological Institute) provides free
open data APIs for weather forecasts and weather warnings across Sweden.

- Forecast API: Point forecasts using the PMP3g model (~2.8 km grid)
- Warnings API: Impact-Based Weather Warnings (IBWW)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15.0
MAX_RETRIES = 2


class SmhiClient:
    """Async client for SMHI open data APIs."""

    def __init__(self) -> None:
        self.forecast_base = settings.SMHI_FORECAST_BASE
        self.warnings_base = settings.SMHI_WARNINGS_BASE
        self.timeout = DEFAULT_TIMEOUT

    # ── Forecast API ──────────────────────────────────────────────

    async def get_point_forecast(
        self, latitude: float, longitude: float
    ) -> dict:
        """Fetch point weather forecast from SMHI PMP3g model.

        Returns a simplified dict with the next 48h of forecast data,
        including temperature, wind speed, wind direction, precipitation,
        and weather symbol.

        Args:
            latitude: WGS84 latitude (e.g. 62.5)
            longitude: WGS84 longitude (e.g. 16.0)
        """
        # SMHI expects max 6 decimal places
        lat = round(latitude, 6)
        lon = round(longitude, 6)
        url = (
            f"{self.forecast_base}/geotype/point"
            f"/lon/{lon}/lat/{lat}/data.json"
        )

        data = await self._get_json(url)
        if not data:
            return self._fallback_forecast()

        return self._parse_forecast(data)

    def _parse_forecast(self, raw: dict) -> dict:
        """Parse SMHI PMP3g response into a clean forecast dict."""
        time_series = raw.get("timeSeries", [])
        approved = raw.get("approvedTime", "")
        ref_time = raw.get("referenceTime", "")
        geometry = raw.get("geometry", {})

        # Extract up to 48 hours of forecast data
        forecasts = []
        for ts in time_series[:48]:  # ~48 hours at 1h intervals
            valid_time = ts.get("validTime", "")
            params = {}
            for p in ts.get("parameters", []):
                name = p.get("name")
                values = p.get("values", [])
                if values:
                    params[name] = values[0]

            forecasts.append({
                "time": valid_time,
                "temperature": params.get("t"),        # °C
                "wind_speed": params.get("ws"),        # m/s
                "wind_gust": params.get("gust"),       # m/s
                "wind_direction": params.get("wd"),    # degrees
                "precipitation": params.get("pmean"),  # mm/h (mean)
                "humidity": params.get("r"),           # %
                "pressure": params.get("msl"),         # hPa
                "visibility": params.get("vis"),       # km
                "cloud_cover": params.get("tcc_mean"), # octas (0-8)
                "weather_symbol": params.get("Wsymb2"), # SMHI weather symbol code
            })

        # Compute summary stats for alerts
        if forecasts:
            max_wind = max((f["wind_speed"] or 0) for f in forecasts)
            max_gust = max((f["wind_gust"] or 0) for f in forecasts)
            min_temp = min((f["temperature"] or 0) for f in forecasts)
            max_temp = max((f["temperature"] or 0) for f in forecasts)
            total_precip = sum((f["precipitation"] or 0) for f in forecasts)
        else:
            max_wind = max_gust = min_temp = max_temp = total_precip = 0

        return {
            "approved_time": approved,
            "reference_time": ref_time,
            "coordinates": geometry.get("coordinates", []),
            "source": "smhi",
            "forecast_hours": len(forecasts),
            "forecasts": forecasts,
            "summary": {
                "max_wind_speed_ms": max_wind,
                "max_wind_gust_ms": max_gust,
                "min_temperature_c": min_temp,
                "max_temperature_c": max_temp,
                "total_precipitation_mm": round(total_precip, 1),
                "storm_risk": max_gust >= 21,       # Kulingvarning >= 21 m/s
                "frost_risk": min_temp < -10,
                "heavy_rain_risk": total_precip > 30,
            },
        }

    def _fallback_forecast(self) -> dict:
        """Return empty forecast structure when API is unavailable."""
        return {
            "approved_time": None,
            "reference_time": None,
            "coordinates": [],
            "source": "fallback",
            "forecast_hours": 0,
            "forecasts": [],
            "summary": {
                "max_wind_speed_ms": 0,
                "max_wind_gust_ms": 0,
                "min_temperature_c": 0,
                "max_temperature_c": 0,
                "total_precipitation_mm": 0,
                "storm_risk": False,
                "frost_risk": False,
                "heavy_rain_risk": False,
            },
        }

    # ── Warnings API ──────────────────────────────────────────────

    async def get_warnings(self) -> list[dict]:
        """Fetch all current weather warnings from SMHI.

        Returns a list of active warnings with severity, event type,
        and affected areas.
        """
        url = f"{self.warnings_base}/warning.json"
        raw = await self._get_json(url)
        if not raw:
            return []

        return self._parse_warnings(raw)

    def _parse_warnings(self, raw) -> list[dict]:
        """Parse SMHI IBWW v1 warnings response into a clean list.

        The IBWW API returns a flat list of warning objects, each with
        nested event, warningAreas, and affectedAreas structures.
        """
        warnings = []

        # IBWW v1 returns a list at top level
        items = raw if isinstance(raw, list) else []

        for item in items:
            event_data = item.get("event", {})
            event_name = event_data.get("sv", "") if isinstance(event_data, dict) else str(event_data)
            event_code = event_data.get("code", "") if isinstance(event_data, dict) else ""

            # Each warning can have multiple warningAreas
            warning_areas = item.get("warningAreas", [])
            if not warning_areas:
                # No areas – skip or add a single entry
                continue

            for area in warning_areas:
                level_data = area.get("warningLevel", {})
                level_sv = level_data.get("sv", "") if isinstance(level_data, dict) else str(level_data)
                level_code = level_data.get("code", "") if isinstance(level_data, dict) else ""

                # Map SMHI level codes to severity
                severity_map = {
                    "RED": "Extreme",
                    "ORANGE": "Severe",
                    "YELLOW": "Moderate",
                    "MESSAGE": "Minor",
                }
                severity = severity_map.get(level_code, level_sv)

                # Color from level code
                color_map = {
                    "RED": "red",
                    "ORANGE": "orange",
                    "YELLOW": "yellow",
                    "MESSAGE": "green",
                }
                event_color = color_map.get(level_code, "gray")

                # Build area description
                area_name = area.get("areaName", {})
                area_sv = area_name.get("sv", "") if isinstance(area_name, dict) else str(area_name)

                # Affected counties
                affected = area.get("affectedAreas", [])
                district_names = [a.get("sv", "") for a in affected if isinstance(a, dict)]

                # Event description (more specific than the event)
                evt_desc = area.get("eventDescription", {})
                description = evt_desc.get("sv", "") if isinstance(evt_desc, dict) else str(evt_desc)

                warnings.append({
                    "id": str(item.get("id", "")),
                    "event": event_name,
                    "event_color": event_color,
                    "severity": severity,
                    "urgency": "Immediate" if level_code in ("RED", "ORANGE") else "Expected",
                    "certainty": "Observed" if not item.get("normalProbability") else "Likely",
                    "district_code": str(area.get("id", "")),
                    "district_name": ", ".join(district_names[:3]) + ("..." if len(district_names) > 3 else ""),
                    "description": description or area_sv,
                    "sent": area.get("published", ""),
                })

        return warnings

    # ── HTTP helper ───────────────────────────────────────────────

    async def _get_json(self, url: str) -> Optional[dict | list]:
        """Make a GET request with retry logic. Returns None on failure."""
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(url)

                    if resp.status_code == 200:
                        return resp.json()
                    elif resp.status_code >= 500:
                        logger.warning(
                            f"SMHI API server error (attempt {attempt}/{MAX_RETRIES}): "
                            f"{resp.status_code} from {url}"
                        )
                        last_error = f"HTTP {resp.status_code}"
                        continue
                    else:
                        logger.warning(
                            f"SMHI API error: {resp.status_code} from {url}"
                        )
                        return None

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                logger.warning(
                    f"SMHI API connection error (attempt {attempt}/{MAX_RETRIES}): {exc}"
                )
                last_error = str(exc)
                continue
            except Exception as exc:
                logger.error(f"Unexpected error calling SMHI API: {exc}")
                return None

        logger.error(f"SMHI API failed after {MAX_RETRIES} retries: {last_error}")
        return None
