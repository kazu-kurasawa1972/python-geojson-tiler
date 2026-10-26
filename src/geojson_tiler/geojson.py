from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

VALID_GEOMETRY_TYPES = {
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
    "GeometryCollection",
}


class GeoJSONError(ValueError):
    """Raised when the input is not valid for this tiler."""


Position = tuple[float, float]
Bounds = tuple[float, float, float, float]


def load_geojson(path: str | Path) -> dict[str, Any]:
    """Load a GeoJSON file and normalize it to a FeatureCollection."""
    input_path = Path(path)
    try:
        data = json.loads(input_path.read_text(encoding="utf-8"), parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise GeoJSONError(f"Invalid JSON in {input_path}: {exc.msg}.") from exc
    except RecursionError as exc:
        raise GeoJSONError(f"{input_path} is nested too deeply to read.") from exc
    return normalize_geojson(data)


def _reject_constant(name: str) -> Any:
    raise GeoJSONError(
        f"Input contains {name}, which is not valid JSON. Replace it with a number or null."
    )


def normalize_geojson(data: Any) -> dict[str, Any]:
    """Normalize a GeoJSON Feature or FeatureCollection into a FeatureCollection."""
    try:
        return _normalize_geojson(data)
    except RecursionError as exc:
        raise GeoJSONError("GeoJSON is nested too deeply.") from exc


def _normalize_geojson(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise GeoJSONError("GeoJSON root must be an object.")

    geojson_type = data.get("type")
    if geojson_type == "FeatureCollection":
        features = data.get("features")
        if not isinstance(features, list):
            raise GeoJSONError("FeatureCollection.features must be a list.")
        return {
            "type": "FeatureCollection",
            "features": [normalize_feature(feature) for feature in features],
        }

    if geojson_type == "Feature":
        return {"type": "FeatureCollection", "features": [normalize_feature(data)]}

    raise GeoJSONError("GeoJSON root must be a Feature or FeatureCollection.")


def normalize_feature(feature: Any) -> dict[str, Any]:
    """Validate a feature while preserving extra keys such as id or bbox."""
    if not isinstance(feature, dict) or feature.get("type") != "Feature":
        raise GeoJSONError("Each item in features must be a GeoJSON Feature.")

    properties = feature.get("properties")
    if properties is None:
        properties = {}
    elif not isinstance(properties, dict):
        raise GeoJSONError("Feature.properties must be an object or null.")

    geometry = feature.get("geometry")
    if geometry is not None:
        validate_geometry(geometry)

    normalized = dict(feature)
    normalized["properties"] = properties
    normalized["geometry"] = geometry
    return normalized


def validate_geometry(geometry: Any) -> None:
    """Perform light validation for supported GeoJSON geometry types."""
    if not isinstance(geometry, dict):
        raise GeoJSONError("Feature.geometry must be an object or null.")

    geometry_type = geometry.get("type")
    if geometry_type == "GeometryCollection":
        geometries = geometry.get("geometries")
        if not isinstance(geometries, list):
            raise GeoJSONError("GeometryCollection.geometries must be a list.")
        for item in geometries:
            validate_geometry(item)
        return

    if geometry_type not in VALID_GEOMETRY_TYPES:
        raise GeoJSONError(f"Unsupported geometry type: {geometry_type!r}.")

    if "coordinates" not in geometry:
        raise GeoJSONError(f"Geometry {geometry_type} must include coordinates.")

    list(iter_geometry_positions(geometry))


def iter_geometry_positions(geometry: Any | None) -> Iterator[Position]:
    """Yield lon/lat positions from a supported geometry object."""
    if geometry is None:
        return

    geometry_type = geometry.get("type")
    if geometry_type == "GeometryCollection":
        for item in geometry.get("geometries", []):
            yield from iter_geometry_positions(item)
        return

    yield from _iter_positions(geometry["coordinates"])


def _iter_positions(coordinates: Any) -> Iterator[Position]:
    if isinstance(coordinates, (list, tuple)):
        if len(coordinates) >= 2 and all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in coordinates[:2]
        ):
            yield float(coordinates[0]), float(coordinates[1])
            return

        for value in coordinates:
            yield from _iter_positions(value)
        return

    raise GeoJSONError("Geometry coordinates must contain numeric positions.")


def geometry_bounds(geometry: dict[str, Any] | None) -> Bounds | None:
    """Return (min_lon, min_lat, max_lon, max_lat) for a geometry."""
    positions = list(iter_geometry_positions(geometry))
    if not positions:
        return None

    longitudes = [position[0] for position in positions]
    latitudes = [position[1] for position in positions]
    return min(longitudes), min(latitudes), max(longitudes), max(latitudes)


def feature_bounds(feature: dict[str, Any]) -> Bounds | None:
    """Return bounds for a GeoJSON feature."""
    return geometry_bounds(feature.get("geometry"))


