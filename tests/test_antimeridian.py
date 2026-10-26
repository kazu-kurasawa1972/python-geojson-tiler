import pytest

from geojson_tiler.geojson import crosses_antimeridian, geometry_bounds
from geojson_tiler.tiler import tile_geojson
from geojson_tiler.xyz import count_tiles_for_bounds, tile_ranges, tiles_for_bounds


def line(*positions):
    return {"type": "LineString", "coordinates": [list(p) for p in positions]}


def test_crosses_antimeridian_detects_line_jump():
    assert crosses_antimeridian(line((170, 0), (-170, 0)))


def test_crosses_antimeridian_detects_jump_in_polygon_ring():
    ring = [[170, 0], [-170, 0], [-170, 5], [170, 5], [170, 0]]
    assert crosses_antimeridian({"type": "Polygon", "coordinates": [ring]})
    assert crosses_antimeridian(
        {"type": "MultiPolygon", "coordinates": [[ring]]}
    )


def test_crosses_antimeridian_ignores_normal_and_missing_geometry():
    assert not crosses_antimeridian(None)
    assert not crosses_antimeridian(line((-10, 0), (10, 0)))


def test_crosses_antimeridian_ignores_jumps_between_separate_parts_and_points():
    multi_point = {"type": "MultiPoint", "coordinates": [[170, 0], [-170, 0]]}
    multi_line = {
        "type": "MultiLineString",
        "coordinates": [[[170, 0], [175, 0]], [[-175, 0], [-170, 0]]],
    }
    assert not crosses_antimeridian(multi_point)
    assert not crosses_antimeridian(multi_line)


def test_crosses_antimeridian_looks_inside_geometry_collections():
    collection = {"type": "GeometryCollection", "geometries": [line((170, 0), (-170, 0))]}
    assert crosses_antimeridian(collection)


def test_crosses_antimeridian_skips_empty_chains():
    assert not crosses_antimeridian({"type": "LineString", "coordinates": []})


def test_geometry_bounds_for_crossing_line_has_west_greater_than_east():
    geometry = line((170, -3), (175, 0), (-170, 4))
    assert geometry_bounds(geometry) == (170, -3, -170, 4)


def test_geometry_bounds_crossing_uses_nearest_positions_not_extremes():
    geometry = line((10, 0), (170, 0), (-170, 0), (-10, 0))
    assert geometry_bounds(geometry) == (10, 0, -10, 0)


def test_geometry_bounds_non_crossing_is_unchanged():
    assert geometry_bounds(line((-10, -1), (10, 2))) == (-10, -1, 10, 2)


def test_tile_ranges_crossing_returns_columns_at_both_edges():
    x_values, y_range = tile_ranges((170, -5, -170, 5), 3)
    assert list(x_values) == [0, 7]
    assert list(y_range) == [3, 4]


def test_tile_ranges_crossing_wide_bbox_at_low_zoom_is_whole_row_without_duplicates():
    x_values, _ = tile_ranges((10, 0, 5, 1), 2)
    assert list(x_values) == [0, 1, 2, 3]


def test_count_matches_tiles_for_crossing_bounds():
    bounds = (170, -5, -170, 5)
    assert count_tiles_for_bounds(bounds, 3) == len(tiles_for_bounds(bounds, 3)) == 4


def test_tile_geojson_writes_only_columns_near_antimeridian():
    data = {
        "type": "Feature",
        "properties": {},
        "geometry": line((170, 0), (-170, 0)),
    }
    result = tile_geojson(data, min_zoom=3, max_zoom=3)
    assert sorted({tile.x for tile in result.tiles}) == [0, 7]


def test_max_tiles_guard_counts_only_wrapped_columns():
    data = {"type": "Feature", "properties": {}, "geometry": line((170, 0), (-170, 0))}
    # Two columns x one row at zoom 3 fits in 2 tiles; the old whole-world span (8) would not.
    assert len(tile_geojson(data, min_zoom=3, max_zoom=3, max_tiles=2).tiles) == 2
    with pytest.raises(ValueError, match="more than 1"):
        tile_geojson(data, min_zoom=3, max_zoom=3, max_tiles=1)
