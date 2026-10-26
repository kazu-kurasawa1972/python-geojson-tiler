import pytest

from geojson_tiler.filters import filter_feature, filter_properties, parse_property_names
from geojson_tiler.tiler import tile_geojson

PROPS = {"name": "a", "pop": 5, "secret": "x"}


def _collection():
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": 7,
                "properties": dict(PROPS),
                "geometry": {"type": "Point", "coordinates": [1, 1]},
            },
            {"type": "Feature", "properties": dict(PROPS), "geometry": None},
        ],
    }


def test_parse_trims_whitespace():
    assert parse_property_names(" name , pop ") == ["name", "pop"]


@pytest.mark.parametrize("text", ["", "a,,b", "a,", " , "])
def test_parse_rejects_empty_names(text):
    with pytest.raises(ValueError, match="empty"):
        parse_property_names(text)


def test_keep():
    assert filter_properties(PROPS, keep=["name", "pop"]) == {"name": "a", "pop": 5}


def test_keep_missing_names_ignored():
    assert filter_properties(PROPS, keep=["nope"]) == {}


def test_drop():
    assert filter_properties(PROPS, drop=["secret"]) == {"name": "a", "pop": 5}


def test_drop_missing_names_ignored():
    assert filter_properties(PROPS, drop=["nope"]) == PROPS


def test_no_filter_returns_copy():
    result = filter_properties(PROPS)
    assert result == PROPS
    assert result is not PROPS


def test_none_properties():
    assert filter_properties(None, keep=["a"]) == {}
    assert filter_properties(None, drop=["a"]) == {}


def test_both_rejected():
    with pytest.raises(ValueError, match="not both"):
        filter_properties(PROPS, keep=["a"], drop=["b"])


def test_filter_feature_does_not_mutate_and_keeps_members():
    feature = {"type": "Feature", "id": 1, "properties": dict(PROPS), "geometry": None}
    result = filter_feature(feature, drop=["secret"])
    assert result == {"type": "Feature", "id": 1, "properties": {"name": "a", "pop": 5}, "geometry": None}
    assert feature["properties"] == PROPS


def test_filter_feature_without_properties_key():
    assert filter_feature({"type": "Feature"}, keep=["a"])["properties"] == {}


def test_tile_geojson_keep_and_input_untouched():
    data = _collection()
    result = tile_geojson(data, keep_properties=["name"])
    feature = result.tiles[next(iter(result.tiles))]["features"][0]
    assert feature["properties"] == {"name": "a"}
    assert feature["id"] == 7
    assert data == _collection()


def test_tile_geojson_drop():
    result = tile_geojson(_collection(), drop_properties=["secret", "pop"])
    feature = next(iter(result.tiles.values()))["features"][0]
    assert feature["properties"] == {"name": "a"}


def test_tile_geojson_default_keeps_all():
    result = tile_geojson(_collection())
    assert next(iter(result.tiles.values()))["features"][0]["properties"] == PROPS


def test_tile_geojson_both_rejected():
    with pytest.raises(ValueError, match="not both"):
        tile_geojson(_collection(), keep_properties=["a"], drop_properties=["b"])
