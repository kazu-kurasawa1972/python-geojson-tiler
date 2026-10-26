"""Clip GeoJSON geometries to the lon/lat bounds of an XYZ tile.

Everything here works in plain longitude/latitude degrees and treats segments as
straight lines in lon/lat (the GeoJSON rule). Only the standard library is used.

Rules:
- Lines are cut with the Liang-Barsky algorithm. A line that leaves and re-enters
  the tile becomes several pieces; more than one piece gives a ``MultiLineString``.
- Polygon rings are cut with the Sutherland-Hodgman algorithm and stay closed.
  Holes that vanish are dropped. If the exterior ring vanishes, the polygon vanishes.
  Rings with fewer than 4 positions or with zero area are treated as vanished.
  For concave polygons the result may contain zero-width "bridges" along the tile edge.
- Points are kept only if ``lonlat_to_tile`` puts them in this tile, so a point on a
  shared tile edge lands in exactly one tile.
- ``Multi*`` geometries keep their type: the surviving members are listed in a
  ``Multi*`` even if only one is left. ``GeometryCollection`` keeps only the members
  that survive. A plain ``LineString`` is the one exception: it becomes a
  ``MultiLineString`` only when it splits into more than one piece.
- Extra ordinates (such as altitude) are kept on original vertices. A new vertex
  created on a tile edge gets interpolated values for every ordinate that both
  neighbouring vertices have.
- An empty result is reported as ``None``.
"""

from __future__ import annotations

from typing import Any

from .xyz import Bounds, TileAddress, lonlat_to_tile, tile_bounds

Position = list[float]
Ring = list[Position]

# A hole whose clipped area reaches this share of the exterior covers the whole piece.
HOLE_COVERS_RATIO = 1 - 1e-12


def clip_geometry(geometry: dict[str, Any], tile: TileAddress) -> dict[str, Any] | None:
    """Clip a GeoJSON geometry to ``tile``. Return ``None`` if nothing is left.

    The result only has ``type`` and ``coordinates`` (or ``geometries``).
    """
    kind = geometry["type"]
    bounds = tile_bounds(tile)
    if kind == "GeometryCollection":
        members = [clip_geometry(member, tile) for member in geometry["geometries"]]
        kept = [member for member in members if member is not None]
        return {"type": kind, "geometries": kept} if kept else None

    coordinates = geometry["coordinates"]
    if kind == "Point":
        return _wrap(kind, clip_point(coordinates, tile))
    if kind == "MultiPoint":
        points = [clip_point(point, tile) for point in coordinates]
        return _wrap(kind, [point for point in points if point is not None])
    if kind == "LineString":
        pieces = clip_line(coordinates, bounds)
        if len(pieces) == 1:
            return _wrap(kind, pieces[0])
        return _wrap("MultiLineString", pieces)
    if kind == "MultiLineString":
        return _wrap(kind, [piece for line in coordinates for piece in clip_line(line, bounds)])
    if kind == "Polygon":
        return _wrap(kind, clip_polygon(coordinates, bounds))
    # MultiPolygon: validate_geometry has already rejected every other type.
    polygons = [clip_polygon(polygon, bounds) for polygon in coordinates]
    return _wrap(kind, [polygon for polygon in polygons if polygon is not None])


def _wrap(kind: str, coordinates: Any) -> dict[str, Any] | None:
    """Build a geometry dict, or ``None`` when the coordinates are empty."""
    if coordinates is None or coordinates == []:
        return None
    return {"type": kind, "coordinates": coordinates}


def clip_point(position: Position, tile: TileAddress) -> Position | None:
    """Return a copy of ``position`` if it belongs to ``tile``, else ``None``.

    Uses ``lonlat_to_tile`` so the half-open edge rule is identical to the tiler's.
    """
    if lonlat_to_tile(position[0], position[1], tile.z) == tile:
        return list(position)
    return None


def _lerp(start: Position, end: Position, fraction: float) -> Position:
    """Interpolate every ordinate that both positions have."""
    return [a + (b - a) * fraction for a, b in zip(start, end)]


