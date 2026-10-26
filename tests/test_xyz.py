import pytest

from geojson_tiler.xyz import (
    TileAddress,
    clamp_latitude,
    clamp_longitude,
    lonlat_to_tile,
    tile_bounds,
    tiles_for_bounds,
    validate_zoom,
)


def test_validate_zoom_rejects_invalid_values():
    with pytest.raises(ValueError, match="non-negative integer"):
        validate_zoom(-1)

    with pytest.raises(ValueError, match="non-negative integer"):
        validate_zoom(True)


def test_clamp_helpers_limit_world_extremes():
    assert clamp_longitude(-200) == -180.0
    assert clamp_longitude(200) < 180.0
    assert clamp_latitude(-100) == pytest.approx(-85.05112878)
    assert clamp_latitude(100) == pytest.approx(85.05112878)


def test_lonlat_to_tile_for_known_location():
    tile = lonlat_to_tile(13.405, 52.52, 2)

    assert tile == TileAddress(z=2, x=2, y=1)


def test_lonlat_to_tile_clamps_edges():
    tile = lonlat_to_tile(180, 90, 1)

    assert tile == TileAddress(z=1, x=1, y=0)


def test_tile_bounds_for_world_tile():
    bounds = tile_bounds(TileAddress(z=0, x=0, y=0))

    assert bounds[0] == pytest.approx(-180.0)
    assert bounds[2] == pytest.approx(180.0)
    assert bounds[1] < 0
    assert bounds[3] > 0


def test_tiles_for_bounds_returns_all_touched_tiles():
    tiles = tiles_for_bounds(bounds=(-10.0, -10.0, 10.0, 10.0), zoom=1)

    assert tiles == [
        TileAddress(z=1, x=0, y=0),
        TileAddress(z=1, x=0, y=1),
        TileAddress(z=1, x=1, y=0),
        TileAddress(z=1, x=1, y=1),
    ]


def test_tiles_for_bounds_normalizes_reversed_bounds():
    tiles = tiles_for_bounds(bounds=(10.0, 10.0, -10.0, -10.0), zoom=1)

    assert tiles[0] == TileAddress(z=1, x=0, y=0)
    assert tiles[-1] == TileAddress(z=1, x=1, y=1)



@pytest.mark.parametrize(
    ("lon", "expected_x"),
    [(-180, 0), (0, 4), (180, 7), (179.9999999, 7), (-179.9999999, 0)],
)
def test_lonlat_to_tile_longitude_edges_at_zoom_3(lon, expected_x):
    assert lonlat_to_tile(lon, 0, 3) == TileAddress(z=3, x=expected_x, y=4)


def test_lonlat_to_tile_latitude_zero_is_just_below_the_middle_row():
    assert lonlat_to_tile(0, 0, 1) == TileAddress(z=1, x=1, y=1)
    assert lonlat_to_tile(-0.0001, 0.0001, 1) == TileAddress(z=1, x=0, y=0)


def test_lonlat_to_tile_zoom_zero_is_always_the_single_tile():
    for lon, lat in [(-180, -90), (0, 0), (180, 90), (13.4, 52.5)]:
        assert lonlat_to_tile(lon, lat, 0) == TileAddress(z=0, x=0, y=0)


def test_lonlat_to_tile_clamps_poles_and_mercator_limit():
    assert lonlat_to_tile(0, 90, 2) == TileAddress(z=2, x=2, y=0)
    assert lonlat_to_tile(0, -90, 2) == TileAddress(z=2, x=2, y=3)
    assert lonlat_to_tile(0, 85.05112878, 2) == TileAddress(z=2, x=2, y=0)
    assert lonlat_to_tile(0, -85.05112878, 2) == TileAddress(z=2, x=2, y=3)


def test_lonlat_to_tile_rejects_negative_zoom():
    with pytest.raises(ValueError, match="non-negative integer"):
        lonlat_to_tile(0, 0, -1)


def test_tile_bounds_exact_values_for_zoom_0_and_1():
    west, south, east, north = tile_bounds(TileAddress(z=0, x=0, y=0))
    assert (west, east) == (-180.0, 180.0)
    assert north == pytest.approx(85.0511287798)
    assert south == pytest.approx(-85.0511287798)

    west, south, east, north = tile_bounds(TileAddress(z=1, x=1, y=0))
    assert (west, east) == (0.0, 180.0)
    assert north == pytest.approx(85.0511287798)
    assert south == pytest.approx(0.0, abs=1e-9)

    west, south, east, north = tile_bounds(TileAddress(z=1, x=0, y=1))
    assert (west, east) == (-180.0, 0.0)
    assert north == pytest.approx(0.0, abs=1e-9)
    assert south == pytest.approx(-85.0511287798)


def test_tile_bounds_center_round_trips_for_all_zoom_2_tiles():
    for x in range(4):
        for y in range(4):
            tile = TileAddress(z=2, x=x, y=y)
            west, south, east, north = tile_bounds(tile)
            center = ((west + east) / 2, (south + north) / 2)
            assert lonlat_to_tile(*center, 2) == tile


def test_tiles_for_bounds_single_point_bbox_returns_one_tile():
    assert tiles_for_bounds((13.4, 52.5, 13.4, 52.5), 2) == [TileAddress(z=2, x=2, y=1)]


def test_tiles_for_bounds_ending_exactly_on_tile_edge_includes_next_tile():
    # East edge 0.0 is the boundary between x=0 and x=1 at zoom 1. Bounds are
    # treated as closed, so the neighboring tile that only touches is included.
    tiles = tiles_for_bounds((-90.0, 10.0, 0.0, 20.0), 1)

    assert tiles == [TileAddress(z=1, x=0, y=0), TileAddress(z=1, x=1, y=0)]


def test_tiles_for_bounds_antimeridian_crossing_bbox_spans_whole_world():
    # CURRENT BEHAVIOR (possible bug): a bbox that crosses the antimeridian
    # (min_lon > max_lon) is treated as reversed bounds and swapped, so it
    # covers -170..170 (almost the whole world) instead of the two small
    # slivers at x=0 and x=1 around +-180. Expected: only the tiles near +-180,
    # which at zoom 1 are still x=0 and x=1, so this case cannot distinguish;
    # the wrongness shows at higher zoom (see the next test).
    tiles = tiles_for_bounds((170, -5, -170, 5), 1)

    assert tiles == [
        TileAddress(z=1, x=0, y=0),
        TileAddress(z=1, x=0, y=1),
        TileAddress(z=1, x=1, y=0),
        TileAddress(z=1, x=1, y=1),
    ]


def test_tiles_for_bounds_antimeridian_crossing_bbox_at_zoom_3():
    # CURRENT BEHAVIOR (possible bug): (170,-5,-170,5) is swapped to
    # (-170,-5,170,5) so every x column 0..7 is returned; a correct
    # antimeridian split would return only x=0 and x=7.
    tiles = tiles_for_bounds((170, -5, -170, 5), 3)

    assert sorted({tile.x for tile in tiles}) == list(range(8))
