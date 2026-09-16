"""Tile geometry on top of the vendored tiling engine.

All coordinates here are in the engine's local "patch units": origin-centred,
unrotated, unscaled. Conversion to pixels is render.py's job.
"""

import math

from covers.tiling.base import MAX_ZOOM_DEPTH, Polygon, depth_for_target_count
from covers.tiling.registry import get_tiling

Point = tuple[float, float]
BoundingBox = tuple[float, float, float, float]


def centroid(polygon: Polygon) -> Point:
    points = polygon.points
    return (
        sum(x for x, _ in points) / len(points),
        sum(y for _, y in points) / len(points),
    )


def bounding_box(polygons: list[Polygon]) -> BoundingBox:
    xs = [x for p in polygons for x, _ in p.points]
    ys = [y for p in polygons for _, y in p.points]
    return min(xs), min(ys), max(xs), max(ys)


def whole_tiles(
    family: str, depth: int, drop_partial_tiles: bool = True
) -> list[Polygon]:
    """Whole tiles for a patch, in the stable order edits index into."""
    tiles = get_tiling(family).outline_polygons(depth)
    if drop_partial_tiles and family == "p3":
        # P3's rhombus merge leaves unpaired boundary triangles. The filter is
        # P3-only because Pinwheel's tiles are legitimately 3-vertex, and
        # applying it there would drop the entire patch.
        tiles = [t for t in tiles if len(t.points) >= 4]
    return tiles


def prototile_types(family: str) -> tuple[str, ...]:
    """The family's prototile tags, in the fixed order colours line up against.

    Every family has exactly two (p3 thin/thick, p2 kite/dart, pinwheel cw/ccw),
    and every tile a patch contains carries one of them -- including P3's unpaired
    boundary triangles, which are tagged "thick". That is what lets the renderer
    colour by tile shape without a per-family special case.
    """
    return get_tiling(family).tile_types


def resolve_depth(family: str, target: int, drop_partial_tiles: bool = True) -> int:
    """Smallest depth whose WHOLE-tile count reaches target.

    The engine's depth_for_target_count counts what generate() emits, which for
    P3 is Robinson triangles -- roughly twice the rhombi actually drawn. It is
    used here only as a lower bound, since merging and dropping never increase
    the count.
    """
    lower_bound = depth_for_target_count(get_tiling(family), target)
    for depth in range(lower_bound, MAX_ZOOM_DEPTH + 1):
        if len(whole_tiles(family, depth, drop_partial_tiles)) >= target:
            return depth
    return MAX_ZOOM_DEPTH


def inset_about_centroid(polygon: Polygon, gap: float) -> Polygon:
    """Shrink a tile toward its own centroid, leaving a gap to its neighbours.

    Uniform scaling rather than true edge offset, so the gap is narrower at a
    rhombus's sharp corners. Leaves the centroid fixed, so it composes with
    rotation and translation in any order.
    """
    if gap <= 0:
        return polygon
    cx, cy = centroid(polygon)
    scale = 1.0 - gap
    return Polygon(
        points=tuple(
            (cx + (x - cx) * scale, cy + (y - cy) * scale) for x, y in polygon.points
        ),
        tile_type=polygon.tile_type,
    )


def rotate_about_centroid(polygon: Polygon, angle: float) -> Polygon:
    """Rotate a tile in place. Angle in radians."""
    if angle == 0.0:
        return polygon
    cx, cy = centroid(polygon)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    return Polygon(
        points=tuple(
            (
                cx + (x - cx) * cos_a - (y - cy) * sin_a,
                cy + (x - cx) * sin_a + (y - cy) * cos_a,
            )
            for x, y in polygon.points
        ),
        tile_type=polygon.tile_type,
    )


def translate(polygon: Polygon, dx: float, dy: float) -> Polygon:
    if dx == 0.0 and dy == 0.0:
        return polygon
    return Polygon(
        points=tuple((x + dx, y + dy) for x, y in polygon.points),
        tile_type=polygon.tile_type,
    )
