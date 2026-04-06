import logging
import math
import re
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# Approximate WGS84 center coordinates (lon, lat) for Swedish municipalities
# Used for generating geographically accurate mock property locations
MUNICIPALITY_COORDS: dict[str, tuple[float, float]] = {
    # Västernorrland
    "Sollefteå": (17.27, 63.17),
    "Örnsköldsvik": (18.71, 63.29),
    "Härnösand": (17.94, 62.63),
    "Sundsvall": (17.31, 62.39),
    "Kramfors": (17.78, 62.93),
    "Ånge": (15.66, 62.52),
    "Timrå": (17.33, 62.49),
    # Västerbotten
    "Umeå": (20.26, 63.83),
    "Skellefteå": (20.95, 64.75),
    "Lycksele": (18.67, 64.60),
    "Vindeln": (19.72, 64.20),
    "Robertsfors": (20.85, 64.19),
    "Nordmaling": (19.50, 63.57),
    "Vilhelmina": (16.66, 64.62),
    "Storuman": (17.11, 64.96),
    "Dorotea": (16.40, 64.26),
    "Åsele": (17.35, 64.16),
    "Vännäs": (19.77, 63.91),
    "Bjurholm": (19.05, 63.93),
    "Norsjö": (19.48, 64.91),
    "Malå": (18.74, 65.18),
    "Sorsele": (17.53, 65.53),
    # Norrbotten
    "Luleå": (22.15, 65.58),
    "Piteå": (21.48, 65.32),
    "Boden": (21.69, 66.00),
    "Gällivare": (20.65, 67.13),
    "Kiruna": (20.23, 67.86),
    "Jokkmokk": (19.83, 66.61),
    "Kalix": (23.16, 65.85),
    "Haparanda": (24.14, 65.84),
    "Älvsbyn": (20.99, 65.68),
    "Överkalix": (22.84, 66.33),
    "Övertorneå": (23.64, 66.39),
    "Pajala": (23.37, 67.21),
    "Arvidsjaur": (19.18, 65.59),
    "Arjeplog": (17.89, 66.05),
    # Jämtland
    "Östersund": (14.64, 63.18),
    "Krokom": (14.46, 63.33),
    "Strömsund": (15.55, 63.85),
    "Berg": (14.85, 63.15),
    "Åre": (13.08, 63.40),
    "Bräcke": (15.42, 62.75),
    "Ragunda": (16.15, 63.08),
    "Härjedalen": (14.10, 62.10),
    # Dalarna
    "Falun": (15.63, 60.61),
    "Mora": (14.55, 61.00),
    "Borlänge": (15.44, 60.49),
    "Ludvika": (15.19, 60.15),
    "Avesta": (16.17, 60.15),
    "Rättvik": (15.12, 61.09),
    "Leksand": (14.99, 60.73),
    "Gagnef": (15.11, 60.59),
    "Vansbro": (14.28, 60.89),
    "Malung-Sälen": (13.72, 61.00),
    "Orsa": (14.62, 61.12),
    "Älvdalen": (14.04, 61.23),
    # Gävleborg
    "Gävle": (17.14, 60.67),
    "Hudiksvall": (17.10, 61.73),
    "Söderhamn": (17.06, 61.30),
    "Sandviken": (16.78, 60.62),
    "Bollnäs": (16.39, 61.35),
    "Ljusdal": (16.09, 61.83),
    "Ockelbo": (16.74, 60.89),
    "Nordanstig": (17.18, 62.06),
    "Ovanåker": (16.32, 61.36),
    "Hofors": (16.29, 60.56),
    # Värmland
    "Karlstad": (13.50, 59.38),
    "Torsby": (13.00, 60.14),
    "Sunne": (13.15, 59.83),
    "Filipstad": (14.17, 59.71),
    "Hagfors": (13.66, 60.03),
    "Arvika": (12.58, 59.65),
    # Västmanland
    "Västerås": (16.54, 59.61),
    "Sala": (16.60, 59.92),
    "Fagersta": (15.79, 60.00),
    "Skinnskatteberg": (15.69, 59.83),
    # Örebro
    "Örebro": (15.21, 59.27),
    "Karlskoga": (14.53, 59.33),
    "Lindesberg": (15.23, 59.59),
    "Hällefors": (14.52, 59.78),
    "Ljusnarsberg": (14.87, 59.93),
    "Nora": (15.04, 59.52),
    # Östergötland
    "Linköping": (15.62, 58.41),
    "Norrköping": (16.19, 58.59),
    "Finspång": (15.77, 58.71),
    # Jönköping
    "Jönköping": (14.16, 57.78),
    "Vetlanda": (15.07, 57.43),
    "Tranås": (14.98, 58.04),
    "Eksjö": (14.97, 57.67),
    # Kronoberg
    "Växjö": (14.81, 56.88),
    "Ljungby": (13.94, 56.83),
    "Älmhult": (14.14, 56.55),
    # Kalmar
    "Kalmar": (16.36, 56.66),
    "Vimmerby": (15.86, 57.66),
    "Oskarshamn": (16.45, 57.26),
    # Blekinge
    "Karlskrona": (15.59, 56.16),
    # Skåne
    "Malmö": (13.00, 55.60),
    "Lund": (13.19, 55.70),
    "Helsingborg": (12.69, 56.05),
    "Kristianstad": (14.16, 56.03),
    "Hässleholm": (13.77, 56.16),
    # Halland
    "Halmstad": (12.86, 56.67),
    "Varberg": (12.25, 57.11),
    "Falkenberg": (12.49, 56.91),
    # Västra Götaland
    "Göteborg": (11.97, 57.71),
    "Borås": (12.94, 57.72),
    "Trollhättan": (12.29, 58.28),
    "Uddevalla": (11.94, 58.35),
    "Skövde": (13.84, 58.39),
    # Stockholm
    "Stockholm": (18.07, 59.33),
    "Norrtälje": (18.70, 59.76),
    # Uppsala
    "Uppsala": (17.64, 59.86),
    "Enköping": (17.08, 59.64),
    # Södermanland
    "Nyköping": (17.01, 58.75),
    "Eskilstuna": (16.51, 59.37),
    "Katrineholm": (16.21, 58.99),
    # Gotland
    "Gotland": (18.29, 57.64),
    "Visby": (18.29, 57.64),
}


