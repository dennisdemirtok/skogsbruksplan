"""Skogsstyrelsen API client for Skogliga grunddata v1.1.

Documentation: https://api.skogsstyrelsen.se/sksapi/swagger/index.html
Auth: OAuth2 client_credentials with scope sks_api at
      https://auth.skogsstyrelsen.se/connect/token

Endpoints (all POST, Bearer token required):
- /Volym          → virkesförråd (m³sk/ha)
- /Grundyta       → basal area (m²/ha)
- /Medelhojd      → mean height (m)
- /Medeldiameter  → mean diameter (cm)
- /Biomassa       → biomass
- /VolymFramskriven → forecasted volume

Request body (StatistikParameters):
  {
    "geometri": "MULTIPOLYGON (...)",   // WKT in SWEREF99 TM (EPSG:3006)
    "omdrev": 2 | null,                 // 1=2008-2016, 2=2018-2025, 3=2025+
    "pixelstorlek": 10 | null,          // meters; ≥10 for >100ha
    "marktyper": ["ProduktivSkogsmark"]
  }
"""

import asyncio
import logging
import time
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 45.0
MAX_RETRIES = 3

# In-process token cache (per-worker)
_token_cache: dict = {
    "access_token": None,
    "expires_at": 0,
}


class SkogsstyrelsenClient:
    def __init__(self):
        self.base_url = settings.SKOGSSTYRELSEN_API_BASE.rstrip("/")
        self.token_url = settings.SKOGSSTYRELSEN_TOKEN_URL
        self.scope = settings.SKOGSSTYRELSEN_SCOPE
        self.client_id = settings.SKOGSSTYRELSEN_CLIENT_ID
        self.client_secret = settings.SKOGSSTYRELSEN_CLIENT_SECRET
        self.timeout = DEFAULT_TIMEOUT

    async def _get_access_token(self) -> Optional[str]:
        """Fetch OAuth2 access token, cached in-process with 60s safety margin."""
        if not self.client_id or not self.client_secret:
            logger.warning("Skogsstyrelsen credentials not configured")
            return None

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
                        "scope": self.scope,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                if response.status_code == 200:
                    data = response.json()
                    token = data.get("access_token")
                    expires_in = int(data.get("expires_in", 3600))
                    _token_cache["access_token"] = token
                    _token_cache["expires_at"] = now + expires_in
                    logger.info(
                        f"Skogsstyrelsen token acquired (expires in {expires_in}s)"
                    )
                    return token
                else:
                    logger.error(
                        f"Token request failed: HTTP {response.status_code} - {response.text[:200]}"
                    )
                    return None
        except Exception as e:
            logger.error(f"Error fetching Skogsstyrelsen token: {e}")
            return None

    async def _post(self, endpoint: str, body: dict) -> Optional[dict]:
        """POST to the API with bearer token; retry once on 401."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        token = await self._get_access_token()
        if not token:
            return None
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        last_exception = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=body, headers=headers)

                if response.status_code == 200:
                    return response.json()
                if response.status_code == 401 and attempt == 1:
                    logger.warning("401 from Skogsstyrelsen — refreshing token")
                    _token_cache["access_token"] = None
                    _token_cache["expires_at"] = 0
                    token = await self._get_access_token()
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                    continue
                if response.status_code in (400, 422):
                    logger.warning(
                        f"Bad request to {endpoint}: HTTP {response.status_code} - {response.text[:300]}"
                    )
                    return None
                if response.status_code == 404:
                    return None
                if response.status_code >= 500:
                    logger.warning(
                        f"Server error {response.status_code} from {endpoint} "
                        f"(attempt {attempt}/{MAX_RETRIES})"
                    )
                    last_exception = httpx.HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    continue
                logger.error(
                    f"Unexpected {response.status_code} from {endpoint}: {response.text[:200]}"
                )
                return None

            except httpx.TimeoutException as e:
                logger.warning(f"Timeout on {endpoint} (attempt {attempt}/{MAX_RETRIES}): {e}")
                last_exception = e
            except httpx.ConnectError as e:
                logger.warning(f"Connection error on {endpoint}: {e}")
                last_exception = e

        if last_exception:
            logger.error(f"All retries failed for {endpoint}: {last_exception}")
        return None

    @staticmethod
    def _extract_value(
        response: Optional[dict], marktyp: str, field: str
    ) -> Optional[float]:
        """Extract a numeric field from {data: {Marktyp: {field: value}}}."""
        if not response:
            return None
        data = response.get("data") or {}
        mark_data = data.get(marktyp) or {}
        v = mark_data.get(field)
        try:
            return float(v) if v is not None else None
        except (ValueError, TypeError):
            return None

    async def get_forest_data(
        self,
        geometry_wkt: str,
        area_ha: Optional[float] = None,
        marktyp: str = "ProduktivSkogsmark",
    ) -> dict:
        """Fetch all forest statistics for a stand polygon (WKT in SWEREF99 TM).

        Makes 4 parallel API calls (Volym, Grundyta, Medelhojd, Medeldiameter)
        and returns a flat dict ready to populate a Stand record.

        Returns {} if credentials missing or all calls fail.
        """
        if not self.client_id or not self.client_secret:
            return {}

        # Pick pixel size: 10m for larger areas reduces edge effects and API load
        pixelstorlek = 10 if area_ha and area_ha > 100 else None

        body = {
            "geometri": geometry_wkt,
            "marktyper": [marktyp],
        }
        if pixelstorlek is not None:
            body["pixelstorlek"] = pixelstorlek

        # Fire all four requests in parallel
        volym_task = self._post("/Volym", body)
        grundyta_task = self._post("/Grundyta", body)
        hojd_task = self._post("/Medelhojd", body)
        diam_task = self._post("/Medeldiameter", body)

        volym, grundyta, hojd, diam = await asyncio.gather(
            volym_task, grundyta_task, hojd_task, diam_task,
            return_exceptions=True,
        )

        # Replace exceptions with None
        def safe(r):
            return r if isinstance(r, dict) or r is None else None

        volym = safe(volym)
        grundyta = safe(grundyta)
        hojd = safe(hojd)
        diam = safe(diam)

        result = {
            "volume_m3_per_ha": self._extract_value(volym, marktyp, "medel"),
            "total_volume_m3": self._extract_value(volym, marktyp, "total"),
            "basal_area_m2": self._extract_value(grundyta, marktyp, "medel"),
            "mean_height_m": self._extract_value(hojd, marktyp, "medel"),
            "mean_diameter_cm": self._extract_value(diam, marktyp, "medel"),
            "productive_area_ha": self._extract_value(volym, marktyp, "arealHa"),
        }

        if volym:
            meta = (volym.get("metadata") or {})
            result["_omdrev"] = meta.get("omdrev")
            result["_scan_date"] = meta.get("maxDatum")

        return result

    async def get_bark_beetle_risk(self, polygon_geojson: dict) -> dict:
        """Not exposed by Skogliga grunddata v1.1 — use separate Äbin/Nemus API."""
        return {
            "source": "unavailable",
            "data": {"risk_index": None, "risk_level": "unknown"},
        }
