"""Tests for empty coordinates, trailing newlines and CLI-friendly messages."""

import json

import pytest

from geojson_tiler.cli import main
from geojson_tiler.tiler import TileLimitError, tile_geojson, validate_zoom_range
from geojson_tiler.writer import write_tiles

EMPTY_GEOMETRIES = [
    {"type": "Point", "coordinates": []},
    {"type": "LineString", "coordinates": []},
    {"type": "Polygon", "coordinates": []},
    {"type": "MultiPoint", "coordinates": []},
    {"type": "MultiLineString", "coordinates": []},
    {"type": "MultiPolygon", "coordinates": []},
    {"type": "GeometryCollection", "geometries": []},
]


def _feature(geometry):
    return {"type": "Feature", "properties": {}, "geometry": geometry}


@pytest.mark.parametrize("geometry", EMPTY_GEOMETRIES, ids=lambda g: g["type"])
def test_empty_coordinates_are_counted_but_produce_no_tile(geometry):
    result = tile_geojson(_feature(geometry), min_zoom=0, max_zoom=2)

    assert result.feature_count == 1
    assert result.tiles == {}


def _write(tmp_path, indent):
    data = {"type": "FeatureCollection", "features": [_feature({"type": "Point", "coordinates": [1, 2]})]}
    write_tiles(tile_geojson(data), tmp_path, indent=indent)
    return [tmp_path / "metadata.json", tmp_path / "0" / "0" / "0.geojson"]


@pytest.mark.parametrize("indent", [None, 0, 2])
def test_every_written_file_ends_with_exactly_one_newline(tmp_path, indent):
    for path in _write(tmp_path, indent):
        text = path.read_text(encoding="utf-8")
        assert text.endswith("}\n") and not text.endswith("\n\n")


def test_written_byte_count_includes_trailing_newline(tmp_path):
    tile = tmp_path / "0" / "0" / "0.geojson"
    _write(tmp_path, None)

    metadata = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["tiles"][0]["bytes"] == tile.stat().st_size


def test_error_messages_do_not_mention_python_parameter_names(tmp_path):
    (tmp_path / "x").write_text("x", encoding="utf-8")
    result = tile_geojson(_feature({"type": "Point", "coordinates": [0, 0]}))
    line = {"type": "LineString", "coordinates": [[-179, -80], [179, 80]]}
    messages = []
    with pytest.raises(FileExistsError) as exc:
        write_tiles(result, tmp_path)
    messages.append(str(exc.value))
    with pytest.raises(TileLimitError) as exc:
        tile_geojson(_feature(line), max_zoom=22)
    messages.append(str(exc.value))
    with pytest.raises(ValueError) as exc:
        validate_zoom_range(3, 1)
    messages.append(str(exc.value))

    for message in messages:
        assert "max_" not in message and "min_" not in message and "=True" not in message
    assert "--overwrite" in messages[0]
    assert "(--max-zoom)" in messages[1] and "(--max-tiles)" in messages[1]


def test_cli_end_to_end_with_empty_point(tmp_path, capsys):
    source = tmp_path / "in.geojson"
    source.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    _feature({"type": "Point", "coordinates": []}),
                    _feature({"type": "Point", "coordinates": [10, 10]}),
                ],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out"

    assert main([str(source), str(out), "--max-zoom", "1", "--indent", "0"]) == 0

    metadata = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["feature_count"] == 2
    assert metadata["tile_count"] == 2
    assert (out / "metadata.json").read_bytes().endswith(b"\n")
    capsys.readouterr()
