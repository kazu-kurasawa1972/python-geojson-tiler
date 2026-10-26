import json

import pytest

from geojson_tiler.cli import build_parser, main
from geojson_tiler.tiler import TileLimitError, tile_geojson
from geojson_tiler.xyz import TileAddress, tile_bounds

POLYGON = {
    "type": "Feature",
    "id": "poly-1",
    "properties": {"name": "box", "secret": "x"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[-80, -60], [80, 60], [-80, 60], [-80, -60]]],
    },
}


def collection(*features):
    return {"type": "FeatureCollection", "features": list(features)}


def run_cli(tmp_path, data, *args):
    source = tmp_path / "in.geojson"
    source.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "out"
    assert main([str(source), str(out), "--quiet", *args]) == 0
    metadata = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    return out, metadata


def read_tile(out, z, x, y):
    return json.loads((out / str(z) / str(x) / f"{y}.geojson").read_text(encoding="utf-8"))


def test_clip_flag_defaults_to_off_and_help_mentions_it():
    assert build_parser().parse_args(["in", "out"]).clip is False
    assert build_parser().parse_args(["in", "out", "--clip"]).clip is True
    build_help = build_parser().format_help()
    assert "--clip" in build_help and "tile edges" in build_help


def test_without_clip_geometry_is_whole_in_every_tile(tmp_path):
    out, metadata = run_cli(tmp_path, POLYGON, "--max-zoom", "2")
    for entry in metadata["tiles"]:
        tile = read_tile(out, entry["z"], entry["x"], entry["y"])
        assert tile["features"][0]["geometry"] == POLYGON["geometry"]
    assert metadata["tile_count"] == 9


def test_clip_cuts_polygon_to_tile_bounds_and_drops_empty_tiles(tmp_path):
    out, metadata = run_cli(tmp_path, POLYGON, "--max-zoom", "2", "--clip")
    assert metadata["feature_count"] == 1
    assert metadata["tile_count"] == len(metadata["tiles"]) == 7
    for entry in metadata["tiles"]:
        assert entry["feature_count"] == 1
        west, south, east, north = tile_bounds(TileAddress(entry["z"], entry["x"], entry["y"]))
        tile = read_tile(out, entry["z"], entry["x"], entry["y"])
        for x, y in tile["features"][0]["geometry"]["coordinates"][0]:
            assert west <= x <= east and south <= y <= north


def test_clip_can_remove_tiles_that_only_matched_the_bounding_box(tmp_path):
    triangle = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-170, 60], [-100, 60], [-170, 80], [-170, 60]]],
        },
    }
    plain = tile_geojson(triangle, max_zoom=3)
    clipped = tile_geojson(triangle, max_zoom=3, clip=True)
    assert 0 < clipped.tile_count < plain.tile_count
    assert set(clipped.tiles) < set(plain.tiles)
    assert all(doc["features"] for doc in clipped.tiles.values())


def test_clip_removes_features_from_tiles_but_keeps_other_features(tmp_path):
    far = {
        "type": "Feature",
        "properties": {"name": "far"},
        "geometry": {"type": "Point", "coordinates": [-120, -30]},
    }
    out, metadata = run_cli(tmp_path, collection(POLYGON, far), "--max-zoom", "1", "--clip")
    assert metadata["feature_count"] == 2
    names = {
        entry["path"]: [f["properties"]["name"] for f in read_tile(out, entry["z"], entry["x"], entry["y"])["features"]]
        for entry in metadata["tiles"]
    }
    assert names["1/1/0.geojson"] == ["box"]
    assert names["1/0/1.geojson"] == ["box", "far"]
    assert names["0/0/0.geojson"] == ["box", "far"]
    assert "1/1/1.geojson" not in names


def test_clip_keeps_properties_id_and_works_with_keep_properties(tmp_path):
    out, _ = run_cli(tmp_path, POLYGON, "--max-zoom", "1", "--clip", "--keep-properties", "name")
    feature = read_tile(out, 1, 1, 0)["features"][0]
    assert feature["id"] == "poly-1"
    assert feature["properties"] == {"name": "box"}
    assert feature["geometry"]["coordinates"][0][0] != [-80, -60]


def test_clip_with_drop_properties(tmp_path):
    out, _ = run_cli(tmp_path, POLYGON, "--clip", "--drop-properties", "secret")
    assert read_tile(out, 0, 0, 0)["features"][0]["properties"] == {"name": "box"}


def test_clip_tile_stats_stay_consistent(tmp_path):
    out, metadata = run_cli(tmp_path, POLYGON, "--max-zoom", "2", "--clip")
    assert metadata["total_bytes"] == sum(entry["bytes"] for entry in metadata["tiles"])
    for entry in metadata["tiles"]:
        assert (out / entry["path"]).stat().st_size == entry["bytes"]


def test_antimeridian_feature_is_not_clipped(tmp_path):
    line = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "LineString", "coordinates": [[170, 10], [-170, 10]]},
    }
    clipped = tile_geojson(line, max_zoom=2, clip=True)
    plain = tile_geojson(line, max_zoom=2)
    assert clipped.tiles == plain.tiles
    for document in clipped.tiles.values():
        assert document["features"][0]["geometry"] == line["geometry"]


def test_null_geometry_still_skipped_with_clip(tmp_path):
    empty = {"type": "Feature", "properties": {}, "geometry": None}
    result = tile_geojson(collection(empty), clip=True)
    assert result.tiles == {}
    assert result.feature_count == 1


def test_max_tiles_counts_candidate_tiles_before_clipping():
    # The feature needs 4 candidate tiles at zoom 2, but clipping leaves only 3.
    with pytest.raises(TileLimitError):
        tile_geojson(POLYGON, min_zoom=2, max_zoom=2, max_tiles=3, clip=True)
    assert tile_geojson(POLYGON, min_zoom=2, max_zoom=2, max_tiles=4, clip=True).tile_count == 3