SAMPLE_PROPERTIES = {
    "Sollefteå Myckelåsen 1:1": {
        "designation": "Sollefteå Myckelåsen 1:1",
        "municipality": "Sollefteå",
        "county": "Västernorrland",
        "area_ha": 85.3,
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [
                    [
                        [17.2650, 63.1660],
                        [17.2750, 63.1660],
                        [17.2780, 63.1700],
                        [17.2800, 63.1750],
                        [17.2750, 63.1780],
                        [17.2680, 63.1790],
                        [17.2620, 63.1760],
                        [17.2600, 63.1720],
                        [17.2610, 63.1680],
                        [17.2650, 63.1660],
                    ]
                ]
            ],
        },
    },
    "Sollefteå Billsta 9:12": {
        "designation": "Sollefteå Billsta 9:12",
        "municipality": "Sollefteå",
        "county": "Västernorrland",
        "area_ha": 4.0,
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [
                    [
                        [17.2730, 63.1640],
                        [17.2755, 63.1636],
                        [17.2780, 63.1640],
                        [17.2790, 63.1648],
                        [17.2785, 63.1658],
                        [17.2770, 63.1664],
                        [17.2745, 63.1665],
                        [17.2725, 63.1660],
                        [17.2720, 63.1650],
                        [17.2730, 63.1640],
                    ]
                ]
            ],
        },
    },
    "Örnsköldsvik Arnäs 2:5": {
        "designation": "Örnsköldsvik Arnäs 2:5",
        "municipality": "Örnsköldsvik",
        "county": "Västernorrland",
        "area_ha": 42.7,
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [
                    [
                        [18.7100, 63.2900],
                        [18.7200, 63.2900],
                        [18.7220, 63.2950],
                        [18.7180, 63.2980],
                        [18.7120, 63.2970],
                        [18.7080, 63.2940],
                        [18.7100, 63.2900],
                    ]
                ]
            ],
        },
    },
    "Umeå Sävar 3:12": {
        "designation": "Umeå Sävar 3:12",
        "municipality": "Umeå",
        "county": "Västerbotten",
        "area_ha": 120.5,
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [
                    [
                        [20.4500, 63.8800],
                        [20.4700, 63.8800],
                        [20.4750, 63.8850],
                        [20.4720, 63.8920],
                        [20.4600, 63.8950],
                        [20.4480, 63.8900],
                        [20.4450, 63.8850],
                        [20.4500, 63.8800],
                    ]
                ]
            ],
        },
    },
}


