import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3


class SkogsstyrelsenClient:
    def __init__(self):
        self.base_url = settings.SKOGSSTYRELSEN_API_BASE
        self.timeout = DEFAULT_TIMEOUT

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
    ) -> dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        last_exception = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if method.upper() == "GET":
                        response = await client.get(url, params=params)
                    elif method.upper() == "POST":
                        response = await client.post(
                            url, params=params, json=json_body
                        )
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 404:
                        logger.warning(
                            f"Resource not found at {url}: {response.status_code}"
                        )
                        return {}
                    elif response.status_code >= 500:
                        logger.warning(
                            f"Server error from Skogsstyrelsen API (attempt {attempt}/{MAX_RETRIES}): "
                            f"{response.status_code}"
                        )
                        last_exception = httpx.HTTPStatusError(
                            f"HTTP {response.status_code}",
                            request=response.request,
                            response=response,
                        )
                        continue
                    else:
                        response.raise_for_status()

            except httpx.TimeoutException as e:
                logger.warning(
                    f"Timeout calling Skogsstyrelsen API (attempt {attempt}/{MAX_RETRIES}): {e}"
                )
                last_exception = e
                continue
            except httpx.ConnectError as e:
                logger.warning(
                    f"Connection error to Skogsstyrelsen API (attempt {attempt}/{MAX_RETRIES}): {e}"
                )
                last_exception = e
                continue
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error from Skogsstyrelsen API: {e}")
                raise

        if last_exception:
            raise last_exception
        return {}

    async def get_forest_data(self, polygon_geojson: dict) -> dict:
        request_body = {
            "type": "Feature",
            "geometry": polygon_geojson,
            "properties": {},
        }

        try:
            result = await self._make_request(
                "POST",
                "/skogligagrunddata",
                json_body=request_body,
            )
        except Exception as e:
            logger.error(f"Failed to fetch forest data from Skogsstyrelsen: {e}")
            result = self._get_fallback_forest_data()

        return result

    async def get_bark_beetle_risk(self, polygon_geojson: dict) -> dict:
        request_body = {
            "type": "Feature",
            "geometry": polygon_geojson,
            "properties": {},
        }

        try:
            result = await self._make_request(
                "POST",
                "/granbarkborre/risk",
                json_body=request_body,
            )
        except Exception as e:
            logger.error(f"Failed to fetch bark beetle risk data: {e}")
            result = self._get_fallback_bark_beetle_data()

        return result

    def _get_fallback_forest_data(self) -> dict:
        return {
            "source": "fallback",
            "message": "Skogsstyrelsen API ej tillgängligt. Använder uppskattade värden.",
            "data": {
                "volume_m3_per_ha": None,
                "mean_height_m": None,
                "basal_area_m2": None,
                "mean_diameter_cm": None,
                "age_years": None,
                "site_index": None,
                "species_distribution": {
                    "pine_pct": None,
                    "spruce_pct": None,
                    "deciduous_pct": None,
                    "contorta_pct": None,
                },
            },
        }

    def _get_fallback_bark_beetle_data(self) -> dict:
        return {
            "source": "fallback",
            "message": "Skogsstyrelsen API ej tillgängligt. Granbarkborreriskdata saknas.",
            "data": {
                "risk_index": None,
                "risk_level": "unknown",
                "description": "Riskdata kunde inte hämtas från Skogsstyrelsen.",
            },
        }
