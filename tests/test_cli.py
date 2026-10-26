import json
import subprocess
import sys

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



def test_main_success_output_has_exact_line_shapes(sample_input, tmp_path, capsys):
    output_dir = tmp_path / "tiles"

    exit_code = main([str(sample_input), str(output_dir), "--min-zoom", "0", "--max-zoom", "1"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    lines = captured.out.splitlines()
    assert lines[1].startswith("Largest tile: ")
    del lines[1]
    assert lines == [
        f"Wrote 2 tile file(s) from 1 feature(s) to {output_dir}",
        f"Metadata: {output_dir / 'metadata.json'}",
    ]


def test_main_writes_exact_tile_paths(sample_input, tmp_path):
    output_dir = tmp_path / "tiles"

    main([str(sample_input), str(output_dir), "--min-zoom", "0", "--max-zoom", "2", "--quiet"])

    written = sorted(p.relative_to(output_dir).as_posix() for p in output_dir.rglob("*") if p.is_file())
    assert written == ["0/0/0.geojson", "1/1/0.geojson", "2/2/1.geojson", "metadata.json"]
    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["source"] == "input.geojson"
    assert [t["path"] for t in metadata["tiles"]] == written[:-1]


def test_main_exits_2_on_invalid_json(tmp_path, capsys):
    bad = tmp_path / "bad.geojson"
    bad.write_text("{not json", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main([str(bad), str(tmp_path / "tiles")])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert captured.err.startswith("Error: Invalid JSON in ")
    assert captured.out == ""


def test_main_refuses_non_empty_output_without_overwrite(sample_input, tmp_path, capsys):
    output_dir = tmp_path / "tiles"
    output_dir.mkdir()
    existing = output_dir / "existing.txt"
    existing.write_text("original", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main([str(sample_input), str(output_dir)])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "not empty" in captured.err
    assert existing.read_text(encoding="utf-8") == "original"
    assert [p.name for p in output_dir.iterdir()] == ["existing.txt"]


def test_main_overwrite_allows_non_empty_output(sample_input, tmp_path):
    output_dir = tmp_path / "tiles"
    output_dir.mkdir()
    (output_dir / "existing.txt").write_text("original", encoding="utf-8")

    exit_code = main([str(sample_input), str(output_dir), "--overwrite", "--quiet"])

    assert exit_code == 0
    assert (output_dir / "existing.txt").read_text(encoding="utf-8") == "original"
    assert (output_dir / "0" / "0" / "0.geojson").exists()


def test_main_exits_2_on_negative_min_zoom(sample_input, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc_info:
        main([str(sample_input), str(tmp_path / "tiles"), "--min-zoom", "-1"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "non-negative integer" in captured.err


def test_main_exits_2_on_non_integer_max_zoom(sample_input, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc_info:
        main([str(sample_input), str(tmp_path / "tiles"), "--max-zoom", "abc"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "invalid int value: 'abc'" in captured.err


def test_main_twice_with_overwrite_gives_byte_identical_files(sample_input, tmp_path):
    output_dir = tmp_path / "tiles"
    args = [str(sample_input), str(output_dir), "--max-zoom", "2", "--overwrite", "--quiet"]

    main(args)
    first = {p.relative_to(output_dir): p.read_bytes() for p in output_dir.rglob("*") if p.is_file()}
    main(args)
    second = {p.relative_to(output_dir): p.read_bytes() for p in output_dir.rglob("*") if p.is_file()}

    assert first == second
    assert len(first) == 4


def test_real_entrypoint_version_via_subprocess():
    completed = subprocess.run(
        [sys.executable, "-m", "geojson_tiler", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stdout == f"geojson-tiler {__version__}\n"


def test_real_entrypoint_runs_end_to_end_via_subprocess(sample_input, tmp_path):
    output_dir = tmp_path / "tiles"

    completed = subprocess.run(
        [sys.executable, "-m", "geojson_tiler", str(sample_input), str(output_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stdout.startswith("Wrote 1 tile file(s) from 1 feature(s)")
    assert (output_dir / "0" / "0" / "0.geojson").exists()
