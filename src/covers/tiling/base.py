"""Interface for aperiodic tiling generators."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Polygon:
    """A single filled tile: vertices in drawing order, tagged by prototile type."""

    points: tuple[tuple[float, float], ...]
    tile_type: str


class Tiling(ABC):
    """An aperiodic tiling generator.

    Implementations produce a patch of tiles in their own natural local
    coordinate space -- unrotated, unscaled, not positioned for any
    particular panel. The renderer (layout/render.py) is responsible for
    a shared rotate/scale/offset transform that covers whatever panel
    it's drawing, based on the patch's actual bounding box -- individual
    Tiling implementations don't need to know or care about panel size.
    """

    #: prototile type tags this tiling produces, in a fixed order --
    #: callers (e.g. palette assignment) line colours up against this.
    tile_types: tuple[str, ...]

    @abstractmethod
    def generate(self, depth: int) -> list[Polygon]:
        """Generate polygons. Higher depth -> smaller, more numerous tiles."""
        raise NotImplementedError

    @abstractmethod
    def tile_count(self, depth: int) -> int:
        """Exact number of tiles generate(depth) will produce.

        Used to resolve a user-facing "zoom" (target visible tile count)
        to the smallest sufficient depth, without having to generate at
        every candidate depth just to count.
        """
        raise NotImplementedError

    def min_useful_depth(self) -> int:
        """Smallest depth worth ever rendering.

        Default 0. Override when a low depth is technically valid but
        degenerate for rendering -- e.g. Penrose P3's depth 0 is a
        monochrome wheel (no "thick" tiles exist yet), which reads as a
        near-solid fill rather than a visible tiling pattern.
        """
        return 0

    def outline_polygons(self, depth: int) -> list[Polygon]:
        """Polygons to use when drawing tile BORDERS specifically.

        Default: same as generate(). Override when generate()'s fill
        polygons are sub-tile pieces drawn without a stroke for a
        seamless look (e.g. Penrose P3 fills each rhombus as two
        same-coloured Robinson-triangle halves) -- stroking those
        directly would draw a stray line through the middle of every
        tile, so such families return the merged true-tile shape here
        instead.
        """
        return self.generate(depth)


#: Hard cap on how deep zoom resolution will search. Tile counts grow
#: geometrically (roughly x2.6/depth for Penrose, x5/depth for Pinwheel),
#: so this comfortably covers the documented ~1000-tile top end with
#: headroom, while bounding worst-case generation cost for a bad target.
MAX_ZOOM_DEPTH = 12


def depth_for_target_count(tiling: Tiling, target: int) -> int:
    """Smallest depth (at or above the tiling's min_useful_depth) whose
    tile_count(depth) >= target.

    If even MAX_ZOOM_DEPTH isn't enough (an absurdly large target),
    returns MAX_ZOOM_DEPTH rather than searching unboundedly.
    """
    if target < 1:
        raise ValueError(f"target must be >= 1, got {target}")

    floor = tiling.min_useful_depth()
    for depth in range(floor, MAX_ZOOM_DEPTH + 1):
        if tiling.tile_count(depth) >= target:
            return depth
    return MAX_ZOOM_DEPTH
