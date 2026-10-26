# python-geojson-tiler

`python-geojson-tiler` is a beginner-friendly Python tool for splitting large GeoJSON datasets into **XYZ tiles**.

If you have ever searched for **"how to serve big GeoJSON"**, this project is meant to be the simple answer: take one large GeoJSON file, break it into smaller tile-shaped chunks, and serve those files from a normal static web server.

This first version is intentionally simple:
- It reads a GeoJSON `Feature` or `FeatureCollection`
- It calculates each feature's geographic bounding box
- It writes every intersecting XYZ tile as `z/x/y.geojson`
- It duplicates features into every tile they touch
- It does **not** clip geometry to tile edges yet

That trade-off keeps the code easy to understand, easy to test, and easy to extend.

For more geospatial workflow ideas, see [Spatial Workflow](https://spatialworkflow.io/).

## Why use this?

Large GeoJSON files are awkward to ship directly to browsers and map clients. Tiling helps because clients can request only the small pieces they need for the current map view.

This project is useful when you want to:
- pre-split a GeoJSON file into web-friendly XYZ tile folders
- serve big GeoJSON from a basic file server or CDN
- build a simple pipeline without introducing a larger GIS stack yet
- understand the mechanics of XYZ tiling in plain Python

## Quickstart

### 1) Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install the project in editable mode

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 3) Create a tiny GeoJSON example

```bash
cat > sample.geojson <<'EOF'
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {"name": "Berlin"},
      "geometry": {"type": "Point", "coordinates": [13.405, 52.52]}
    },
    {
      "type": "Feature",
      "properties": {"name": "Paris"},
      "geometry": {"type": "Point", "coordinates": [2.3522, 48.8566]}
    }
  ]
}
EOF
```

### 4) Tile the file

```bash
geojson-tiler sample.geojson tiles --min-zoom 0 --max-zoom 2
```

### 5) Inspect the output

```bash
find tiles -maxdepth 4 -type f | sort
cat tiles/metadata.json
```

### 6) Serve the tile directory locally

```bash
cd tiles
python -m http.server 8000
```

Your files will then be available at paths like:
- `http://localhost:8000/0/0/0.geojson`
- `http://localhost:8000/1/1/0.geojson`

## Command-line usage

```bash
geojson-tiler INPUT OUTPUT [--min-zoom MIN] [--max-zoom MAX] [--max-tiles N] [--indent N] [--overwrite] [--quiet]
```

### Arguments

- `INPUT`: path to a GeoJSON file containing a `Feature` or `FeatureCollection`
- `OUTPUT`: directory that will receive XYZ tile folders
- `--min-zoom`: first zoom level to generate, default `0`, maximum `22`
- `--max-zoom`: last zoom level to generate, default `0`, maximum `22`
- `--max-tiles`: stop with an error if more than this many tiles would be created, default `100000`
- `--indent`: JSON indentation level for generated files (`0` or greater), default `2`
- `--overwrite`: allow writing into a non-empty output directory
- `--quiet`: skip the success summary message
- `--version`: print the installed version

### Default zoom behavior

With no zoom options, `--min-zoom` and `--max-zoom` are both `0`, so the tool writes only the single world tile `0/0/0.geojson`. To get more detailed tiles, raise `--max-zoom`:

```bash
geojson-tiler sample.geojson tiles --max-zoom 4
```

### Safety limits

Each zoom level has four times as many tiles as the one before, so a large feature at a high zoom can need an enormous number of tiles. Two guards keep that from running away:

- **Zoom cap:** zoom levels above `22` are rejected.
- **Tile limit:** `--max-tiles` (default `100000`) stops the run with an error as soon as more tiles than that would be needed. The check happens before the tiles are built, so it fails immediately instead of using up memory.

For example, this fails fast because a world-spanning line needs trillions of tiles at zoom 22:

```bash
cat > world-line.geojson <<'EOF'
{"type": "Feature", "properties": {}, "geometry": {"type": "LineString", "coordinates": [[-179, -80], [179, 80]]}}
EOF
geojson-tiler world-line.geojson world-tiles --max-zoom 22
```

Fix it by lowering `--max-zoom`, or raise the limit on purpose:

```bash
geojson-tiler world-line.geojson world-tiles --max-zoom 8
geojson-tiler world-line.geojson world-tiles --max-zoom 9 --max-tiles 1000000 --overwrite
```

In Python, pass `max_tiles=` to `tile_geojson`; it raises `TileLimitError` (a `ValueError`).

### Input restrictions

- `NaN`, `Infinity` and `-Infinity` are not valid JSON and are rejected with an error that names the problem. Replace them with real numbers or `null`.
- Extremely deeply nested input is rejected with a clean `Error:` message (exit code 2) instead of a traceback.

## Output layout

The generated directory structure looks like this:

