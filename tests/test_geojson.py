import json

import pytest

from geojson_tiler.geojson import (
    GeoJSONError,
    feature_bounds,
    geometry_bounds,
    iter_geometry_positions,
    load_geojson,
    normalize_geojson,
    normalize_feature,
    validate_geometry,
)


POINT_FEATURE = {
    "type": "Feature",
    "properties": {"name": "Berlin"},
    "geometry": {"type": "Point", "coordinates": [13.405, 52.52]},
}


def test_load_geojson_normalizes_feature(tmp_path):
    input_path = tmp_path / "feature.geojson"
    input_path.write_text(json.dumps(POINT_FEATURE), encoding="utf-8")

    loaded = load_geojson(input_path)

    assert loaded["type"] == "FeatureCollection"
    assert loaded["features"][0]["properties"]["name"] == "Berlin"


def test_load_geojson_rejects_invalid_json(tmp_path):
    input_path = tmp_path / "broken.geojson"
    input_path.write_text("{", encoding="utf-8")

    with pytest.raises(GeoJSONError, match="Invalid JSON"):
        load_geojson(input_path)


def test_normalize_geojson_rejects_non_object_root():
    with pytest.raises(GeoJSONError, match="GeoJSON root must be an object"):
        normalize_geojson([])


def test_normalize_geojson_rejects_invalid_feature_collection():
    with pytest.raises(GeoJSONError, match="features must be a list"):
        normalize_geojson({"type": "FeatureCollection", "features": {}})


def test_normalize_geojson_rejects_invalid_root_type():
    with pytest.raises(GeoJSONError, match="Feature or FeatureCollection"):
        normalize_geojson({"type": "Polygon", "coordinates": []})


def test_normalize_feature_handles_missing_and_invalid_properties():
    normalized = normalize_feature(
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [0, 0]}}
    )

    assert normalized["properties"] == {}

    with pytest.raises(GeoJSONError, match="GeoJSON Feature"):
        normalize_feature({"type": "NotFeature"})

    with pytest.raises(GeoJSONError, match="object or null"):
        normalize_feature(
            {
                "type": "Feature",
                "properties": "bad",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
            }
        )


def test_validate_geometry_supports_geometry_collection():
    geometry = {
        "type": "GeometryCollection",
        "geometries": [
            {"type": "Point", "coordinates": [0, 0]},
            {"type": "LineString", "coordinates": [[1, 1], [2, 2]]},
        ],
    }

    validate_geometry(geometry)


def test_validate_geometry_rejects_bad_collection():
    with pytest.raises(GeoJSONError, match="geometries must be a list"):
        validate_geometry({"type": "GeometryCollection", "geometries": {}})


def test_validate_geometry_rejects_unsupported_type():
    with pytest.raises(GeoJSONError, match="Unsupported geometry type"):
        validate_geometry({"type": "CircularString", "coordinates": []})


def test_validate_geometry_requires_coordinates():
    with pytest.raises(GeoJSONError, match="must include coordinates"):
        validate_geometry({"type": "Point"})


def test_validate_geometry_rejects_non_object_geometry():
    with pytest.raises(GeoJSONError, match="must be an object"):
        validate_geometry("bad geometry")


def test_iter_geometry_positions_yields_for_nested_coordinates():
    geometry = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
    }

    positions = list(iter_geometry_positions(geometry))

    assert positions == [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)]


def test_iter_geometry_positions_accepts_none_geometry():
    assert list(iter_geometry_positions(None)) == []


def test_iter_geometry_positions_supports_geometry_collection():
    geometry = {
        "type": "GeometryCollection",
        "geometries": [
            {"type": "Point", "coordinates": [1, 2]},
            {"type": "LineString", "coordinates": [[3, 4], [5, 6]]},
        ],
    }

    assert list(iter_geometry_positions(geometry)) == [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]


def test_iter_geometry_positions_rejects_non_numeric_coordinates():
    with pytest.raises(GeoJSONError, match="numeric positions"):
        list(iter_geometry_positions({"type": "Point", "coordinates": ["x", 10]}))


def test_feature_bounds_and_geometry_bounds_handle_empty_and_null_geometries():
    feature = {"type": "Feature", "properties": {}, "geometry": None}
    empty_collection = {"type": "GeometryCollection", "geometries": []}

    assert feature_bounds(feature) is None
    assert geometry_bounds(empty_collection) is None


def test_feature_bounds_for_linestring():
    feature = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "LineString", "coordinates": [[2, 3], [10, -5], [4, 1]]},
    }

    assert feature_bounds(feature) == (2.0, -5.0, 10.0, 3.0)


