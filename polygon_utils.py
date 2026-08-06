from __future__ import annotations

from typing import Any


def normalize_polygon(points: Any) -> list[list[int]]:
    if not isinstance(points, list) or len(points) < 3:
        return []

    normalized: list[list[int]] = []
    try:
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                return []
            normalized.append([int(point[0]), int(point[1])])
    except (TypeError, ValueError):
        return []

    vertices = {(point[0], point[1]) for point in normalized}
    if len(vertices) < 3:
        return []
    area_twice = sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(normalized, normalized[1:] + normalized[:1])
    )
    return normalized if area_twice != 0 else []


def polygon_ready(points: Any) -> bool:
    return bool(normalize_polygon(points))
