"""Pinwheel tiling (Radin-Conway 1:2 right-triangle substitution).

The subdivision math here is ported from Brian Yee's Py-Rep-Tile
(https://github.com/Brian-Yee/Py-Rep-Tile, MIT licensed), specifically
src/pinwheel.py and src/reptile.py's handedness (`sign`) calculation --
translated from a class-based, numpy/cmath implementation into the
functional, tuple-based style used elsewhere in this package. The
geometry (which point goes where) is unchanged from that source; see
LICENSE below.

    MIT License, Copyright (c) 2019 Brian [Yee]. Permission is hereby
    granted, free of charge, to any person obtaining a copy of this
    software and associated documentation files (the "Software"), to
    deal in the Software without restriction, including without
    limitation the rights to use, copy, modify, merge, publish,
    distribute, sublicense, and/or sell copies of the Software, subject
    to including the above copyright notice in all copies or substantial
    portions of the Software.

Each triangle is a right triangle with legs 1 and 2 (hypotenuse sqrt(5)),
represented as (origin, index, thumb): origin is the right-angle vertex,
index is the long-leg (length 2) endpoint, thumb is the short-leg
(length 1) endpoint. It subdivides into 5 congruent copies scaled by
1/sqrt(5). One 1x2 rectangle is two such triangles sharing the diagonal
(matching the construction in the pinwheel mesh-generation paper, arXiv
cs/0407018) -- but a single 1x2 rectangle is too elongated to seed a
whole cover panel with: the shared renderer (layout/render.py) covers a
panel by scaling the tiling's rotated axis-aligned bounding box to fit,
and a *rotated* 2:1 rectangle's bounding box is much bigger than the
rectangle itself, leaving big background wedges uncovered in the corners
(confirmed by an actual render -- this isn't a hypothetical). Fixed by
seeding a COLS x ROWS grid of such rectangles (plain translation, no
rotation at seed time) forming a roughly square overall patch, each cell
subdivided independently. This is gap-free: per the mesh-generation
paper, pinwheel subdivision never places a new vertex on a triangle's
short-leg edge, and the long-leg edge only ever gets a vertex at its
exact midpoint (a "hanging node", collinear with the parent edge) --
so adjacent grid cells' shared straight edges always still line up
exactly, subdivided or not.

Tiles are coloured by chirality (the algorithm's own handedness sign) --
the two colours line up with the two ways a pinwheel triangle can be
oriented relative to its neighbours, giving a visually structured
two-colour split analogous to Penrose's thin/thick.
"""

import cmath
import math

from covers.tiling.base import Polygon, Tiling

PINWHEEL_ALPHA = math.atan2(1, 2)

# (origin, index, thumb) as complex numbers.
_Triangle = tuple[complex, complex, complex]

# Each cell is a 1x2 rectangle (2 wide, 1 tall). COLS x ROWS = 2 x 4 makes
# the overall seed patch 4x4 -- square, so it behaves well under the
# renderer's isotropic rotate-and-scale-to-cover transform.
_GRID_COLS = 2
_GRID_ROWS = 4
_CELLS_PER_SEED = _GRID_COLS * _GRID_ROWS
_TRIANGLES_PER_CELL = 2


def _seed_cell(col: int, row: int) -> tuple[_Triangle, _Triangle]:
    x0, y0 = 2 * col, row
    x1, y1 = x0 + 2, y0 + 1
    return (
        (complex(x0, y0), complex(x1, y0), complex(x0, y1)),
        (complex(x1, y1), complex(x0, y1), complex(x1, y0)),
    )


def _build_seed() -> tuple[_Triangle, ...]:
    total_w, total_h = 2 * _GRID_COLS, _GRID_ROWS
    # Centre the whole grid on the origin, matching the single-rectangle
    # seed's convention (and what the renderer's transform expects).
    offset = complex(-total_w / 2, -total_h / 2)
    triangles = []
    for col in range(_GRID_COLS):
        for row in range(_GRID_ROWS):
            for triangle in _seed_cell(col, row):
                triangles.append(tuple(v + offset for v in triangle))
    return tuple(triangles)


_SEED: tuple[_Triangle, ...] = _build_seed()


def _sign(origin: complex, index: complex, thumb: complex) -> float:
    thumb_vec = thumb - origin
    index_vec = index - origin
    cross = thumb_vec.real * index_vec.imag - thumb_vec.imag * index_vec.real
    return 1.0 if cross >= 0 else -1.0


def _subdivide_triangle(triangle: _Triangle) -> tuple[_Triangle, ...]:
    origin, index, thumb = triangle
    sign = _sign(origin, index, thumb)

    qp_rad, qp_phi = cmath.polar(thumb - origin)
    qa = cmath.rect(qp_rad, qp_phi + sign * math.pi / 2)
    qc = cmath.rect(2 / math.sqrt(5) * qp_rad, qp_phi + sign * PINWHEEL_ALPHA)
    qb = qc / 2

    a = origin + qa
    c = origin + qc
    b = origin + qb
    d = a + qb

    return (
        (c, origin, thumb),
        (b, a, origin),
        (b, a, c),
        (d, index, a),
        (d, c, a),
    )


def _subdivide(triangles: tuple[_Triangle, ...]) -> tuple[_Triangle, ...]:
    result: list[_Triangle] = []
    for triangle in triangles:
        result.extend(_subdivide_triangle(triangle))
    return tuple(result)


class PinwheelTiling(Tiling):
    tile_types = ("cw", "ccw")

    def generate(self, depth: int) -> list[Polygon]:
        if depth < 0:
            raise ValueError(f"depth must be >= 0, got {depth}")

        triangles = _SEED
        for _ in range(depth):
            triangles = _subdivide(triangles)

        polygons = []
        for origin, index, thumb in triangles:
            tile_type = "cw" if _sign(origin, index, thumb) > 0 else "ccw"
            polygons.append(
                Polygon(
                    points=tuple(
                        (v.real, v.imag) for v in (origin, index, thumb)
                    ),
                    tile_type=tile_type,
                )
            )
        return polygons

    def tile_count(self, depth: int) -> int:
        if depth < 0:
            raise ValueError(f"depth must be >= 0, got {depth}")
        return _CELLS_PER_SEED * _TRIANGLES_PER_CELL * 5**depth

    def min_useful_depth(self) -> int:
        # Every seed triangle shares the same handedness (all "ccw"), so
        # depth 0 is monochrome under our chirality-based colouring;
        # depth 1 is the first depth with both types present (verified
        # empirically against generate()).
        return 1
