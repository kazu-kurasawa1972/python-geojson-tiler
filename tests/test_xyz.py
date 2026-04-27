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

