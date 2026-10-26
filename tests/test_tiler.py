import copy

import pytest

from geojson_tiler.geojson import GeoJSONError
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



def _feature(geometry, properties=None):
    return {"type": "Feature", "properties": properties, "geometry": geometry}


def test_multipolygon_with_distant_parts_puts_whole_feature_in_each_tile():
    geometry = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[-100, 10], [-90, 10], [-90, 20], [-100, 20], [-100, 10]]],
            [[[90, -20], [100, -20], [100, -10], [90, -10], [90, -20]]],
        ],
    }

    result = tile_geojson(_feature(geometry, {}), min_zoom=1, max_zoom=1)

    # The bbox spans all four z1 tiles, and each tile holds the full unclipped feature.
    assert result.tile_count == 4
    for document in result.tiles.values():
        assert [f["geometry"] for f in document["features"]] == [geometry]


def test_geometry_collection_uses_combined_bounds():
    geometry = {
        "type": "GeometryCollection",
        "geometries": [
            {"type": "Point", "coordinates": [-90, 45]},
            {"type": "LineString", "coordinates": [[90, -45], [100, -40]]},
        ],
    }

    result = tile_geojson(_feature(geometry, {}), min_zoom=1, max_zoom=1)

    assert sorted(result.tiles) == [
        TileAddress(z=1, x=0, y=0),
        TileAddress(z=1, x=0, y=1),
        TileAddress(z=1, x=1, y=0),
        TileAddress(z=1, x=1, y=1),
    ]


def test_point_with_z_coordinate_is_preserved():
    geometry = {"type": "Point", "coordinates": [13.405, 52.52, 34.0]}

    result = tile_geojson(_feature(geometry, {}), min_zoom=2, max_zoom=2)

    feature = result.tiles[TileAddress(z=2, x=2, y=1)]["features"][0]
    assert feature["geometry"]["coordinates"] == [13.405, 52.52, 34.0]


def test_point_with_empty_coordinates_is_counted_but_produces_no_tile():
    # CURRENT BEHAVIOR (possible bug): {"type": "Point", "coordinates": []} passes
    # validation and is silently skipped like a null geometry. Per RFC 7946 a
    # Point needs a position, so this probably should raise GeoJSONError.
    geometry = {"type": "Point", "coordinates": []}

    result = tile_geojson(_feature(geometry, {}))

    assert result.feature_count == 1
    assert result.tiles == {}


def test_null_geometry_among_real_features_is_counted_without_tile():
    data = {
        "type": "FeatureCollection",
        "features": [
            _feature(None, {}),
            _feature({"type": "Point", "coordinates": [0, 0]}, {}),
        ],
    }

    result = tile_geojson(data, min_zoom=0, max_zoom=0)

    assert result.feature_count == 2
    assert result.tile_count == 1
    assert len(result.tiles[TileAddress(z=0, x=0, y=0)]["features"]) == 1


def test_boolean_coordinates_are_rejected():
    geometry = {"type": "Point", "coordinates": [True, False]}

    with pytest.raises(GeoJSONError, match="numeric positions"):
        tile_geojson(_feature(geometry, {}))


def test_tile_geojson_does_not_mutate_input():
    data = {
        "type": "FeatureCollection",
        "features": [
            _feature({"type": "Point", "coordinates": [10, 10]}, None),
            _feature(None, {"a": 1}),
        ],
    }
    snapshot = copy.deepcopy(data)

    tile_geojson(data, min_zoom=0, max_zoom=2)

    assert data == snapshot
    assert data["features"][0]["properties"] is None


def test_null_properties_become_empty_object_in_tiles():
    geometry = {"type": "Point", "coordinates": [10, 10]}

    result = tile_geojson(_feature(geometry, None))

    feature = result.tiles[TileAddress(z=0, x=0, y=0)]["features"][0]
    assert feature["properties"] == {}


def test_min_zoom_equal_to_max_zoom_produces_only_that_zoom():
    geometry = {"type": "Point", "coordinates": [10, 10]}

    result = tile_geojson(_feature(geometry, {}), min_zoom=3, max_zoom=3)

    assert [tile.z for tile in result.tiles] == [3]


def test_small_square_full_tile_set_for_zoom_0_to_1():
    geometry = {
        "type": "Polygon",
        "coordinates": [[[-10, -10], [10, -10], [10, 10], [-10, 10], [-10, -10]]],
    }

    result = tile_geojson(_feature(geometry, {}), min_zoom=0, max_zoom=1)

    assert list(result.tiles) == [
        TileAddress(z=0, x=0, y=0),
        TileAddress(z=1, x=0, y=0),
        TileAddress(z=1, x=0, y=1),
        TileAddress(z=1, x=1, y=0),
        TileAddress(z=1, x=1, y=1),
    ]
    assert result.tile_count == 5
    for document in result.tiles.values():
        assert document["type"] == "FeatureCollection"
        assert [f["geometry"] for f in document["features"]] == [geometry]
