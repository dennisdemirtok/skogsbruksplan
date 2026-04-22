import logging
import time
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3

# Simple in-process token cache
_token_cache: dict = {
    "access_token": None,
    "expires_at": 0,
}


class SkogsstyrelsenClient:
    def __init__(self):
        self.base_url = settings.SKOGSSTYRELSEN_API_BASE
        self.token_url = settings.SKOGSSTYRELSEN_TOKEN_URL
        self.client_id = settings.SKOGSSTYRELSEN_CLIENT_ID
        self.client_secret = settings.SKOGSSTYRELSEN_CLIENT_SECRET
        self.timeout = DEFAULT_TIMEOUT

    async def _get_access_token(self) -> Optional[str]:
        """Fetch OAuth2 access token using client credentials, cached in-process."""
        if not self.client_id or not self.client_secret:
            logger.warning("Skogsstyrelsen credentials not configured")
            return None

        # Reuse cached token if still valid (with 60s safety margin)
        now = time.time()
        if (
            _token_cache["access_token"]
            and _token_cache["expires_at"] > now + 60
        ):
            return _token_cache["access_token"]

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                if response.status_code == 200:
                    data = response.json()
                    token = data.get("access_token")
                    expires_in = data.get("expires_in", 3600)
                    _token_cache["access_token"] = token
                    _token_cache["expires_at"] = now + expires_in
                    logger.info(
                        f"Got Skogsstyrelsen access token (expires in {expires_in}s)"
                    )
                    return token
                else:
                    logger.error(
                        f"Failed to get token: HTTP {response.status_code} - {response.text[:200]}"
                    )
                    return None
        except Exception as e:
            logger.error(f"Error fetching Skogsstyrelsen token: {e}")
            return None

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
    ) -> dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        last_exception = None

        # Get auth token
        token = await self._get_access_token()
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if method.upper() == "GET":
                        response = await client.get(url, params=params, headers=headers)
                    elif method.upper() == "POST":
                        response = await client.post(
                            url, params=params, json=json_body, headers=headers
                        )
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 401:
                        # Token might have expired; clear cache and retry once
                        logger.warning("Got 401 from Skogsstyrelsen, refreshing token")
                        _token_cache["access_token"] = None
                        _token_cache["expires_at"] = 0
                        token = await self._get_access_token()
                        if token:
                            headers["Authorization"] = f"Bearer {token}"
                        continue
                    elif response.status_code == 403:
                        logger.error(
                            f"Skogsstyrelsen API 403 Forbidden: {response.text[:200]}"
                        )
                        return {}
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
                        logger.error(
                            f"Unexpected status {response.status_code} from Skogsstyrelsen: {response.text[:200]}"
                        )
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