class LantmaterietClient:
    """Client for Lantmäteriet Fastighetsindelning Direkt (OGC API Features).

    Uses Basic Auth with systemkonto credentials.
    API docs: https://geotorget.lantmateriet.se/dokumentation/GEODOK/81/latest.html
    Endpoint: https://api.lantmateriet.se/ogc-features/v1/fastighetsindelning
    """

    def __init__(self):
        self.base_url = settings.LANTMATERIET_API_BASE
        self.user = settings.LANTMATERIET_USER
        self.password = settings.LANTMATERIET_PASS

    @property
    def _has_credentials(self) -> bool:
        return bool(self.user and self.password)

    @property
    def _auth(self) -> Optional[tuple[str, str]]:
        if self._has_credentials:
            return (self.user, self.password)
        return None

    async def lookup_property(self, designation: str) -> Optional[dict]:
        """Look up a property by its designation (fastighetsbeteckning).

        Args:
            designation: e.g. "Sollefteå Bringen 1:2"

        Returns:
            Dict with designation, municipality, county, geometry, area_ha
            or None if not found.
        """
        parsed = self._parse_designation(designation)
        if not parsed:
            logger.warning(f"Could not parse property designation: {designation}")
            return None

        if self._has_credentials:
            try:
                result = await self._api_lookup(designation, parsed)
                if result:
                    return result
                logger.info(f"Property not found via API: {designation}, trying mock")
            except Exception as e:
                logger.warning(
                    f"Lantmateriet API lookup failed, falling back to mock: {e}"
                )

        return self._mock_lookup(designation, parsed)

    async def _api_lookup(self, designation: str, parsed: dict) -> Optional[dict]:
        """Look up property via Fastighetsindelning Direkt OGC API.

        Searches registerenhetsomradesytor (property area polygons) by
        kommun, trakt, block, enhet.
        """
        municipality = parsed.get("municipality", "")
        property_name = parsed.get("property_name", "")
        unit = parsed.get("unit", "1:1")
        block, enhet = unit.split(":") if ":" in unit else ("1", "1")

        # The trakt name is the property_name (e.g. "BRINGEN")
        trakt = property_name.upper()

        params = {
            "f": "json",
            "limit": 20,
            "trakt": trakt,
            "block": block,
            "enhet": int(enhet),
        }

        # Optionally filter by kommun if we can map municipality name to code
        kommun_code = self._get_kommun_code(municipality)
        if kommun_code:
            params["kommunkod"] = kommun_code

        url = f"{self.base_url}/collections/registerenhetsomradesytor/items"

        async with httpx.AsyncClient(timeout=30.0, auth=self._auth) as client:
            response = await client.get(url, params=params)

            if response.status_code != 200:
                logger.warning(
                    f"Lantmäteriet API error {response.status_code}: {response.text[:200]}"
                )
                return None

            data = response.json()
            features = data.get("features", [])

            if not features:
                logger.info(f"No features found for {designation} (trakt={trakt}, block={block}, enhet={enhet})")
                return None

            # If multiple features (property has multiple areas), merge geometries
            if len(features) == 1:
                geom = features[0]["geometry"]
                props = features[0]["properties"]
            else:
                # Combine into MultiPolygon
                all_coords = []
                for feat in features:
                    g = feat["geometry"]
                    if g["type"] == "Polygon":
                        all_coords.append(g["coordinates"])
                    elif g["type"] == "MultiPolygon":
                        all_coords.extend(g["coordinates"])
                geom = {"type": "MultiPolygon", "coordinates": all_coords}
                props = features[0]["properties"]

            # Ensure geometry is MultiPolygon for consistency
            if geom["type"] == "Polygon":
                geom = {
                    "type": "MultiPolygon",
                    "coordinates": [geom["coordinates"]],
                }

            # Calculate approximate area from polygon (WGS84)
            area_ha = self._estimate_area_ha(geom)

            kommun_namn = props.get("kommunnamn", municipality)

            logger.info(
                f"Found property via Lantmäteriet: {kommun_namn} {props.get('trakt')} "
                f"{props.get('block')}:{props.get('enhet')} "
                f"({len(features)} area(s), ~{area_ha:.1f} ha)"
            )

            return {
                "designation": designation,
                "municipality": kommun_namn.title() if kommun_namn else municipality,
                "county": self._guess_county(kommun_namn.title() if kommun_namn else municipality),
                "geometry": geom,
                "area_ha": area_ha,
                "lantmateriet_id": props.get("objektidentitet"),
                "last_updated": props.get("senastandrad"),
            }

    async def search_properties(
        self,
        municipality: Optional[str] = None,
        kommun_code: Optional[str] = None,
        trakt: Optional[str] = None,
        bbox: Optional[tuple[float, float, float, float]] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search for properties by various criteria.

        Args:
            municipality: Municipality name (e.g. "Sollefteå")
            kommun_code: Municipality code (e.g. "2283")
            trakt: Tract name (e.g. "BRINGEN")
            bbox: Bounding box (minlon, minlat, maxlon, maxlat) in WGS84
            limit: Max results

        Returns:
            List of property dicts with designation and basic info.
        """
        if not self._has_credentials:
            logger.warning("No Lantmäteriet credentials configured")
            return []

        params: dict = {"f": "json", "limit": limit}

        if kommun_code:
            params["kommunkod"] = kommun_code
        elif municipality:
            code = self._get_kommun_code(municipality)
            if code:
                params["kommunkod"] = code

        if trakt:
            params["trakt"] = trakt.upper()

        if bbox:
            params["bbox"] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"

        url = f"{self.base_url}/collections/registerenhetsomradesytor/items"

        try:
            async with httpx.AsyncClient(timeout=30.0, auth=self._auth) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.error(f"Lantmäteriet search failed: {e}")
            return []

        results = []
        seen = set()
        for feat in data.get("features", []):
            p = feat["properties"]
            key = f"{p.get('trakt','')} {p.get('block','')}:{p.get('enhet','')}"
            if key in seen:
                continue
            seen.add(key)

            kommun = p.get("kommunnamn", "").title()
            results.append({
                "designation": f"{kommun} {p.get('trakt','')} {p.get('block','')}:{p.get('enhet','')}",
                "municipality": kommun,
                "kommun_code": p.get("kommunkod", ""),
                "trakt": p.get("trakt", ""),
                "block": p.get("block", ""),
                "enhet": p.get("enhet", 0),
                "last_updated": p.get("senastandrad", ""),
            })

        return results

    def _mock_lookup(self, designation: str, parsed: dict) -> Optional[dict]:
        normalized = designation.strip()

        if normalized in SAMPLE_PROPERTIES:
            logger.info(f"Using sample property data for: {normalized}")
            return SAMPLE_PROPERTIES[normalized]

        for key, value in SAMPLE_PROPERTIES.items():
            if key.lower() == normalized.lower():
                logger.info(f"Using sample property data for: {normalized}")
                return value

        logger.info(
            f"No sample data for '{normalized}'. Generating mock property."
        )

        municipality = parsed.get("municipality", "Okänd")
        center_lon, center_lat = self._get_municipality_center(municipality)
        mock_area_ha = 50.0
        geometry = self._generate_mock_polygon(center_lon, center_lat, mock_area_ha)

        return {
            "designation": designation,
            "municipality": municipality,
            "county": self._guess_county(municipality),
            "area_ha": mock_area_ha,
            "geometry": geometry,
        }

    def _parse_designation(self, designation: str) -> Optional[dict]:
        designation = designation.strip()

        # Pattern: "Kommun Fastighetsnamn X:Y"
        # Examples: "Sollefteå Myckelåsen 1:1", "Umeå Sävar 3:12"
        pattern = r"^(\S+)\s+(.+?)\s+(\d+:\d+)$"
        match = re.match(pattern, designation)
        if match:
            return {
                "municipality": match.group(1),
                "property_name": match.group(2),
                "unit": match.group(3),
            }

        # Try simpler pattern: "Text X:Y"
        simple_pattern = r"^(.+?)\s+(\d+:\d+)$"
        match = re.match(simple_pattern, designation)
        if match:
            name_parts = match.group(1).split()
            municipality = name_parts[0] if name_parts else "Okänd"
            property_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else name_parts[0]
            return {
                "municipality": municipality,
                "property_name": property_name,
                "unit": match.group(2),
            }

        return {"municipality": "Okänd", "property_name": designation, "unit": "1:1"}

    def _get_municipality_center(self, municipality: str) -> tuple[float, float]:
        """Get approximate WGS84 center coordinates for a municipality."""
        # Exact match
        if municipality in MUNICIPALITY_COORDS:
            return MUNICIPALITY_COORDS[municipality]
        # Case-insensitive match
        for name, coords in MUNICIPALITY_COORDS.items():
            if name.lower() == municipality.lower():
                return coords
        # Default: central Sweden (roughly Sundsvall area)
        logger.warning(f"No coordinates for municipality '{municipality}', using default")
        return (17.31, 62.39)

    def _generate_mock_polygon(
        self, center_lon: float, center_lat: float, area_ha: float
    ) -> dict:
        """Generate a realistic-looking polygon centered on given coordinates.

        Creates an octagonal shape with the approximate target area.
        Coordinates are in WGS84.
        """
        # Calculate approximate dimensions in degrees
        # At given latitude, 1 degree longitude ≈ 111320 * cos(lat) meters
        # 1 degree latitude ≈ 111320 meters
        lat_rad = math.radians(center_lat)
        m_per_deg_lon = 111320.0 * math.cos(lat_rad)
        m_per_deg_lat = 111320.0

        # Target area in m², create roughly circular polygon
        area_m2 = area_ha * 10000.0
        radius_m = math.sqrt(area_m2 / math.pi)

        # Convert radius to degrees
        r_lon = radius_m / m_per_deg_lon
        r_lat = radius_m / m_per_deg_lat

        # Generate 10-point polygon (roughly circular)
        num_points = 10
        coords = []
        for i in range(num_points):
            angle = 2.0 * math.pi * i / num_points
            # Add slight irregularity to look more natural
            scale = 1.0 + 0.08 * math.sin(3 * angle)
            lon = center_lon + r_lon * math.cos(angle) * scale
            lat = center_lat + r_lat * math.sin(angle) * scale
            coords.append([round(lon, 4), round(lat, 4)])
        # Close the polygon
        coords.append(coords[0])

        return {
            "type": "MultiPolygon",
            "coordinates": [[coords]],
        }

    def _estimate_area_ha(self, geom: dict) -> float:
        """Estimate area in hectares from a WGS84 GeoJSON geometry.

        Uses the Shoelace formula with latitude correction.
        """
        total_area_m2 = 0.0

        if geom["type"] == "Polygon":
            polygons = [geom["coordinates"]]
        elif geom["type"] == "MultiPolygon":
            polygons = geom["coordinates"]
        else:
            return 0.0

        for polygon in polygons:
            ring = polygon[0]  # outer ring
            if len(ring) < 3:
                continue

            # Approximate center latitude for correction
            avg_lat = sum(c[1] for c in ring) / len(ring)
            lat_rad = math.radians(avg_lat)
            m_per_deg_lon = 111320.0 * math.cos(lat_rad)
            m_per_deg_lat = 111320.0

            # Shoelace formula in projected meters
            area = 0.0
            n = len(ring)
            for i in range(n):
                j = (i + 1) % n
                x1 = ring[i][0] * m_per_deg_lon
                y1 = ring[i][1] * m_per_deg_lat
                x2 = ring[j][0] * m_per_deg_lon
                y2 = ring[j][1] * m_per_deg_lat
                area += x1 * y2 - x2 * y1

            total_area_m2 += abs(area) / 2.0

        return total_area_m2 / 10000.0  # m² → ha

    # Kommun codes for municipalities we support
    KOMMUN_CODES: dict[str, str] = {
        "Sollefteå": "2283", "Örnsköldsvik": "2284", "Härnösand": "2280",
        "Sundsvall": "2281", "Kramfors": "2282", "Ånge": "2260", "Timrå": "2262",
        "Umeå": "2480", "Skellefteå": "2482", "Lycksele": "2481",
        "Vindeln": "2404", "Robertsfors": "2409", "Nordmaling": "2401",
        "Vilhelmina": "2462", "Storuman": "2421", "Dorotea": "2425",
        "Åsele": "2463", "Vännäs": "2460", "Bjurholm": "2403",
        "Norsjö": "2417", "Malå": "2418", "Sorsele": "2422",
        "Luleå": "2580", "Piteå": "2581", "Boden": "2582",
        "Gällivare": "2583", "Kiruna": "2584", "Jokkmokk": "2510",
        "Kalix": "2514", "Haparanda": "2583", "Älvsbyn": "2560",
        "Östersund": "2380", "Krokom": "2309", "Strömsund": "2313",
        "Berg": "2326", "Åre": "2303", "Bräcke": "2305",
        "Ragunda": "2303", "Härjedalen": "2361",
        "Falun": "2080", "Mora": "2062", "Borlänge": "2081",
        "Gävle": "2180", "Hudiksvall": "2184", "Söderhamn": "2182",
        "Sandviken": "2181", "Bollnäs": "2183", "Ljusdal": "2161",
    }

    def _get_kommun_code(self, municipality: str) -> Optional[str]:
        """Get SCB kommun code from municipality name."""
        if not municipality:
            return None
        # Exact match
        if municipality in self.KOMMUN_CODES:
            return self.KOMMUN_CODES[municipality]
        # Case-insensitive
        for name, code in self.KOMMUN_CODES.items():
            if name.lower() == municipality.lower():
                return code
        return None

    def _guess_county(self, municipality: str) -> Optional[str]:
        county_map = {
            "Sollefteå": "Västernorrland",
            "Örnsköldsvik": "Västernorrland",
            "Härnösand": "Västernorrland",
            "Sundsvall": "Västernorrland",
            "Kramfors": "Västernorrland",
            "Ånge": "Västernorrland",
            "Timrå": "Västernorrland",
            "Umeå": "Västerbotten",
            "Skellefteå": "Västerbotten",
            "Lycksele": "Västerbotten",
            "Vindeln": "Västerbotten",
            "Robertsfors": "Västerbotten",
            "Nordmaling": "Västerbotten",
            "Vilhelmina": "Västerbotten",
            "Storuman": "Västerbotten",
            "Luleå": "Norrbotten",
            "Piteå": "Norrbotten",
            "Boden": "Norrbotten",
            "Gällivare": "Norrbotten",
            "Kiruna": "Norrbotten",
            "Jokkmokk": "Norrbotten",
            "Östersund": "Jämtland",
            "Krokom": "Jämtland",
            "Strömsund": "Jämtland",
            "Berg": "Jämtland",
            "Åre": "Jämtland",
            "Falun": "Dalarna",
            "Mora": "Dalarna",
            "Borlänge": "Dalarna",
            "Gävle": "Gävleborg",
            "Hudiksvall": "Gävleborg",
            "Söderhamn": "Gävleborg",
            "Sandviken": "Gävleborg",
            "Bollnäs": "Gävleborg",
            "Västerås": "Västmanland",
            "Karlstad": "Värmland",
            "Örebro": "Örebro",
            "Jönköping": "Jönköping",
            "Växjö": "Kronoberg",
            "Kalmar": "Kalmar",
            "Linköping": "Östergötland",
            "Stockholm": "Stockholm",
            "Uppsala": "Uppsala",
            "Göteborg": "Västra Götaland",
            "Malmö": "Skåne",
        }
        return county_map.get(municipality)
