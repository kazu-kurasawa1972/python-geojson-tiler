from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .tiler import TileBuildResult
from .xyz import TileAddress


def tile_path(output_dir: str | Path, tile: TileAddress) -> Path:
    """Return the file path for a tile inside the output directory."""
    return Path(output_dir) / str(tile.z) / str(tile.x) / f"{tile.y}.geojson"


def write_tiles(
    result: TileBuildResult,
    output_dir: str | Path,
    *,
    indent: int | None = 2,
    overwrite: bool = False,
    source_name: str = "input.geojson",
) -> dict[str, Any]:
    """Write tile files and a metadata summary into the output directory."""
    output_path = Path(output_dir)
    if output_path.exists() and any(output_path.iterdir()) and not overwrite:
        raise FileExistsError(
            f"Output directory {output_path} is not empty. "
            "Allow overwriting (--overwrite on the command line, overwrite=True in Python) to continue."
        )

    output_path.mkdir(parents=True, exist_ok=True)

    for tile, payload in result.tiles.items():
        destination = tile_path(output_path, tile)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(payload, indent=indent, sort_keys=True)
            + ("\n" if indent is not None else ""),
            encoding="utf-8",
        )

    metadata = {
        "source": source_name,
        "feature_count": result.feature_count,
        "tile_count": result.tile_count,
        "tiles": [
            {
                "z": tile.z,
                "x": tile.x,
                "y": tile.y,
                "path": f"{tile.z}/{tile.x}/{tile.y}.geojson",
            }
            for tile in sorted(result.tiles.keys())
        ],
    }
    (output_path / "metadata.json").write_text(
        json.dumps(metadata, indent=indent, sort_keys=True)
        + ("\n" if indent is not None else ""),
        encoding="utf-8",
    )
    return metadata


