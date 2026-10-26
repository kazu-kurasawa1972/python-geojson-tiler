import json

import pytest

from geojson_tiler import cli
from geojson_tiler.cli import _non_negative_int, _positive_int, main

POINT = {
    "type": "Feature",
    "properties": {},
    "geometry": {"type": "Point", "coordinates": [1, 1]},
}


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "in.geojson"
    path.write_text(json.dumps(POINT), encoding="utf-8")
    return path


def run(capsys, *argv):
    with pytest.raises(SystemExit) as exc:
        main([str(a) for a in argv])
    return exc.value.code, capsys.readouterr().err


def test_zoom_above_cap_fails_cleanly(capsys, source, tmp_path):
    code, err = run(capsys, source, tmp_path / "out", "--max-zoom", "23")
    assert code == 2
    assert "Error:" in err and "22" in err
    assert not (tmp_path / "out").exists()


def test_max_tiles_error_mentions_options(capsys, tmp_path):
    path = tmp_path / "line.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "LineString", "coordinates": [[-179, -80], [179, 80]]},
            }
        ),
        encoding="utf-8",
    )
    code, err = run(capsys, path, tmp_path / "out", "--max-zoom", "22")
    assert code == 2
    assert "--max-zoom" in err and "--max-tiles" in err


def test_max_tiles_option_is_applied(capsys, source, tmp_path):
    code, err = run(capsys, source, tmp_path / "out", "--max-zoom", "2", "--max-tiles", "2")
    assert code == 2 and "--max-tiles" in err
    assert main([str(source), str(tmp_path / "ok"), "--max-zoom", "2", "--max-tiles", "3", "--quiet"]) == 0


def test_nan_input_reports_error(capsys, tmp_path):
    path = tmp_path / "nan.geojson"
    path.write_text(
        '{"type":"Feature","properties":{},"geometry":{"type":"Point","coordinates":[NaN,1]}}',
        encoding="utf-8",
    )
    code, err = run(capsys, path, tmp_path / "out")
    assert code == 2 and "NaN" in err


def test_deep_nesting_reports_error(capsys, tmp_path):
    path = tmp_path / "deep.geojson"
    path.write_text("[" * 100000 + "]" * 100000, encoding="utf-8")
    code, err = run(capsys, path, tmp_path / "out")
    assert code == 2 and "nested too deeply" in err


def test_recursion_error_from_pipeline_is_caught(capsys, source, tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise RecursionError

    monkeypatch.setattr(cli, "tile_geojson", boom)
    code, err = run(capsys, source, tmp_path / "out")
    assert code == 2 and err.startswith("Error:")


def test_negative_indent_is_rejected_by_argparse(capsys, source, tmp_path):
    code, err = run(capsys, source, tmp_path / "out", "--indent", "-1")
    assert code == 2 and "0 or greater" in err


def test_zero_max_tiles_is_rejected_by_argparse(capsys, source, tmp_path):
    code, err = run(capsys, source, tmp_path / "out", "--max-tiles", "0")
    assert code == 2 and "1 or greater" in err


def test_non_integer_option_is_rejected(capsys, source, tmp_path):
    code, err = run(capsys, source, tmp_path / "out", "--indent", "abc")
    assert code == 2 and "invalid int value" in err
    assert _non_negative_int("0") == 0 and _positive_int("5") == 5


def test_help_shows_defaults(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert "default: 0, maximum: 22" in out
    assert "only tile 0/0/0" in out
    assert "default: 100000" in out


def test_existing_output_error_mentions_overwrite_flag(capsys, source, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "x.txt").write_text("x", encoding="utf-8")
    code, err = run(capsys, source, out)
    assert code == 2 and "--overwrite" in err
