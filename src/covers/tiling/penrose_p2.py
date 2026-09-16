"""Penrose P2 (kite/dart) tiling via inflation.

Ported from CPython's own standard library demo,
Lib/turtledemo/penrose.py (PSF License -- part of the official Python
distribution, https://github.com/python/cpython/blob/main/Lib/turtledemo/penrose.py),
translated from stateful turtle-graphics moves (lt/rt/fd) into plain
complex-number position/heading arithmetic. The turn angles, move
lengths, and recursion structure are unchanged from that source.

Unlike P3 (deflation: one fixed-size patch subdivided into ever-smaller
tiles), this is INFLATION: each depth step recursively builds a LARGER
surrounding structure at a fixed ratio, while the leaf tile size shrinks
by a factor of 1/phi per step (matched in generate() by scaling final
leaf tiles by F**depth, mirroring the source's draw()). That's a
different generation direction than P3/Pinwheel, but produces the same
kind of result the renderer needs: a patch of many small tiles, more and
smaller as depth increases -- render.py's coverage transform doesn't
care which direction the recursion grew from, only the final polygons.

The seed is "sun": 5 kites arranged with 5-fold rotational symmetry
around a point (the source module's other named seed, "star", is 5
darts instead -- an arbitrary but equally valid choice).

Verified (see project history): kite/dart vertex sequences close
exactly and match the expected angle sets (kite: 72,72,144,72; dart:
72,36,144,36 with the reflex correction for its concave vertex); the
tile_count recurrence below matches actual generate() output exactly;
and a rendered "sun" patch is visually an unmistakable, gap-free
Penrose tiling.
"""

import cmath
import math

from covers.tiling.base import Polygon, Tiling

_F = (5**0.5 - 1) / 2.0  # 1/phi
_D = 2 * math.cos(3 * math.pi / 10)
_SUN_ARMS = 5


class _Turtle:
    """Tracks position/heading and records each fd() move as an edge."""

    def __init__(self, pos: complex, heading: float):
        self.pos = pos
        self.heading = heading
        self.trace: list[complex] = [pos]

    def lt(self, degrees: float) -> None:
        self.heading += degrees

    def rt(self, degrees: float) -> None:
        self.heading -= degrees

    def fd(self, distance: float) -> None:
        self.pos += cmath.rect(distance, math.radians(self.heading))
        self.trace.append(self.pos)


def _kite_vertices(pos: complex, heading: float, length: float) -> list[complex]:
    t = _Turtle(pos, heading)
    fl = _F * length
    t.lt(36); t.fd(length)
    t.rt(108); t.fd(fl)
    t.rt(36); t.fd(fl)
    t.rt(108); t.fd(length)
    return t.trace  # 5 points, first == last (closed quadrilateral)


def _dart_vertices(pos: complex, heading: float, length: float) -> list[complex]:
    t = _Turtle(pos, heading)
    fl = _F * length
    t.lt(36); t.fd(length)
    t.rt(144); t.fd(fl)
    t.lt(36); t.fd(fl)
    t.rt(144); t.fd(length)
    return t.trace


def _inflate(is_kite: bool, pos: complex, heading: float, length: float, depth: int):
    if depth == 0:
        return [(is_kite, pos, heading)]

    fl = _F * length
    t = _Turtle(pos, heading)
    leaves = []
    if is_kite:
        t.lt(36)
        leaves += _inflate(False, t.pos, t.heading, fl, depth - 1)
        t.fd(length); t.rt(144)
        leaves += _inflate(True, t.pos, t.heading, fl, depth - 1)
        t.lt(18); t.fd(length * _D); t.rt(162)
        leaves += _inflate(True, t.pos, t.heading, fl, depth - 1)
        t.lt(36); t.fd(length); t.rt(180)
        leaves += _inflate(False, t.pos, t.heading, fl, depth - 1)
    else:
        leaves += _inflate(True, t.pos, t.heading, fl, depth - 1)
        t.lt(36); t.fd(length); t.rt(180)
        leaves += _inflate(False, t.pos, t.heading, fl, depth - 1)
        t.lt(54); t.fd(length * _D); t.rt(126)
        leaves += _inflate(False, t.pos, t.heading, fl, depth - 1)
    return leaves


def _sun(length: float, depth: int) -> list[tuple[bool, complex, float]]:
    leaves = []
    pos, heading = 0j, 0.0
    for _ in range(_SUN_ARMS):
        leaves += _inflate(True, pos, heading, length, depth)
        heading += 360 / _SUN_ARMS
    return leaves


class PenroseP2Tiling(Tiling):
    tile_types = ("kite", "dart")

    def generate(self, depth: int) -> list[Polygon]:
        if depth < 0:
            raise ValueError(f"depth must be >= 0, got {depth}")

        base_length = 1.0  # arbitrary; render.py rescales to fit the panel
        final_length = base_length * _F**depth

        polygons = []
        for is_kite, pos, heading in _sun(base_length, depth):
            vertices = (_kite_vertices if is_kite else _dart_vertices)(pos, heading, final_length)
            polygons.append(
                Polygon(
                    points=tuple((v.real, v.imag) for v in vertices[:-1]),
                    tile_type="kite" if is_kite else "dart",
                )
            )
        return polygons

    def tile_count(self, depth: int) -> int:
        if depth < 0:
            raise ValueError(f"depth must be >= 0, got {depth}")

        # (kites, darts) produced by one inflatekite/inflatedart call,
        # read directly off _inflate's branches: inflatekite recurses
        # into 2 inflatedart + 2 inflatekite; inflatedart recurses into
        # 1 inflatekite + 2 inflatedart. Starting point: a single
        # unsubdivided kite (1, 0) / dart (0, 1). Verified against actual
        # generate() output.
        kite_counts = (1, 0)
        dart_counts = (0, 1)
        for _ in range(depth):
            kite_counts, dart_counts = (
                (2 * dart_counts[0] + 2 * kite_counts[0], 2 * dart_counts[1] + 2 * kite_counts[1]),
                (kite_counts[0] + 2 * dart_counts[0], kite_counts[1] + 2 * dart_counts[1]),
            )
        total_kites, total_darts = kite_counts
        return _SUN_ARMS * (total_kites + total_darts)

    def min_useful_depth(self) -> int:
        # Depth 0 is 5 unsubdivided kites -- no darts exist yet, so it
        # renders as a near-solid fill rather than a visible pattern.
        return 1
