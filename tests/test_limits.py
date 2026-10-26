import json

import pytest

from geojson_tiler.geojson import GeoJSONError, load_geojson, normalize_geojson
from geojson_tiler.tiler import TileLimitError, tile_geojson
from geojson_tiler.xyz import MAX_ZOOM, count_tiles_for_bounds, tile_ranges, validate_zoom

WORLD_LINE = {
    "type": "Feature",
    "properties": {},
    "geometry": {"type": "LineString", "coordinates": [[-179, -80], [179, 80]]},
}


def point(lon, lat):
    return {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def test_validate_zoom_accepts_max_and_rejects_above():
    validate_zoom(MAX_ZOOM)
    assert MAX_ZOOM == 22
    with pytest.raises(ValueError, match="maximum supported zoom is 22"):
        validate_zoom(MAX_ZOOM + 1)


def test_tile_ranges_and_count_do_not_build_tiles():
    x_range, y_range = tile_ranges((-10.0, -10.0, 10.0, 10.0), 1)
    assert (list(x_range), list(y_range)) == ([0, 1], [0, 1])
    assert count_tiles_for_bounds((-179.0, -80.0, 179.0, 80.0), 22) > 10**12


def test_huge_feature_fails_fast_before_building_tiles():
    with pytest.raises(TileLimitError, match="Lower the maximum zoom.*--max-zoom.*raise the tile limit.*--max-tiles"):
        tile_geojson(WORLD_LINE, min_zoom=0, max_zoom=22)


def test_distinct_tile_total_is_limited():
    data = {"type": "FeatureCollection", "features": [point(-90, 45), point(90, -45)]}
    with pytest.raises(TileLimitError):
        tile_geojson(data, min_zoom=0, max_zoom=1, max_tiles=2)
    assert tile_geojson(data, min_zoom=0, max_zoom=1, max_tiles=3).tile_count == 3


def test_many_features_in_same_tile_are_not_counted_repeatedly():
    data = {"type": "FeatureCollection", "features": [point(1, 1)] * 5}
    assert tile_geojson(data, max_tiles=1).tile_count == 1


@pytest.mark.parametrize("bad", [0, -1, True, 1.5])
def test_invalid_max_tiles_rejected(bad):
    with pytest.raises(ValueError, match="max_tiles"):
        tile_geojson(point(0, 0), max_tiles=bad)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_load_rejects_non_finite_constants(tmp_path, constant):
    path = tmp_path / "bad.geojson"
    path.write_text(
        '{"type": "Feature", "properties": {}, "geometry": '
        f'{{"type": "Point", "coordinates": [{constant}, 1]}}}}',
        encoding="utf-8",
    )
    with pytest.raises(GeoJSONError, match=constant):
        load_geojson(path)


def test_load_deeply_nested_json_raises_geojson_error(tmp_path):
    path = tmp_path / "deep.geojson"
    path.write_text("[" * 100000 + "]" * 100000, encoding="utf-8")
    with pytest.raises(GeoJSONError, match="nested too deeply"):
        load_geojson(path)


def test_normalize_deeply_nested_geometry_raises_geojson_error():
    geometry = {"type": "Point", "coordinates": [0, 0]}
    for _ in range(5000):
        geometry = {"type": "GeometryCollection", "geometries": [geometry]}
    feature = {"type": "Feature", "properties": {}, "geometry": geometry}
    with pytest.raises(GeoJSONError, match="nested too deeply"):
        normalize_geojson(feature)


def test_normal_nesting_still_works():
    assert json.dumps(normalize_geojson(point(0, 0)))
