import json

import pytest

from geojson_tiler.cli import build_parser, largest_tile_line, main, oversized_tile_warnings


@pytest.fixture()
def sample_input(tmp_path):
    path = tmp_path / "input.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "Point", "coordinates": [13.405, 52.52]},
            }
        ),
        encoding="utf-8",
    )
    return path


def _entries(sizes):
    return [{"z": 0, "x": i, "y": 0, "bytes": size} for i, size in enumerate(sizes)]


def test_warn_tile_bytes_defaults_to_500000():
    args = build_parser().parse_args(["in.geojson", "out"])

    assert args.warn_tile_bytes == 500000


@pytest.mark.parametrize("value", ["0", "-5", "abc"])
def test_warn_tile_bytes_rejects_invalid_values(value, capsys):
    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args(["in.geojson", "out", "--warn-tile-bytes", value])

    assert exc_info.value.code == 2
    assert "--warn-tile-bytes" in capsys.readouterr().err


def test_oversized_tile_warnings_lists_only_tiles_over_limit():
    lines = oversized_tile_warnings(_entries([10, 11, 12]), 10)

    assert lines == [
        "Warning: tile 0/1/0 is 11 bytes (limit 10)",
        "Warning: tile 0/2/0 is 12 bytes (limit 10)",
    ]


def test_oversized_tile_warnings_caps_at_five_and_counts_the_rest():
    lines = oversized_tile_warnings(_entries([100] * 8), 1)

    assert len(lines) == 6
    assert lines[4] == "Warning: tile 0/4/0 is 100 bytes (limit 1)"
    assert lines[5] == "... and 3 more"


def test_oversized_tile_warnings_exactly_five_has_no_summary():
    lines = oversized_tile_warnings(_entries([100] * 5), 1)

    assert len(lines) == 5
    assert not any(line.startswith("...") for line in lines)


def test_largest_tile_line_picks_biggest_and_handles_empty():
    assert largest_tile_line(_entries([5, 9, 7])) == "Largest tile: 0/1/0 (9 bytes)"
    assert largest_tile_line([]) is None


def test_main_prints_largest_tile_after_wrote_line(sample_input, tmp_path, capsys):
    output_dir = tmp_path / "tiles"

    exit_code = main([str(sample_input), str(output_dir), "--max-zoom", "1"])

    captured = capsys.readouterr()
    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    tile = metadata["tiles"][0]
    lines = captured.out.splitlines()
    assert exit_code == 0
    assert lines[0].startswith("Wrote ")
    assert lines[1] == f"Largest tile: {tile['z']}/{tile['x']}/{tile['y']} ({tile['bytes']} bytes)"
    assert captured.err == ""


def test_main_warns_on_stderr_but_exits_zero(sample_input, tmp_path, capsys):
    output_dir = tmp_path / "tiles"

    exit_code = main([str(sample_input), str(output_dir), "--max-zoom", "1", "--warn-tile-bytes", "1"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err.startswith("Warning: tile 0/0/0 is ")
    assert captured.err.splitlines()[0].endswith("bytes (limit 1)")
    assert "Warning" not in captured.out


def test_main_quiet_still_warns_but_skips_largest_tile(sample_input, tmp_path, capsys):
    exit_code = main(
        [str(sample_input), str(tmp_path / "t"), "--quiet", "--warn-tile-bytes", "1"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    assert "Warning: tile 0/0/0" in captured.err


def test_main_skips_largest_line_when_no_tiles_written(tmp_path, capsys):
    empty = tmp_path / "empty.geojson"
    empty.write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")

    exit_code = main([str(empty), str(tmp_path / "t")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Largest tile" not in captured.out
