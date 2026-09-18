"""The colour dial (phase 16).

The enumeration is easy; the ordering is the design (section 12.1, decisions 20
and 21). These tests pin the ordering, the wrap, and the one property that made
this phase cheap: it touches no random draws, so it cannot disturb a breed seed.
"""

import colorsys
import random

import pytest

from shatter import dial, wada
from shatter.breed import PALETTES
from shatter.color import offered_by_combination, parse_hex, passes_contrast_floor, assign_roles
from shatter.spec import CoverSpec

WADA = CoverSpec(mode="wada")
CLASSIC = CoverSpec()


def hue_of(rgb):
    return colorsys.rgb_to_hsv(*[channel / 255 for channel in rgb])[0]


@pytest.mark.parametrize("spec", [WADA, CLASSIC], ids=["wada", "classic"])
def test_the_dial_changes_colour_and_nothing_else(spec):
    """It recolours *this* cover; the arrangement must survive untouched."""
    untouched = [
        "family", "seed", "zoom", "depth", "core_fraction", "falloff", "max_push",
        "jitter", "max_rotation", "dropout", "tile_gap", "box_margin", "box_corner",
        "mode",
    ]
    for entry in dial.entries(spec):
        for field in untouched:
            assert getattr(entry, field) == getattr(spec, field), field


def fingerprint(spec):
    """`CoverSpec` is a plain dataclass, so it is unhashable; compare on its
    serialised form instead."""
    return tuple(sorted(spec.to_dict().items()))


@pytest.mark.parametrize("spec", [WADA, CLASSIC], ids=["wada", "classic"])
def test_every_entry_is_distinct(spec):
    entries = [fingerprint(entry) for entry in dial.entries(spec)]
    assert len(set(entries)) == len(entries)


@pytest.mark.parametrize("spec", [WADA, CLASSIC], ids=["wada", "classic"])
def test_the_dial_is_ordered_by_the_background_hue(spec):
    """Decision 21. Combination id is stable but arbitrary, which is exactly the
    wrong property for hunting a colour."""
    from shatter.render import RenderParams
    from shatter.color import resolve_palette

    hues = [
        hue_of(resolve_palette(entry.render_params(10, 10)).background)
        for entry in dial.entries(spec)
    ]
    assert hues == sorted(hues)


def test_a_wada_entry_always_uses_an_assignment_that_clears_the_floor():
    for entry in dial.entries(WADA):
        assigned = assign_roles(
            wada.combination_by_id(entry.wada_combination),
            entry.role_layout,
            entry.role_permutation,
        )
        assert passes_contrast_floor(assigned)


@pytest.mark.parametrize("layout", ["box", "shapes", "full"])
def test_the_representative_assignment_is_always_legal(layout):
    for combination, legal in offered_by_combination(layout).items():
        assert dial.representative_permutation(layout, combination) in legal


def test_the_representative_is_the_house_look_wherever_it_can_be():
    """Permutation 0 is the house ordering (decision 10) and is used whenever it
    clears the floor -- but 13 of the 103 `full` combinations cannot take it, so
    this cannot be the constant it looks like it should be."""
    layout = "full"
    chosen = {
        combination: dial.representative_permutation(layout, combination)
        for combination in offered_by_combination(layout)
    }
    assert 0 < sum(1 for value in chosen.values() if value != 0) < len(chosen)
    for combination, value in chosen.items():
        if value != 0:
            assert 0 not in offered_by_combination(layout)[combination]


def test_the_classic_dial_walks_the_curated_palettes():
    assert set(dial.classic_order()) == set(PALETTES)


@pytest.mark.parametrize("spec", [WADA, CLASSIC], ids=["wada", "classic"])
def test_a_full_sweep_visits_every_entry_exactly_once(spec):
    """No cover appears twice in a sweep and none is skipped -- which is why the
    last page is allowed to be short rather than padded from the start."""
    seen = []
    for index in range(dial.page_count(spec)):
        seen.extend(fingerprint(entry) for entry in dial.page(spec, index))
    entries = [fingerprint(entry) for entry in dial.entries(spec)]
    assert seen == entries


@pytest.mark.parametrize("spec", [WADA, CLASSIC], ids=["wada", "classic"])
def test_paging_wraps_at_both_ends(spec):
    """Hue is a circle: past the reds at one end are the reds at the other."""
    total = dial.page_count(spec)
    assert dial.page(spec, total) == dial.page(spec, 0)
    assert dial.page(spec, -1) == dial.page(spec, total - 1)


def test_position_finds_a_cover_on_its_own_dial():
    entries = dial.entries(WADA)
    for index in (0, 7, len(entries) - 1):
        assert dial.position(entries[index]) == index


def test_a_cover_that_is_not_on_the_dial_starts_from_the_beginning():
    """A hand-written config may name a combination the floor rejects. That is
    legal to render (decision 12) and simply has no place in the ordering."""
    off_dial = WADA.with_changes(wada_combination=337, role_permutation=4)
    assert 337 not in dial.wada_order("box")
    assert dial.position(off_dial) == 0


def test_cycling_roles_stays_inside_the_floor_and_comes_back_round():
    spec = WADA
    seen = []
    for _ in range(12):
        spec = dial.next_permutation(spec)
        seen.append(spec.role_permutation)
        assigned = assign_roles(
            wada.combination_by_id(spec.wada_combination), spec.role_layout,
            spec.role_permutation,
        )
        assert passes_contrast_floor(assigned)
    assert len(set(seen)) > 1, "the assignment never moved"
    assert seen[0] in seen[1:], "cycling never returned to where it started"


def test_cycling_roles_changes_only_the_assignment():
    moved = dial.next_permutation(WADA)
    assert moved.with_changes(role_permutation=WADA.role_permutation) == WADA


def test_a_classic_cover_has_no_roles_to_cycle():
    assert dial.next_permutation(CLASSIC) == CLASSIC


def test_the_dial_consumes_no_randomness():
    """The reason phase 16 broke no saved breed seed. If the dial ever reaches
    for `random`, this fails rather than the stream golden failing much later."""
    def explode(*args, **kwargs):
        raise AssertionError("the dial made a random draw")

    saved = (random.random, random.choice, random.randrange, random.shuffle)
    random.random, random.choice, random.randrange, random.shuffle = (explode,) * 4
    try:
        dial.entries(WADA)
        dial.page(WADA, 3)
        dial.position(WADA)
        dial.next_permutation(WADA)
        dial.entries(CLASSIC)
        dial.page(CLASSIC, 2)
    finally:
        random.random, random.choice, random.randrange, random.shuffle = saved


@pytest.mark.parametrize("spec", [WADA, CLASSIC], ids=["wada", "classic"])
def test_the_same_page_always_holds_the_same_covers(spec):
    assert dial.page(spec, 4) == dial.page(spec, 4)