def _clamped_lerp(start: Position, end: Position, fraction: float, bounds: Bounds) -> Position:
    """Like ``_lerp``, but round-off can never push x/y outside ``bounds``."""
    west, south, east, north = bounds
    result = _lerp(start, end, fraction)
    result[0] = min(max(result[0], west), east)
    result[1] = min(max(result[1], south), north)
    return result


def clip_line(line: list[Position], bounds: Bounds) -> list[list[Position]]:
    """Clip a line with Liang-Barsky. Return the pieces (each has 2 or more positions)."""
    pieces: list[list[Position]] = []
    current: list[Position] = []
    for start, end in zip(line, line[1:]):
        span = _segment_span(start, end, bounds)
        if span is None:
            current = []
            continue
        first, last = span
        clipped_start = list(start) if first == 0.0 else _clamped_lerp(start, end, first, bounds)
        clipped_end = list(end) if last == 1.0 else _clamped_lerp(start, end, last, bounds)
        if current and current[-1] == clipped_start:
            current.append(clipped_end)
        else:
            current = [clipped_start, clipped_end]
            pieces.append(current)
    return pieces


def _segment_span(start: Position, end: Position, bounds: Bounds) -> tuple[float, float] | None:
    """Liang-Barsky: return the (t0, t1) part of the segment inside ``bounds``."""
    west, south, east, north = bounds
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    first, last = 0.0, 1.0
    checks = (
        (-dx, start[0] - west),
        (dx, east - start[0]),
        (-dy, start[1] - south),
        (dy, north - start[1]),
    )
    for p, q in checks:
        if p == 0:
            if q < 0:
                return None
            continue
        ratio = q / p
        if p < 0:
            first = max(first, ratio)
        else:
            last = min(last, ratio)
    if first >= last:
        return None
    return first, last


def ring_area(ring: Ring) -> float:
    """Return the absolute shoelace area of a ring in square degrees."""
    total = 0.0
    for a, b in zip(ring, ring[1:]):
        total += a[0] * b[1] - b[0] * a[1]
    return abs(total) / 2.0


def clip_ring(ring: Ring, bounds: Bounds) -> Ring | None:
    """Clip a closed ring with Sutherland-Hodgman. Return a closed ring or ``None``."""
    west, south, east, north = bounds
    points = [list(position) for position in ring[:-1]]
    # (axis, edge value, keep values at or above the edge?)
    for axis, value, keep_above in ((0, west, True), (0, east, False), (1, south, True), (1, north, False)):
        points = _clip_to_edge(points, axis, value, keep_above)
        if not points:
            return None
    if points[0][:2] == points[-1][:2]:
        points.pop()
    if len(points) < 3:
        return None
    result = [*points, list(points[0])]
    return result if ring_area(result) > 0.0 else None


def _clip_to_edge(points: Ring, axis: int, value: float, keep_above: bool) -> Ring:
    """One Sutherland-Hodgman pass against a single straight tile edge."""
    out: Ring = []

    def add(position: Position) -> None:
        if not out or out[-1][:2] != position[:2]:
            out.append(position)

    def inside(position: Position) -> bool:
        return position[axis] >= value if keep_above else position[axis] <= value

    previous = points[-1]
    for current in points:
        if inside(current):
            if not inside(previous):
                add(_cross(previous, current, axis, value))
            add(current)
        elif inside(previous):
            add(_cross(previous, current, axis, value))
        previous = current
    return out


def _cross(start: Position, end: Position, axis: int, value: float) -> Position:
    """Where the segment start-end meets the line ``position[axis] == value``."""
    crossing = _lerp(start, end, (value - start[axis]) / (end[axis] - start[axis]))
    crossing[axis] = value
    return crossing


def clip_polygon(rings: list[Ring], bounds: Bounds) -> list[Ring] | None:
    """Clip a polygon (exterior ring first, then holes). Return ``None`` if it vanishes."""
    exterior = clip_ring(rings[0], bounds)
    if exterior is None:
        return None
    exterior_area = ring_area(exterior)
    result = [exterior]
    for hole in rings[1:]:
        clipped = clip_ring(hole, bounds)
        if clipped is None:
            continue
        if ring_area(clipped) >= exterior_area * HOLE_COVERS_RATIO:
            return None
        result.append(clipped)
    return result
