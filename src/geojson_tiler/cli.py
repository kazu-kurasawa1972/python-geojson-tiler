from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from . import __version__
from .geojson import GeoJSONError, load_geojson
from .tiler import tile_geojson
from .writer import write_tiles


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="geojson-tiler",
        description="Chunk a GeoJSON file into XYZ tile GeoJSON files.",
    )
    parser.add_argument("input", help="Path to a GeoJSON Feature or FeatureCollection file.")
    parser.add_argument("output", help="Directory where XYZ tile files will be written.")
    parser.add_argument("--min-zoom", type=int, default=0, help="Lowest zoom level to generate.")
    parser.add_argument("--max-zoom", type=int, default=0, help="Highest zoom level to generate.")
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Indent level for generated JSON files. Use 0 for compact but multiline output.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow writing into a non-empty output directory.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Skip the success summary message.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        data = load_geojson(args.input)
        result = tile_geojson(data, min_zoom=args.min_zoom, max_zoom=args.max_zoom)
        metadata = write_tiles(
            result,
            args.output,
            indent=args.indent,
            overwrite=args.overwrite,
            source_name=Path(args.input).name,
        )
    except (GeoJSONError, OSError, ValueError, FileExistsError) as exc:
        parser.exit(2, f"Error: {exc}\n")

    if not args.quiet:
        print(
            f"Wrote {metadata['tile_count']} tile file(s) from {metadata['feature_count']} "
            f"feature(s) to {args.output}"
        )
        print(f"Metadata: {Path(args.output) / 'metadata.json'}")

    return 0