```text
tiles/
├── metadata.json
├── 0/
│   └── 0/
│       └── 0.geojson
├── 1/
│   ├── 0/
│   │   ├── 0.geojson
│   │   └── 1.geojson
│   └── 1/
│       ├── 0.geojson
│       └── 1.geojson
└── ...
```

Each tile file is a valid GeoJSON `FeatureCollection`.

`metadata.json` includes:
- the original source filename
- total input feature count
- total tile count written
- a list of tile addresses and relative file paths

## Reducing tile size with property filters

Because features are duplicated into every tile they touch, big properties are repeated many times. Remove the ones your map does not need:

```bash
cat > props.geojson <<'EOF'
{"type": "Feature", "properties": {"name": "a", "pop": 5, "secret": "x"}, "geometry": {"type": "Point", "coordinates": [13.405, 52.52]}}
EOF
geojson-tiler props.geojson props-tiles --keep-properties name,pop
geojson-tiler props.geojson props-tiles-2 --drop-properties secret
```

Without a filter, `props-tiles/0/0/0.geojson` contains all three properties. With either command above it contains only:

```json
"properties": {"name": "a", "pop": 5}
```

- `--keep-properties NAMES` keeps only the listed properties.
- `--drop-properties NAMES` removes the listed properties and keeps the rest.
- Names are comma-separated; spaces around names are ignored and empty names (such as `a,,b`) are an error.
- Names that a feature does not have are ignored.
- The two options cannot be combined (exit code 2). By default all properties are kept.
- Geometry, `id` and other feature members are never changed.

In Python: `tile_geojson(data, keep_properties=["name", "pop"])` or `drop_properties=["secret"]`.

## Python API

You can also use the tiler directly from Python:

```python
from geojson_tiler.tiler import tile_geojson
from geojson_tiler.writer import write_tiles

geojson_data = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"name": "Example"},
            "geometry": {"type": "Point", "coordinates": [13.405, 52.52]},
        }
    ],
}

result = tile_geojson(geojson_data, min_zoom=0, max_zoom=2)
write_tiles(result, "tiles", source_name="example.geojson")
```

## Supported geometry types

This version supports bounding-box tiling for:
- `Point`
- `MultiPoint`
- `LineString`
- `MultiLineString`
- `Polygon`
- `MultiPolygon`
- `GeometryCollection`
- `null` geometry (skipped)

## Important behavior to know

### Features are duplicated, not clipped

If a feature overlaps multiple tiles, the full feature is written into every intersecting tile.

That means:
- output is easy to reason about
- output may be larger than a clipped-vector-tiles workflow
- tile borders can contain repeated features

For many beginner and static-serving workflows, this is a good first step.

### Coordinates use geographic longitude/latitude

The tool expects standard GeoJSON coordinates in longitude/latitude order (`[lon, lat]`). It clamps latitude to the Web Mercator limit used by XYZ tiles.

## Examples

### Generate one zoom level

```bash
geojson-tiler countries.geojson country-tiles --min-zoom 4 --max-zoom 4
```

### Generate a zoom range

```bash
geojson-tiler roads.geojson road-tiles --min-zoom 5 --max-zoom 8
```

### Re-run into an existing directory

```bash
geojson-tiler parcels.geojson parcel-tiles --min-zoom 10 --max-zoom 12 --overwrite
```

### Quiet mode for scripts

```bash
geojson-tiler input.geojson public/tiles --min-zoom 0 --max-zoom 3 --quiet
```

## Development

### Run the test suite

```bash
python -m pytest
```

### Check the CLI help

```bash
geojson-tiler --help
python -m geojson_tiler --help
```

### Build distribution files

```bash
python -m pip install build
python -m build
```

## Project structure

```text
src/geojson_tiler/
├── __init__.py
├── __main__.py
├── cli.py
├── filters.py
├── geojson.py
├── tiler.py
├── writer.py
└── xyz.py
tests/
```

## Limitations of the current version

This repository now contains a complete, runnable first version, but it is still intentionally small.

Current limitations:
- no geometry clipping at tile edges
- no simplification by zoom level
- no spatial index yet
- no direct shapefile reader yet

## Troubleshooting

### “Output directory is not empty”

Use `--overwrite` if you want to write into an existing output directory.

### “GeoJSON root must be a Feature or FeatureCollection”

The input file must be standard GeoJSON with a top-level `Feature` or `FeatureCollection` object.

### “This would create more than N tiles”

Lower `--max-zoom`, or raise `--max-tiles` if you really need that many tiles.

### My tiles seem duplicated

That is expected in this version when a feature spans multiple tiles. The tool duplicates full features into every intersecting tile rather than clipping them.

## Contributing

When you extend this project, please keep the beginner-friendly goal in mind:
- document new behavior in `README.md`
- keep CLI examples copy-pasteable
- preserve the Python-only implementation unless the project scope changes

For more spatial workflow ideas and tutorials, visit [https://spatialworkflow.io/](https://spatialworkflow.io/).

