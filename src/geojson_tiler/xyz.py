from __future__ import annotations

from dataclasses import dataclass
from math import asinh, atan, degrees, floor, pi, radians, sinh, tan

WEB_MERCATOR_LAT_LIMIT = 85.05112878
EPSILON = 1e-12
Bounds = tuple[float, float, float, float]


@dataclass(frozen=True, order=True)
class TileAddress:
    """An XYZ tile address."""

    z: int
    x: int
    y: int


def validate_zoom(zoom: int) -> None:
    """Ensure a zoom level can be used in XYZ math."""
    if not isinstance(zoom, int) or isinstance(zoom, bool) or zoom < 0:
        raise ValueError("Zoom must be a non-negative integer.")


def clamp_longitude(longitude: float) -> float:
    """Clamp longitude to the inclusive world range used by XYZ tiles."""
    if longitude <= -180.0:
        return -180.0
    if longitude >= 180.0:
        return 180.0 - EPSILON
    return float(longitude)


def clamp_latitude(latitude: float) -> float:
    """Clamp latitude to the Web Mercator range."""
    if latitude <= -WEB_MERCATOR_LAT_LIMIT:
        return -WEB_MERCATOR_LAT_LIMIT
    if latitude >= WEB_MERCATOR_LAT_LIMIT:
        return WEB_MERCATOR_LAT_LIMIT
    return float(latitude)


def lonlat_to_tile(longitude: float, latitude: float, zoom: int) -> TileAddress:
    """Convert lon/lat coordinates into an XYZ tile address."""
    validate_zoom(zoom)
    n = 2**zoom
    longitude = clamp_longitude(float(longitude))
    latitude = clamp_latitude(float(latitude))

    x = int(floor((longitude + 180.0) / 360.0 * n))
    y = int(floor((1.0 - asinh(tan(radians(latitude))) / pi) / 2.0 * n))
    x = min(max(x, 0), n - 1)
    y = min(max(y, 0), n - 1)
    return TileAddress(z=zoom, x=x, y=y)


def tile_bounds(tile: TileAddress) -> Bounds:
    """Return geographic bounds for a tile as (west, south, east, north)."""
    n = 2**tile.z
    west = tile.x / n * 360.0 - 180.0
    east = (tile.x + 1) / n * 360.0 - 180.0
    north = degrees(atan(sinh(pi * (1 - 2 * tile.y / n))))
    south = degrees(atan(sinh(pi * (1 - 2 * (tile.y + 1) / n))))
    return west, south, east, north


def tiles_for_bounds(bounds: Bounds, zoom: int) -> list[TileAddress]:
    """Return every tile touched by the given geographic bounds."""
    validate_zoom(zoom)
    min_lon, min_lat, max_lon, max_lat = bounds
    west = min(min_lon, max_lon)
    east = max(min_lon, max_lon)
    south = min(min_lat, max_lat)
    north = max(min_lat, max_lat)

    top_left = lonlat_to_tile(west, north, zoom)
    bottom_right = lonlat_to_tile(east, south, zoom)

    return [
        TileAddress(z=zoom, x=x, y=y)
        for x in range(top_left.x, bottom_right.x + 1)
        for y in range(top_left.y, bottom_right.y + 1)
    ]

