import math

from shatter.autoshatter import ShatterParams, auto_shatter
from shatter.geometry import centroid, whole_tiles
from shatter.model import TileEdit

FAMILY, DEPTH = "p3", 4
IDENTITY = TileEdit()


def radii(family=FAMILY, depth=DEPTH):
    centroids = [centroid(tile) for tile in whole_tiles(family, depth)]
    magnitudes = [math.hypot(x, y) for x, y in centroids]
    largest = max(magnitudes)
    return [m / largest for m in magnitudes]


def test_one_edit_per_tile():
    layout = auto_shatter(FAMILY, DEPTH, 1, ShatterParams())
    assert len(layout.edits) == len(whole_tiles(FAMILY, DEPTH))


def test_layout_records_what_it_was_built_from():
    layout = auto_shatter(FAMILY, DEPTH, 7, ShatterParams(), drop_partial_tiles=False)
    assert (layout.family, layout.depth, layout.seed) == (FAMILY, DEPTH, 7)
    assert layout.drop_partial_tiles is False


def test_core_stays_intact_and_the_rim_does_not():
    params = ShatterParams(core_fraction=0.5)
    layout = auto_shatter(FAMILY, DEPTH, 1, params)
    inside = [
        edit
        for edit, r in zip(layout.edits, radii())
        if r <= params.core_fraction
    ]
    outside = [
        edit for edit, r in zip(layout.edits, radii()) if r > params.core_fraction
    ]

    assert inside and outside
    assert all(edit == IDENTITY for edit in inside)
    assert all(edit != IDENTITY for edit in outside)


def test_same_seed_reproduces_the_layout():
    a = auto_shatter(FAMILY, DEPTH, 42, ShatterParams())
    b = auto_shatter(FAMILY, DEPTH, 42, ShatterParams())
    assert a == b


def test_different_seed_changes_the_layout():
    a = auto_shatter(FAMILY, DEPTH, 42, ShatterParams())
    b = auto_shatter(FAMILY, DEPTH, 43, ShatterParams())
    assert a != b


def test_zeroed_knobs_leave_every_tile_alone():
    params = ShatterParams(
        core_fraction=0.0,
        max_push=0.0,
        jitter=0.0,
        max_rotation=0.0,
        dropout=0.0,
    )
    layout = auto_shatter(FAMILY, DEPTH, 1, params)
    assert all(edit == IDENTITY for edit in layout.edits)


def test_dropout_of_zero_hides_nothing():
    layout = auto_shatter(FAMILY, DEPTH, 1, ShatterParams(dropout=0.0))
    assert not any(edit.hidden for edit in layout.edits)


def test_displacement_grows_with_radius():
    layout = auto_shatter(FAMILY, DEPTH, 1, ShatterParams(jitter=0.0))
    moved = [
        (r, math.hypot(edit.dx, edit.dy))
        for edit, r in zip(layout.edits, radii())
        if not edit.hidden
    ]
    rim = max(moved, key=lambda pair: pair[0])
    mid = min((pair for pair in moved if pair[0] > 0.6), key=lambda pair: pair[0])
    assert rim[1] > mid[1]


def test_tiles_are_pushed_outward():
    layout = auto_shatter(FAMILY, DEPTH, 1, ShatterParams(jitter=0.0))
    tiles = whole_tiles(FAMILY, DEPTH)
    for tile, edit in zip(tiles, layout.edits):
        if edit == IDENTITY:
            continue
        cx, cy = centroid(tile)
        # displacement points the same way as the centroid
        assert cx * edit.dx + cy * edit.dy > 0


def test_core_fraction_reclassifies_without_rerolling():
    """Random draws are per-tile, so nudging core_fraction must not re-roll the
    patch -- otherwise every knob tweak scrambles a layout you were tuning."""
    loose = auto_shatter(FAMILY, DEPTH, 5, ShatterParams(core_fraction=0.4))
    tight = auto_shatter(FAMILY, DEPTH, 5, ShatterParams(core_fraction=0.5))

    compared = 0
    for a, b, r in zip(loose.edits, tight.edits, radii()):
        if r <= 0.5 or a.rot == 0.0 or b.rot == 0.0:
            continue
        assert math.copysign(1, a.rot) == math.copysign(1, b.rot)
        compared += 1
    assert compared > 10
