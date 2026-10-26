"""Property filtering, used to shrink tile output."""

from __future__ import annotations

from typing import Any, Iterable


def parse_property_names(text: str) -> list[str]:
    """Turn ``"name, pop"`` into ``["name", "pop"]``. Empty names are rejected."""
    names = [part.strip() for part in text.split(",")]
    if any(not name for name in names):
        raise ValueError("property names must not be empty (check for stray commas).")
    return names


def filter_properties(
    properties: dict[str, Any] | None,
    *,
    keep: Iterable[str] | None = None,
    drop: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return a new properties dict with only the wanted entries.

    ``keep`` keeps just those names; ``drop`` removes those names. Names that
    are not present are ignored. ``None`` properties count as ``{}``. The input
    is never modified.
    """
    if keep is not None and drop is not None:
        raise ValueError("Use either keep or drop, not both.")
    properties = properties or {}
    if keep is not None:
        wanted = set(keep)
        return {key: value for key, value in properties.items() if key in wanted}
    if drop is not None:
        unwanted = set(drop)
        return {key: value for key, value in properties.items() if key not in unwanted}
    return dict(properties)


def filter_feature(
    feature: dict[str, Any],
    *,
    keep: Iterable[str] | None = None,
    drop: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return a shallow copy of ``feature`` with filtered properties."""
    filtered = dict(feature)
    filtered["properties"] = filter_properties(feature.get("properties"), keep=keep, drop=drop)
    return filtered
