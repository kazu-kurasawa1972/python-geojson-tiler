import pytest

from geojson_tiler.tiler import TileBuildResult, tile_geojson, validate_zoom_range
from geojson_tiler.xyz import TileAddress


def test_validate_zoom_range_rejects_inverted_ranges():
    with pytest.raises(ValueError, match="less than or equal"):
        validate_zoom_range(2, 1)


def test_tile_geojson_creates_tiles_across_zoom_range():
    data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Center square"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-10, -10], [10, -10], [10, 10], [-10, 10], [-10, -10]]],
                },
            }
        ],
    }

    result = tile_geojson(data, min_zoom=0, max_zoom=1)

    assert isinstance(result, TileBuildResult)
    assert result.feature_count == 1
    assert result.tile_count == 5
    assert TileAddress(z=0, x=0, y=0) in result.tiles
    assert TileAddress(z=1, x=1, y=1) in result.tiles


def test_tile_geojson_skips_null_geometry_but_counts_feature():
    data = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"name": "Empty"}, "geometry": None}
        ],
    }

    result = tile_geojson(data)

    assert result.feature_count == 1
    assert result.tile_count == 0
    assert result.tiles == {}


def test_tile_geojson_accepts_single_feature_root():
    data = {
        "type": "Feature",
        "properties": {"name": "Berlin"},
        "geometry": {"type": "Point", "coordinates": [13.405, 52.52]},
    }

    result = tile_geojson(data, min_zoom=2, max_zoom=2)

    assert result.tile_count == 1
    assert result.tiles[TileAddress(z=2, x=2, y=1)]["features"][0]["properties"]["name"] == "Berlin"

