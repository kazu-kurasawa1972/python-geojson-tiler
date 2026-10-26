import pytest

from geojson_tiler.clip import (
    clip_geometry,
    clip_line,
    clip_point,
    clip_polygon,
    clip_ring,
    ring_area,
)
from geojson_tiler.tiler import tile_geojson
from geojson_tiler.xyz import TileAddress, tile_bounds

BOX = (0.0, 0.0, 10.0, 10.0)  # west, south, east, north
# Tile 1/1/0 covers lon 0..180, lat 0..85.05 (east edge 180, north edge about 85.05).
TILE = TileAddress(1, 1, 0)


def square(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


# ---- lines (Liang-Barsky) ----


def test_line_fully_inside_is_unchanged():
    line = [[1, 1], [5, 5], [9, 2]]
    assert clip_line(line, BOX) == [line]


def test_line_fully_outside_is_dropped():
    assert clip_line([[20, 20], [30, 30]], BOX) == []


def test_line_outside_parallel_to_edge_is_dropped():
    assert clip_line([[-5, 20], [15, 20]], BOX) == []


def test_line_crossing_one_edge_is_cut():
    assert clip_line([[5, 5], [15, 5]], BOX) == [[[5, 5], [10, 5]]]


def test_line_entering_from_outside_is_cut_at_start():
    assert clip_line([[-5, 5], [5, 5]], BOX) == [[[0, 5], [5, 5]]]


def test_line_leaving_and_reentering_gives_two_pieces():
    line = [[2, 5], [15, 5], [15, 8], [2, 8]]
    assert clip_line(line, BOX) == [[[2, 5], [10, 5]], [[10, 8], [2, 8]]]


def test_line_pieces_continue_across_vertices_inside():
    # The middle vertex is inside, so both segments belong to one piece.
    line = [[-5, 5], [5, 5], [15, 5]]
    assert clip_line(line, BOX) == [[[0, 5], [5, 5], [10, 5]]]


def test_line_along_an_edge_is_kept():
    assert clip_line([[0, 0], [10, 0]], BOX) == [[[0, 0], [10, 0]]]


def test_line_touching_only_a_corner_is_dropped():
    assert clip_line([[-5, 5], [5, -5]], BOX) == []


def test_line_with_one_position_gives_nothing():
    assert clip_line([[5, 5]], BOX) == []


def test_line_diagonal_crossing_stays_inside_bounds():
    (piece,) = clip_line([[-3, -1], [13, 11]], BOX)
    for x, y in piece:
        assert 0 <= x <= 10 and 0 <= y <= 10


def test_line_z_is_carried_and_interpolated():
    line = [[5, 5, 100], [15, 5, 200]]
    assert clip_line(line, BOX) == [[[5, 5, 100], [10, 5, 150]]]


def test_line_z_missing_on_one_end_is_not_invented():
    line = [[5, 5, 100], [15, 5]]
    assert clip_line(line, BOX) == [[[5, 5, 100], [10, 5]]]


# ---- polygon rings (Sutherland-Hodgman) ----


def test_ring_fully_inside_is_unchanged():
    ring = square(2, 2, 8, 8)
    assert clip_ring(ring, BOX) == ring


def test_ring_fully_outside_vanishes():
    assert clip_ring(square(20, 20, 30, 30), BOX) is None


def test_ring_straddling_one_edge():
    clipped = clip_ring(square(5, 2, 15, 8), BOX)
    assert clipped[0] == clipped[-1]
    assert ring_area(clipped) == pytest.approx(5 * 6)
    assert max(x for x, _ in clipped) == 10


def test_ring_straddling_two_edges_at_a_corner():
    clipped = clip_ring(square(5, 5, 15, 15), BOX)
    assert ring_area(clipped) == pytest.approx(25)
    assert len(clipped) == 5


def test_ring_covering_the_whole_box_becomes_the_box():
    clipped = clip_ring(square(-5, -5, 15, 15), BOX)
    assert ring_area(clipped) == pytest.approx(100)
    assert clipped[0] == clipped[-1]


def test_ring_straddling_two_opposite_edges():
    clipped = clip_ring(square(-5, 2, 15, 8), BOX)
    assert ring_area(clipped) == pytest.approx(10 * 6)


def test_ring_touching_box_along_an_edge_vanishes():
    assert clip_ring(square(10, 0, 20, 10), BOX) is None


def test_ring_touching_box_at_a_point_vanishes():
    assert clip_ring(square(10, 10, 20, 20), BOX) is None


def test_ring_with_zero_area_vanishes():
    assert clip_ring([[0, 0], [5, 0], [10, 0], [0, 0]], BOX) is None


def test_ring_with_vertex_on_edge_has_no_duplicate_points():
    ring = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    clipped = clip_ring(ring, BOX)
    assert clipped == ring


def test_ring_that_closes_on_a_clipped_vertex_has_no_repeat():
    # Clipping makes the first and last open positions meet on the east edge.
    ring = [[12, 5], [5, 2], [5, 8], [12, 5]]
    clipped = clip_ring(ring, BOX)
    assert clipped[0] == clipped[-1]
    assert clipped[0] != clipped[-2]


def test_ring_z_is_interpolated_on_new_vertices():
    ring = [[5, 2, 10], [15, 2, 20], [15, 8, 20], [5, 8, 10], [5, 2, 10]]
    clipped = clip_ring(ring, BOX)
    assert all(len(position) == 3 for position in clipped)
    on_edge = [position for position in clipped if position[0] == 10]
    assert {position[2] for position in on_edge} == {15}


# ---- polygons ----


def test_polygon_exterior_vanishing_removes_whole_polygon():
    polygon = [square(20, 20, 30, 30), square(22, 22, 28, 28)]
    assert clip_polygon(polygon, BOX) is None


def test_polygon_hole_inside_is_kept():
    polygon = [square(1, 1, 9, 9), square(3, 3, 5, 5)]
    assert clip_polygon(polygon, BOX) == polygon


def test_polygon_hole_outside_the_box_is_dropped():
    polygon = [square(-20, -20, 9, 9), square(-15, -15, -10, -10)]
    result = clip_polygon(polygon, BOX)
    assert len(result) == 1


def test_polygon_hole_cut_by_edge_is_clipped():
    polygon = [square(-5, -5, 9, 9), square(-2, 3, 4, 6)]
    result = clip_polygon(polygon, BOX)
    assert len(result) == 2
    assert ring_area(result[1]) == pytest.approx(4 * 3)


def test_polygon_hole_covering_the_box_removes_polygon():
    polygon = [square(-20, -20, 20, 20), square(-10, -10, 15, 15)]
    assert clip_polygon(polygon, BOX) is None


# ---- points ----


def test_point_inside_tile_is_kept_and_copied():
    position = [90.0, 45.0, 7.0]
    kept = clip_point(position, TILE)
    assert kept == position
    assert kept is not position


def test_point_in_other_tile_is_dropped():
    assert clip_point([-90.0, 45.0], TILE) is None


@pytest.mark.parametrize(
    "position, owner",
    [
        ([0.0, 45.0], TileAddress(1, 1, 0)),  # west edge belongs to the east tile
        ([0.0, 0.0], TileAddress(1, 1, 1)),  # equator belongs to the southern tile
        ([180.0, 45.0], TileAddress(1, 1, 0)),  # world edge is clamped into the last column
    ],
)
def test_point_on_tile_edge_is_in_exactly_one_tile(position, owner):
    owners = [
        TileAddress(1, x, y)
        for x in range(2)
        for y in range(2)
        if clip_point(position, TileAddress(1, x, y)) is not None
    ]
    assert owners == [owner]


# ---- clip_geometry ----


def test_geometry_point_kept_and_dropped():
    inside = {"type": "Point", "coordinates": [90, 45]}
    assert clip_geometry(inside, TILE) == inside
    assert clip_geometry({"type": "Point", "coordinates": [-90, 45]}, TILE) is None


def test_geometry_multipoint_keeps_members_inside():
    geometry = {"type": "MultiPoint", "coordinates": [[90, 45], [-90, 45], [100, 10]]}
    assert clip_geometry(geometry, TILE) == {
        "type": "MultiPoint",
        "coordinates": [[90, 45], [100, 10]],
    }


def test_geometry_multipoint_with_one_survivor_stays_multi():
    geometry = {"type": "MultiPoint", "coordinates": [[90, 45], [-90, 45]]}
    assert clip_geometry(geometry, TILE)["type"] == "MultiPoint"


def test_geometry_multipoint_all_outside_is_none():
    assert clip_geometry({"type": "MultiPoint", "coordinates": [[-90, 45]]}, TILE) is None


def test_geometry_linestring_one_piece_stays_linestring():
    geometry = {"type": "LineString", "coordinates": [[-10, 10], [10, 10]]}
    assert clip_geometry(geometry, TILE) == {"type": "LineString", "coordinates": [[0, 10], [10, 10]]}


def test_geometry_linestring_two_pieces_become_multilinestring():
    geometry = {"type": "LineString", "coordinates": [[10, 10], [-10, 10], [-10, 20], [10, 20]]}
    result = clip_geometry(geometry, TILE)
    assert result == {
        "type": "MultiLineString",
        "coordinates": [[[10, 10], [0, 10]], [[0, 20], [10, 20]]],
    }


def test_geometry_linestring_outside_is_none():
    assert clip_geometry({"type": "LineString", "coordinates": [[-20, 10], [-10, 10]]}, TILE) is None


def test_geometry_multilinestring_keeps_type_with_one_survivor():
    geometry = {
        "type": "MultiLineString",
        "coordinates": [[[-20, 10], [-10, 10]], [[10, 10], [20, 10]]],
    }
    assert clip_geometry(geometry, TILE) == {
        "type": "MultiLineString",
        "coordinates": [[[10, 10], [20, 10]]],
    }


def test_geometry_multilinestring_flattens_split_members():
    geometry = {
        "type": "MultiLineString",
        "coordinates": [[[10, 10], [-10, 10], [-10, 20], [10, 20]], [[5, 5], [6, 6]]],
    }
    result = clip_geometry(geometry, TILE)
    assert len(result["coordinates"]) == 3


def test_geometry_polygon_clipped_and_vanishing():
    polygon = {"type": "Polygon", "coordinates": [square(-10, 10, 10, 20)]}
    result = clip_geometry(polygon, TILE)
    assert result["type"] == "Polygon"
    assert ring_area(result["coordinates"][0]) == pytest.approx(10 * 10)
    far = {"type": "Polygon", "coordinates": [square(-50, 10, -10, 20)]}
    assert clip_geometry(far, TILE) is None


def test_geometry_multipolygon_keeps_survivors_only():
    geometry = {
        "type": "MultiPolygon",
        "coordinates": [[square(-50, 10, -10, 20)], [square(10, 10, 20, 20)]],
    }
    assert clip_geometry(geometry, TILE) == {
        "type": "MultiPolygon",
        "coordinates": [[square(10, 10, 20, 20)]],
    }


def test_geometry_multipolygon_all_outside_is_none():
    geometry = {"type": "MultiPolygon", "coordinates": [[square(-50, 10, -10, 20)]]}
    assert clip_geometry(geometry, TILE) is None


def test_geometry_collection_keeps_surviving_members():
    geometry = {
        "type": "GeometryCollection",
        "geometries": [
            {"type": "Point", "coordinates": [90, 45]},
            {"type": "Point", "coordinates": [-90, 45]},
            {"type": "LineString", "coordinates": [[-10, 10], [10, 10]]},
        ],
    }
    assert clip_geometry(geometry, TILE) == {
        "type": "GeometryCollection",
        "geometries": [
            {"type": "Point", "coordinates": [90, 45]},
            {"type": "LineString", "coordinates": [[0, 10], [10, 10]]},
        ],
    }


def test_geometry_collection_with_nothing_left_is_none():
    geometry = {
        "type": "GeometryCollection",
        "geometries": [{"type": "Point", "coordinates": [-90, 45]}],
    }
    assert clip_geometry(geometry, TILE) is None


def test_geometry_z_preserved_for_polygon_and_point():
    point = {"type": "Point", "coordinates": [90, 45, 5]}
    assert clip_geometry(point, TILE)["coordinates"] == [90, 45, 5]
    line = {"type": "LineString", "coordinates": [[-10, 10, 0], [10, 10, 20]]}
    assert clip_geometry(line, TILE)["coordinates"] == [[0, 10, 10], [10, 10, 20]]


def test_input_geometry_is_not_modified():
    coordinates = [[-10, 10], [10, 10]]
    geometry = {"type": "LineString", "coordinates": coordinates}
    clip_geometry(geometry, TILE)
    assert coordinates == [[-10, 10], [10, 10]]


# ---- property-style sanity: areas add up over all tiles ----


def test_clipped_areas_add_up_to_original_area():
    ring = [[-30, -20], [60, -25], [75, 40], [10, 55], [-35, 30], [-30, -20]]
    original = ring_area(ring)
    data = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }
    for zoom in (1, 2, 3):
        result = tile_geojson(data, min_zoom=zoom, max_zoom=zoom, clip=True)
        total = 0.0
        for tile, document in result.tiles.items():
            west, south, east, north = tile_bounds(tile)
            for feature in document["features"]:
                (clipped_ring,) = feature["geometry"]["coordinates"]
                assert all(
                    west <= x <= east and south <= y <= north for x, y in clipped_ring
                )
                total += ring_area(clipped_ring)
        assert total == pytest.approx(original, rel=1e-9)
