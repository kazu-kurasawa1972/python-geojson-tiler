import json

from geojson_tiler.tiler import TileBuildResult
from geojson_tiler.writer import write_tiles
from geojson_tiler.xyz import TileAddress


def _feature(name):
    return {
        "type": "Feature",
        "properties": {"name": name},
        "geometry": {"type": "Point", "coordinates": [0, 0]},
    }


def _result():
    return TileBuildResult(
        tiles={
            TileAddress(z=0, x=0, y=0): {
                "type": "FeatureCollection",
                "features": [_feature("a"), _feature("b")],
            },
            TileAddress(z=1, x=0, y=1): {
                "type": "FeatureCollection",
                "features": [_feature("a")],
            },
        },
        feature_count=2,
        tile_count=2,
    )


def test_metadata_records_feature_count_and_bytes_per_tile(tmp_path):
    metadata = write_tiles(_result(), tmp_path)

    first, second = metadata["tiles"]
    assert first["feature_count"] == 2
    assert second["feature_count"] == 1
    assert first["bytes"] == (tmp_path / "0" / "0" / "0.geojson").stat().st_size
    assert second["bytes"] == (tmp_path / "1" / "0" / "1.geojson").stat().st_size
    assert first["bytes"] > second["bytes"]


def test_total_bytes_is_sum_of_tile_bytes_and_saved_in_metadata_json(tmp_path):
    metadata = write_tiles(_result(), tmp_path, indent=None)

    assert metadata["total_bytes"] == sum(t["bytes"] for t in metadata["tiles"])
    saved = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert saved["total_bytes"] == metadata["total_bytes"]
    assert saved["tiles"][0]["bytes"] == metadata["tiles"][0]["bytes"]


def test_empty_result_has_zero_total_bytes(tmp_path):
    metadata = write_tiles(TileBuildResult(tiles={}, feature_count=0, tile_count=0), tmp_path)

    assert metadata["total_bytes"] == 0
    assert metadata["tiles"] == []
