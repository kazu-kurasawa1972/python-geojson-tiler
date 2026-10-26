from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from .clip import clip_geometry
from .filters import filter_feature
from .geojson import crosses_antimeridian, feature_bounds, normalize_geojson
from .xyz import TileAddress, count_tiles_for_bounds, tiles_for_bounds, validate_zoom


DEFAULT_MAX_TILES = 100_000


class TileLimitError(ValueError):
    """Raised when a run would create more tiles than allowed."""


@dataclass(frozen=True)
class TileBuildResult:
    """Container for the generated tile documents and summary counts."""

    tiles: dict[TileAddress, dict[str, Any]]
    feature_count: int
    tile_count: int


def validate_zoom_range(min_zoom: int, max_zoom: int) -> None:
    """Validate a user-supplied zoom range."""
    validate_zoom(min_zoom)
    validate_zoom(max_zoom)
    if min_zoom > max_zoom:
        raise ValueError("The minimum zoom (--min-zoom) must be less than or equal to the maximum zoom (--max-zoom).")


def tile_geojson(
    data: dict[str, Any],
    *,
    min_zoom: int = 0,
    max_zoom: int = 0,
    max_tiles: int = DEFAULT_MAX_TILES,
    keep_properties: Iterable[str] | None = None,
    drop_properties: Iterable[str] | None = None,
    clip: bool = False,
) -> TileBuildResult:
    """Split a GeoJSON object into tile-sized FeatureCollections.

    Raises TileLimitError as soon as more than ``max_tiles`` tiles would be needed.
    ``keep_properties`` / ``drop_properties`` (not both) filter feature properties.
    With ``clip=True`` each feature's geometry is cut to the tile bounds and tiles left with no
    features are not created; ``max_tiles`` still counts candidate tiles before clipping.
    Features that cross the antimeridian are never clipped.
    """
    validate_zoom_range(min_zoom, max_zoom)
    if isinstance(max_tiles, bool) or not isinstance(max_tiles, int) or max_tiles < 1:
        raise ValueError("max_tiles must be a positive integer.")
    if keep_properties is not None and drop_properties is not None:
        raise ValueError("Use either keep_properties or drop_properties, not both.")
    filtering = keep_properties is not None or drop_properties is not None
    collection = normalize_geojson(data)

    buckets: dict[TileAddress, list[dict[str, Any]]] = defaultdict(list)
    feature_count = 0

    for feature in collection["features"]:
        feature_count += 1
        bounds = feature_bounds(feature)
        if bounds is None:
            continue
        # Antimeridian features are kept whole: lon/lat clipping would cut them wrongly.
        clipping = clip and not crosses_antimeridian(feature["geometry"])
        if filtering:
            feature = filter_feature(feature, keep=keep_properties, drop=drop_properties)

        for zoom in range(min_zoom, max_zoom + 1):
            # Check the size arithmetically so a huge feature never builds a huge list.
            if count_tiles_for_bounds(bounds, zoom) > max_tiles:
                raise _too_many_tiles(max_tiles)
            for tile in tiles_for_bounds(bounds, zoom):
                piece = _clip_feature(feature, tile) if clipping else feature
                if piece is not None:
                    buckets[tile].append(piece)
            if len(buckets) > max_tiles:
                raise _too_many_tiles(max_tiles)

    tile_documents = {
        tile: {"type": "FeatureCollection", "features": features}
        for tile, features in sorted(buckets.items())
    }
    return TileBuildResult(
        tiles=tile_documents,
        feature_count=feature_count,
        tile_count=len(tile_documents),
    )


def _clip_feature(feature: dict[str, Any], tile: TileAddress) -> dict[str, Any] | None:
    """Return a copy of ``feature`` clipped to ``tile``, or None if nothing is left."""
    clipped = clip_geometry(feature["geometry"], tile)
    if clipped is None:
        return None
    result = dict(feature)
    result["geometry"] = clipped
    return result


def _too_many_tiles(max_tiles: int) -> TileLimitError:
    return TileLimitError(
        f"This would create more than {max_tiles} tiles. "
        "Lower the maximum zoom (--max-zoom) or raise the tile limit (--max-tiles)."
    )
