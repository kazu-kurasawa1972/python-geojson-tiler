# AGENTS.md

## Read this first
- Start with `description.md` for product intent, then `README.md` for the actual implemented workflow and user-facing behavior.
- The repo goal is a **Python-only GeoJSON tiler** that chunks large GeoJSON datasets into **XYZ tile** files.
- Keep the project beginner-friendly: when behavior changes, update `README.md` with copy-pasteable commands and concrete examples.

## Current architecture
- Source code lives under `src/geojson_tiler/` with a small, explicit module split:
  - `geojson.py`: load/normalize GeoJSON, validate supported geometry types, extract bounds
  - `xyz.py`: Web Mercator / XYZ tile math (`lonlat_to_tile`, `tile_bounds`, `tiles_for_bounds`)
  - `tiler.py`: main tiling pipeline; duplicates each feature into every intersecting tile across a zoom range
  - `writer.py`: writes `z/x/y.geojson` plus `metadata.json`
  - `cli.py`: argparse-based CLI and error handling
- The public package entrypoints are `geojson-tiler` and `python -m geojson_tiler`.

## Important product behavior
- This implementation is **bbox-based tiling**, not geometry clipping. A polygon/line is written in full to every intersecting tile.
- `null` geometries are allowed and skipped during tile generation.
- The tool accepts a top-level GeoJSON `Feature` or `FeatureCollection`; single features are normalized into a `FeatureCollection` internally.
- Output always includes `metadata.json` summarizing the source filename, total input feature count, tile count, and written tile paths.

## Developer workflow
- Set up the project with:
  - `python -m venv .venv`
  - `source .venv/bin/activate`
  - `python -m pip install -e ".[dev]"`
- Run tests with `python -m pytest`.
- Coverage is intentionally strict: `pyproject.toml` config requires **100% coverage** for `geojson_tiler`.
- After changing runnable behavior, smoke-test the CLI, not just unit tests; the README quickstart commands should remain accurate.

## Project-specific conventions
- Prefer the standard library over extra GIS dependencies unless the added complexity clearly pays off; the current implementation has no runtime dependencies.
- Keep file output predictable and static-host-friendly: tile files live at `OUTPUT/z/x/y.geojson`.
- When expanding the tiler, preserve the current documented semantics or update `README.md` and tests in the same change.
- `.gitignore` ignores `description.md`; treat it as local product-spec context unless the user asks to track it.

## Testing patterns to follow
- Tests live in `tests/` and currently cover CLI behavior, GeoJSON validation, XYZ math, tiling logic, writing, and module entrypoint import.
- Prefer small inline GeoJSON fixtures in tests unless a file fixture makes the behavior clearer.
- If you add a new module under `src/geojson_tiler/`, add direct tests for every error path; the repo is configured to fail below 100% coverage.


