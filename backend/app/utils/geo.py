from typing import Union

import pyproj
from shapely.geometry import MultiPolygon, Polygon, box, mapping, shape
from shapely.ops import transform

SWEREF99_TM = pyproj.CRS("EPSG:3006")
WGS84 = pyproj.CRS("EPSG:4326")

_transformer_to_wgs84 = pyproj.Transformer.from_crs(
    SWEREF99_TM, WGS84, always_xy=True
)
_transformer_to_sweref99 = pyproj.Transformer.from_crs(
    WGS84, SWEREF99_TM, always_xy=True
)


def sweref99_to_wgs84(
    geometry: Union[Polygon, MultiPolygon],
) -> Union[Polygon, MultiPolygon]:
    return transform(_transformer_to_wgs84.transform, geometry)


def wgs84_to_sweref99(
    geometry: Union[Polygon, MultiPolygon],
) -> Union[Polygon, MultiPolygon]:
    return transform(_transformer_to_sweref99.transform, geometry)


def calculate_area_ha(geometry_3006: Union[Polygon, MultiPolygon]) -> float:
    area_m2 = geometry_3006.area
    return round(area_m2 / 10000.0, 2)


def geometry_to_geojson(geometry: Union[Polygon, MultiPolygon]) -> dict:
    return mapping(geometry)


def geojson_to_geometry(geojson: dict) -> Union[Polygon, MultiPolygon]:
    return shape(geojson)


def bbox_to_polygon(bbox: list[float]) -> Polygon:
    if len(bbox) != 4:
        raise ValueError(
            f"Bounding box must have exactly 4 values [minx, miny, maxx, maxy], got {len(bbox)}"
        )
    minx, miny, maxx, maxy = bbox
    if minx >= maxx or miny >= maxy:
        raise ValueError(
            f"Invalid bounding box: minx ({minx}) must be less than maxx ({maxx}), "
            f"miny ({miny}) must be less than maxy ({maxy})"
        )
    return box(minx, miny, maxx, maxy)
