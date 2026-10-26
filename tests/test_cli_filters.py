import json

import pytest

from geojson_tiler.cli import main


@pytest.fixture()
def source(tmp_path):
    path = tmp_path / "in.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "Feature",
                "properties": {"name": "a", "pop": 5, "secret": "x"},
                "geometry": {"type": "Point", "coordinates": [13.4, 52.5]},
            }
        ),
        encoding="utf-8",
    )
    return path


def _props(tmp_path):
    tile = json.loads((tmp_path / "out" / "0" / "0" / "0.geojson").read_text(encoding="utf-8"))
    return tile["features"][0]["properties"]


def test_keep_properties(source, tmp_path):
    assert main([str(source), str(tmp_path / "out"), "--quiet", "--keep-properties", "name, pop"]) == 0
    assert _props(tmp_path) == {"name": "a", "pop": 5}


def test_drop_properties(source, tmp_path):
    assert main([str(source), str(tmp_path / "out"), "--quiet", "--drop-properties", "secret"]) == 0
    assert _props(tmp_path) == {"name": "a", "pop": 5}


def test_default_keeps_everything(source, tmp_path):
    assert main([str(source), str(tmp_path / "out"), "--quiet"]) == 0
    assert _props(tmp_path) == {"name": "a", "pop": 5, "secret": "x"}


def test_both_options_exit_2(source, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main([str(source), str(tmp_path / "out"), "--keep-properties", "a", "--drop-properties", "b"])
    assert exc.value.code == 2
    assert "not allowed with" in capsys.readouterr().err


@pytest.mark.parametrize("option", ["--keep-properties", "--drop-properties"])
def test_empty_names_exit_2(source, tmp_path, capsys, option):
    with pytest.raises(SystemExit) as exc:
        main([str(source), str(tmp_path / "out"), option, "a,,b"])
    assert exc.value.code == 2
    assert "must not be empty" in capsys.readouterr().err
