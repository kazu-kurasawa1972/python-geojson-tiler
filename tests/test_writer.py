import json

import pytest

from geojson_tiler.tiler import TileBuildResult
from geojson_tiler.writer import tile_path, write_tiles
from geojson_tiler.xyz import TileAddress


def test_tile_path_builds_xyz_output_path(tmp_path):
    tile = TileAddress(z=3, x=4, y=5)

    assert tile_path(tmp_path, tile) == tmp_path / "3" / "4" / "5.geojson"


def test_write_tiles_writes_geojson_and_metadata(tmp_path):
    result = TileBuildResult(
        tiles={
            TileAddress(z=0, x=0, y=0): {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "Origin"},
                        "geometry": {"type": "Point", "coordinates": [0, 0]},
                    }
                ],
            }
        },
        feature_count=1,
        tile_count=1,
    )

    metadata = write_tiles(result, tmp_path / "tiles", source_name="sample.geojson")

    tile_file = tmp_path / "tiles" / "0" / "0" / "0.geojson"
    assert tile_file.exists()
    assert json.loads(tile_file.read_text(encoding="utf-8"))["type"] == "FeatureCollection"
    assert metadata["source"] == "sample.geojson"
    assert metadata["tiles"][0]["path"] == "0/0/0.geojson"


def test_write_tiles_rejects_non_empty_output_without_overwrite(tmp_path):
    output_dir = tmp_path / "tiles"
    output_dir.mkdir()
    (output_dir / "existing.txt").write_text("keep", encoding="utf-8")
    result = TileBuildResult(tiles={}, feature_count=0, tile_count=0)

    with pytest.raises(FileExistsError, match="not empty"):
        write_tiles(result, output_dir)


def test_write_tiles_allows_overwrite_and_compact_output(tmp_path):
    output_dir = tmp_path / "tiles"
    output_dir.mkdir()
    (output_dir / "existing.txt").write_text("keep", encoding="utf-8")
    result = TileBuildResult(tiles={}, feature_count=0, tile_count=0)

    metadata = write_tiles(result, output_dir, overwrite=True, indent=None)

    assert metadata["tile_count"] == 0
    assert json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))["tiles"] == []

