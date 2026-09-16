import math

import pytest

from covers.tiling.base import Polygon, depth_for_target_count
from covers.tiling.registry import get_tiling
from shatter.geometry import (
    bounding_box,
    centroid,
    inset_about_centroid,
    resolve_depth,
    whole_tiles,
)

SQUARE = Polygon(points=((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)), tile_type="x")


def test_centroid_of_known_tile():
    assert centroid(SQUARE) == (1.0, 1.0)


def test_bounding_box_spans_all_polygons():
    other = Polygon(points=((-1.0, 3.0), (0.0, 3.0), (0.0, 4.0)), tile_type="x")
    assert bounding_box([SQUARE, other]) == (-1.0, 0.0, 2.0, 4.0)


def test_p3_partial_tiles_dropped():
    assert len(whole_tiles("p3", 3, drop_partial_tiles=True)) == 60
    assert len(whole_tiles("p3", 3, drop_partial_tiles=False)) == 70


def test_p3_filtering_leaves_only_rhombi():
    kept = whole_tiles("p3", 3, drop_partial_tiles=True)
    assert {len(tile.points) for tile in kept} == {4}


@pytest.mark.parametrize("family", ["p2", "pinwheel"])
def test_filter_does_not_touch_other_families(family):
    """Pinwheel tiles are 3-vertex by nature -- a blanket filter would erase it."""
    assert whole_tiles(family, 2, drop_partial_tiles=True) == whole_tiles(
        family, 2, drop_partial_tiles=False
    )


def test_resolve_depth_counts_whole_tiles_not_triangles():
    target = 100
    # The engine's own resolver stops at depth 3, where generate() emits 130
    # triangles but only 60 rhombi survive the merge.
    assert depth_for_target_count(get_tiling("p3"), target) == 3
    assert len(whole_tiles("p3", 3)) < target

    depth = resolve_depth("p3", target)
    assert depth == 4
    assert len(whole_tiles("p3", depth)) >= target


def test_resolve_depth_agrees_with_engine_when_no_merging_happens():
    assert resolve_depth("pinwheel", 300) == depth_for_target_count(
        get_tiling("pinwheel"), 300
    )


def test_inset_shrinks_tile_without_moving_it():
    inset = inset_about_centroid(SQUARE, 0.1)
    assert centroid(inset) == pytest.approx(centroid(SQUARE))
    x0, y0, x1, y1 = bounding_box([inset])
    assert (x1 - x0) == pytest.approx(1.8)
    assert (y1 - y0) == pytest.approx(1.8)


def test_inset_of_zero_is_identity():
    assert inset_about_centroid(SQUARE, 0.0) is SQUARE


def test_inset_preserves_tile_type_and_vertex_count():
    inset = inset_about_centroid(SQUARE, 0.25)
    assert inset.tile_type == SQUARE.tile_type
    assert len(inset.points) == len(SQUARE.points)


def test_patches_are_centred_on_origin():
    """Section 6 relies on |centroid| being distance-from-centre."""
    for family in ("p2", "p3", "pinwheel"):
        x0, y0, x1, y1 = bounding_box(whole_tiles(family, 3))
        assert math.hypot((x0 + x1) / 2, (y0 + y1) / 2) < 0.05
