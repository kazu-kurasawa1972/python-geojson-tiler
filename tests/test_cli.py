import json

import pytest

from geojson_tiler import __version__
from geojson_tiler.cli import build_parser, main


@pytest.fixture()
def sample_input(tmp_path):
    input_path = tmp_path / "input.geojson"
    input_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "Berlin"},
                        "geometry": {"type": "Point", "coordinates": [13.405, 52.52]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return input_path


def test_build_parser_has_expected_program_name():
    parser = build_parser()

    assert parser.prog == "geojson-tiler"


def test_main_writes_tiles_and_reports_summary(sample_input, tmp_path, capsys):
    output_dir = tmp_path / "tiles"

    exit_code = main([str(sample_input), str(output_dir), "--min-zoom", "0", "--max-zoom", "1"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Wrote" in captured.out
    assert (output_dir / "metadata.json").exists()


def test_main_supports_quiet_mode(sample_input, tmp_path, capsys):
    output_dir = tmp_path / "tiles"

    exit_code = main([str(sample_input), str(output_dir), "--quiet"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""


def test_main_exits_on_missing_input(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc_info:
        main([str(tmp_path / "missing.geojson"), str(tmp_path / "tiles")])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "Error:" in captured.err


def test_main_exits_on_invalid_zoom_range(sample_input, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc_info:
        main([str(sample_input), str(tmp_path / "tiles"), "--min-zoom", "2", "--max-zoom", "1"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "min_zoom" in captured.err


def test_main_supports_version_flag(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert __version__ in captured.out

