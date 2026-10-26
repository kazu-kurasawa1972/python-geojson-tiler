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



def _point_feature(name):
    return {
        "type": "Feature",
        "properties": {"name": name},
        "geometry": {"type": "Point", "coordinates": [0, 0]},
    }


def _two_zoom_result():
    feature = _point_feature("Origin")
    collection = {"type": "FeatureCollection", "features": [feature]}
    return TileBuildResult(
        tiles={
            TileAddress(z=1, x=1, y=1): collection,
            TileAddress(z=0, x=0, y=0): collection,
            TileAddress(z=1, x=0, y=1): collection,
        },
        feature_count=1,
        tile_count=3,
    )


def test_write_tiles_metadata_full_content_for_two_zooms(tmp_path):
    output_dir = tmp_path / "tiles"

    returned = write_tiles(_two_zoom_result(), output_dir, source_name="in.geojson")

    sizes = [(output_dir / p).stat().st_size for p in ("0/0/0.geojson", "1/0/1.geojson", "1/1/1.geojson")]
    expected = {
        "source": "in.geojson",
        "feature_count": 1,
        "tile_count": 3,
        "tiles": [
            {"z": 0, "x": 0, "y": 0, "path": "0/0/0.geojson", "feature_count": 1, "bytes": sizes[0]},
            {"z": 1, "x": 0, "y": 1, "path": "1/0/1.geojson", "feature_count": 1, "bytes": sizes[1]},
            {"z": 1, "x": 1, "y": 1, "path": "1/1/1.geojson", "feature_count": 1, "bytes": sizes[2]},
        ],
        "total_bytes": sum(sizes),
    }
    assert returned == expected
    assert json.loads((output_dir / "metadata.json").read_text(encoding="utf-8")) == expected


def test_write_tiles_tile_files_round_trip(tmp_path):
    result = _two_zoom_result()

    write_tiles(result, tmp_path)

    for tile, payload in result.tiles.items():
        text = tile_path(tmp_path, tile).read_text(encoding="utf-8")
        assert json.loads(text) == payload


def test_write_tiles_indented_vs_compact_output(tmp_path):
    result = _two_zoom_result()

    write_tiles(result, tmp_path / "indented", indent=2)
    write_tiles(result, tmp_path / "compact", indent=None)

    tile = TileAddress(z=0, x=0, y=0)
    indented = tile_path(tmp_path / "indented", tile).read_text(encoding="utf-8")
    compact = tile_path(tmp_path / "compact", tile).read_text(encoding="utf-8")
    assert indented.startswith('{\n  "features"')
    assert indented.endswith("}\n")
    # CURRENT BEHAVIOR (possible bug): indent=None writes a single line with NO
    # trailing newline, while any indent writes a trailing newline. The CLI help
    # says "--indent 0" is "compact but multiline", yet the CLI passes 0 straight
    # to json.dumps (newlines, no indentation), so None and 0 differ. Expected:
    # consistent trailing newline for every output mode.
    assert "\n" not in compact
    assert json.loads(compact) == json.loads(indented)


def test_write_tiles_indent_zero_is_multiline_with_trailing_newline(tmp_path):
    write_tiles(_two_zoom_result(), tmp_path, indent=0)

    text = tile_path(tmp_path, TileAddress(z=0, x=0, y=0)).read_text(encoding="utf-8")
    assert text.startswith('{\n"features"')
    assert text.endswith("\n")


def test_write_tiles_overwrite_replaces_tile_and_keeps_unrelated_files(tmp_path):
    output_dir = tmp_path / "tiles"
    stale_tile = output_dir / "0" / "0" / "0.geojson"
    stale_tile.parent.mkdir(parents=True)
    stale_tile.write_text("stale", encoding="utf-8")
    unrelated = output_dir / "notes.txt"
    unrelated.write_text("keep me", encoding="utf-8")
    orphan_tile = output_dir / "5" / "1" / "1.geojson"
    orphan_tile.parent.mkdir(parents=True)
    orphan_tile.write_text("orphan", encoding="utf-8")

    write_tiles(_two_zoom_result(), output_dir, overwrite=True)

    assert json.loads(stale_tile.read_text(encoding="utf-8"))["type"] == "FeatureCollection"
    assert unrelated.read_text(encoding="utf-8") == "keep me"
    # Tiles from earlier runs that are not part of this result are not removed.
    assert orphan_tile.read_text(encoding="utf-8") == "orphan"


def test_write_tiles_accepts_existing_empty_directory_without_overwrite(tmp_path):
    output_dir = tmp_path / "tiles"
    output_dir.mkdir()

    metadata = write_tiles(_two_zoom_result(), output_dir, overwrite=False)

    assert metadata["tile_count"] == 3
    assert (output_dir / "metadata.json").exists()
