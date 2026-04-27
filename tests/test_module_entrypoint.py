import importlib


def test_package_module_entrypoint_is_importable():
    module = importlib.import_module("geojson_tiler.__main__")

    assert module.main is not None

