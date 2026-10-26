from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from . import __version__
from .geojson import load_geojson
from .tiler import DEFAULT_MAX_TILES, tile_geojson, validate_zoom_range
from .writer import write_tiles
from .xyz import MAX_ZOOM


def _non_negative_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid int value: {text!r}") from None
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or greater")
    return value


def _positive_int(text: str) -> int:
    value = _non_negative_int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or greater")
    return value


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="geojson-tiler",
        description="Chunk a GeoJSON file into XYZ tile GeoJSON files.",
    )
    parser.add_argument("input", help="Path to a GeoJSON Feature or FeatureCollection file.")
    parser.add_argument("output", help="Directory where XYZ tile files will be written.")
    parser.add_argument(
        "--min-zoom",
        type=int,
        default=0,
        help=f"Lowest zoom level to generate (default: 0, maximum: {MAX_ZOOM}).",
    )
    parser.add_argument(
        "--max-zoom",
        type=int,
        default=0,
        help=(
            f"Highest zoom level to generate (default: 0, maximum: {MAX_ZOOM}). "
            "The default produces only tile 0/0/0."
        ),
    )
    parser.add_argument(
        "--max-tiles",
        type=_positive_int,
        default=DEFAULT_MAX_TILES,
        help="Stop with an error if more than this many tiles would be created "
        "(default: %(default)s).",
    )
    parser.add_argument(
        "--indent",
        type=_non_negative_int,
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
        validate_zoom_range(args.min_zoom, args.max_zoom)
        data = load_geojson(args.input)
        result = tile_geojson(
            data,
            min_zoom=args.min_zoom,
            max_zoom=args.max_zoom,
            max_tiles=args.max_tiles,
        )
        metadata = write_tiles(
            result,
            args.output,
            indent=args.indent,
            overwrite=args.overwrite,
            source_name=Path(args.input).name,
        )
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    except RecursionError:
        parser.exit(2, "Error: the GeoJSON is nested too deeply.\n")

    if not args.quiet:
        print(
            f"Wrote {metadata['tile_count']} tile file(s) from {metadata['feature_count']} "
            f"feature(s) to {args.output}"
        )
        print(f"Metadata: {Path(args.output) / 'metadata.json'}")

    return 0

