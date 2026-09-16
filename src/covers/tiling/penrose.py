"""Penrose P3 (rhombus) tiling via Robinson-triangle deflation.

Each rhombus is represented as two Robinson triangles sharing an edge;
rendering both triangles of a pair in the same colour (no stroke) reads as
a single seamless rhombus. Subdivision rules and initial wheel setup
follow the standard construction described in
https://preshing.com/20110831/penrose-tiling-explained/ .
"""

import cmath
import math

from covers.tiling.base import Polygon, Tiling

GOLDEN_RATIO = (1 + math.sqrt(5)) / 2

# Internal triangle representation: (color, A, B, C) as complex numbers,
# A the apex. color 0 = "thin" prototile half, color 1 = "thick" half.
_Triangle = tuple[int, complex, complex, complex]

_TILE_TYPE_BY_COLOR = {0: "thin", 1: "thick"}


def _initial_wheel() -> list[_Triangle]:
    triangles = []
    for i in range(10):
        b = cmath.rect(1.0, (2 * i - 1) * math.pi / 10)
        c = cmath.rect(1.0, (2 * i + 1) * math.pi / 10)
        if i % 2 == 0:
            b, c = c, b
        triangles.append((0, 0j, b, c))
    return triangles


def _subdivide(triangles: list[_Triangle]) -> list[_Triangle]:
    result: list[_Triangle] = []
    for color, a, b, c in triangles:
        if color == 0:
            p = a + (b - a) / GOLDEN_RATIO
            result.append((0, c, p, b))
            result.append((1, p, c, a))
        else:
            q = b + (a - b) / GOLDEN_RATIO
            r = b + (c - b) / GOLDEN_RATIO
            result.append((1, r, c, a))
            result.append((1, q, r, b))
            result.append((0, r, q, a))
    return result


def _triangles_at_depth(depth: int) -> list[_Triangle]:
    if depth < 0:
        raise ValueError(f"depth must be >= 0, got {depth}")

    triangles = _initial_wheel()
    for _ in range(depth):
        triangles = _subdivide(triangles)
    return triangles


def _edge_key(p1: complex, p2: complex, tol: int = 9) -> frozenset:
    a = (round(p1.real, tol), round(p1.imag, tol))
    b = (round(p2.real, tol), round(p2.imag, tol))
    return frozenset((a, b))


def _merge_rhombi(triangles: list[_Triangle]) -> list[Polygon]:
    """Merges same-coloured Robinson-triangle pairs (sharing their base
    edge B-C) into their true rhombus tile: apex1, B, apex2, C, going
    around the perimeter. Triangles on the patch's outer boundary have no
    partner and stay as a 3-point polygon. See tiling/base.py's
    outline_polygons docstring for why this exists.
    """
    groups: dict[frozenset, list[_Triangle]] = {}
    for triangle in triangles:
        _color, _a, b, c = triangle
        groups.setdefault(_edge_key(b, c), []).append(triangle)

    polygons = []
    for group in groups.values():
        if len(group) == 2:
            (color, apex1, b, c), (color2, apex2, _b2, _c2) = group
            if color2 != color:
                raise AssertionError(
                    "Penrose rhombus merge paired triangles of different "
                    "colours -- this should never happen; the substitution "
                    "or edge-matching tolerance may have changed."
                )
            points = (apex1, b, apex2, c)
        else:
            color, apex, b, c = group[0]
            points = (apex, b, c)
        polygons.append(
            Polygon(
                points=tuple((v.real, v.imag) for v in points),
                tile_type=_TILE_TYPE_BY_COLOR[color],
            )
        )
    return polygons


class PenroseP3Tiling(Tiling):
    tile_types = ("thin", "thick")

    def generate(self, depth: int) -> list[Polygon]:
        triangles = _triangles_at_depth(depth)
        return [
            Polygon(
                points=tuple((v.real, v.imag) for v in (a, b, c)),
                tile_type=_TILE_TYPE_BY_COLOR[color],
            )
            for color, a, b, c in triangles
        ]

    def outline_polygons(self, depth: int) -> list[Polygon]:
        return _merge_rhombi(_triangles_at_depth(depth))

    def tile_count(self, depth: int) -> int:
        if depth < 0:
            raise ValueError(f"depth must be >= 0, got {depth}")

        # (thin, thick) triangle counts evolve as a linear recurrence,
        # read directly off _subdivide's branches: a thin triangle
        # produces 1 thin + 1 thick; a thick triangle produces 1 thin +
        # 2 thick. Starting point is the 10-triangle initial wheel (all
        # thin). Verified against actual generate() output up to depth 5.
        n0, n1 = 10, 0
        for _ in range(depth):
            n0, n1 = n0 + n1, n0 + 2 * n1
        return n0 + n1

    def min_useful_depth(self) -> int:
        # Depth 0 is a monochrome wheel -- no "thick" tiles exist yet, so
        # it renders as a near-solid fill rather than a visible pattern.
        return 1
