"""The Sanzo Wada colour mode (phase 13).

Covers the dataset loader, the role assignment and its permutations, the
two-tier contrast floor, and the mode's palette. The decisions these pin down
are section 12.1, numbers 10-13; where a test exists to guard a decision rather
than an obvious behaviour, it says which.
"""

import itertools

import pytest

from shatter import wada
from shatter.color import (
    DEFAULT_WADA_COMBINATION,
    LAYOUT_SPLITS,
    ROLE_LAYOUTS,
    STRICT_FLOOR,
    TILE_PAIR_FLOOR,
    WADA_OVERLAP_BLEND,
    assign_roles,
    blend,
    contrast_failures,
    delta_e,
    effective_tile_split,
    lightness,
    offered,
    passes_contrast_floor,
    permutation_count,
    roles_for_layout,
    srgb_to_lab,
    wada_overlap,
    wada_palette,
)
from shatter.render import RenderParams
from shatter.spec import CoverSpec

THREE_COLOUR = DEFAULT_WADA_COMBINATION  # 126: Ivory Buff / Yellow Ocher / Deep Lyons Blue
FOUR_COLOUR = 1 + next(
    i for i, c in enumerate(wada.all_combinations()) if c.size == 4
)


# --- the dataset ---------------------------------------------------------


def test_the_dataset_has_the_shape_section_12s_arithmetic_assumes():
    wada.check_dataset()  # raises if not
    assert len(wada.all_combinations()) == 348
    assert {n: len(wada.combinations_of_size(n)) for n in (2, 3, 4)} == {
        2: 120, 3: 120, 4: 108
    }


def test_combinations_are_looked_up_by_id_and_bad_ids_are_named():
    assert wada.combination_by_id(1).id == 1
    assert wada.combination_by_id(348).id == 348
    for bad in (0, 349, -1):
        with pytest.raises(KeyError, match="valid range 1-348"):
            wada.combination_by_id(bad)


def test_every_colour_is_named_and_its_hex_matches_its_rgb():
    for combination in wada.all_combinations():
        for color in combination.colors:
            assert color.name
            assert color.hex.lstrip("#") == "%02x%02x%02x" % color.rgb


def test_the_loader_does_not_carry_the_shipped_lab():
    """Section 12.1, decision 13.

    The dataset's own `lab` disagrees with its `rgb` by up to 20 dE because
    upstream derived them separately. Not carrying it is what stops it being
    picked up by accident later; the floor must measure what is rendered.
    """
    assert "lab" not in wada.WadaColor.__dataclass_fields__


# --- perceptual maths ----------------------------------------------------


def test_lab_endpoints_and_distance():
    assert srgb_to_lab((255, 255, 255))[0] == pytest.approx(100.0)
    assert srgb_to_lab((0, 0, 0))[0] == pytest.approx(0.0)
    assert delta_e((0, 0, 0), (255, 255, 255)) == pytest.approx(100.0)
    assert delta_e((12, 34, 56), (12, 34, 56)) == 0.0
    assert delta_e((1, 2, 3), (4, 5, 6)) == delta_e((4, 5, 6), (1, 2, 3))


# --- role assignment (decision 10) ---------------------------------------


@pytest.mark.parametrize("layout", sorted(ROLE_LAYOUTS))
def test_permutation_zero_hands_the_colours_out_lightest_first(layout):
    size = len(roles_for_layout(layout))
    combination = next(c for c in wada.combinations_of_size(size))
    assigned = assign_roles(combination, layout, 0)
    ordered = [lightness(assigned[role]) for role in roles_for_layout(layout)]
    assert ordered == sorted(ordered, reverse=True)


def test_permutation_zero_is_the_house_look_not_its_inverse():
    """Section 12.1, decision 10.

    The classic default puts the box *above* the background in lightness (box
    L*=100, background 89.0, tiles 64.5). An earlier draft of section 12 sent the
    lightest colour to the background, which inverts that relationship; this is
    the test that would have caught it.
    """
    for layout in ("box", "full"):
        size = len(roles_for_layout(layout))
        for combination in wada.combinations_of_size(size):
            assigned = assign_roles(combination, layout, 0)
            assert lightness(assigned["box"]) > lightness(assigned["background"])
            assert lightness(assigned["background"]) > lightness(assigned["tile_a"])


def test_shapes_sends_the_lightest_colour_to_the_background_instead():
    """Not an inconsistency with the test above: `shapes` paints no box, so the
    background genuinely is the lightest thing on the cover."""
    for combination in wada.combinations_of_size(3):
        assigned = assign_roles(combination, "shapes", 0)
        assert lightness(assigned["background"]) > lightness(assigned["tile_a"])
        assert "box" not in assigned


def test_permutations_are_distinct_and_cover_every_ordering():
    combination = wada.combination_by_id(THREE_COLOUR)
    seen = {
        tuple(assign_roles(combination, "box", p).values())
        for p in range(permutation_count("box"))
    }
    assert len(seen) == permutation_count("box") == 6


def test_the_permutation_wraps_rather_than_failing():
    """Decision 12: the value is taken modulo k!, so no integer is an error."""
    combination = wada.combination_by_id(THREE_COLOUR)
    base = assign_roles(combination, "box", 0)
    assert assign_roles(combination, "box", 6) == base
    assert assign_roles(combination, "box", 600) == base
    assert assign_roles(combination, "box", 7) == assign_roles(combination, "box", 1)


def test_a_layout_and_a_combination_must_agree_on_size():
    with pytest.raises(ValueError, match="3 colours, but role layout 'full' needs 4"):
        assign_roles(wada.combination_by_id(THREE_COLOUR), "full", 0)


def test_an_unknown_layout_is_rejected_by_name():
    with pytest.raises(ValueError, match="Unknown role layout"):
        roles_for_layout("medallion")


# --- the contrast floor (decision 11) ------------------------------------

#: 19.7 dE apart: inside the strict floor, outside the lenient one. The whole
#: two-tier decision is visible in this one pair.
NEAR_A = (128, 128, 128)
NEAR_B = (180, 180, 180)


def test_the_two_floors_are_applied_to_the_right_pairs():
    assert TILE_PAIR_FLOOR < delta_e(NEAR_A, NEAR_B) < STRICT_FLOOR
    # tolerated between the two tile colours ...
    assert passes_contrast_floor({"tile_a": NEAR_A, "tile_b": NEAR_B})
    # ... and not between a tile and either ground
    assert not passes_contrast_floor({"box": NEAR_A, "tile_a": NEAR_B})
    assert not passes_contrast_floor({"background": NEAR_A, "tile_a": NEAR_B})


def test_a_failure_names_both_roles_and_the_floor_it_missed():
    (role_a, role_b, distance, floor), = contrast_failures(
        {"box": NEAR_A, "tile_a": NEAR_B}
    )
    assert {role_a, role_b} == {"box", "tile_a"}
    assert distance == pytest.approx(delta_e(NEAR_A, NEAR_B))
    assert floor == STRICT_FLOOR


def test_the_floor_only_compares_roles_the_layout_declares():
    """A `box` layout copies tile_a into tile_b. Comparing a colour with itself
    would be a distance of zero and would fail every combination."""
    assigned = assign_roles(wada.combination_by_id(THREE_COLOUR), "box", 0)
    assert "tile_b" not in assigned
    assert passes_contrast_floor(assigned)


def test_every_offered_assignment_passes_the_floor():
    """Phase 13's stated check, in full: not a sample."""
    for layout in ROLE_LAYOUTS:
        offers = offered(layout)
        assert offers, f"{layout} offers nothing"
        for combination_id, permutation in offers:
            assigned = assign_roles(
                wada.combination_by_id(combination_id), layout, permutation
            )
            assert passes_contrast_floor(assigned)


def test_reshuffling_rescues_combinations_the_default_ordering_fails():
    """Decision 11's rationale, made falsifiable.

    Under a *uniform* floor this number would be zero, because permuting roles
    cannot change the multiset of pairwise distances. It is only the lenient
    tile_a/tile_b floor that lets a reshuffle save anything, so if this ever
    reads zero the two-tier floor has stopped doing its job.
    """
    rescued = 0
    for combination in wada.combinations_of_size(4):
        assignments = [
            assign_roles(combination, "full", p)
            for p in range(permutation_count("full"))
        ]
        if not passes_contrast_floor(assignments[0]) and any(
            passes_contrast_floor(a) for a in assignments[1:]
        ):
            rescued += 1
    assert rescued > 0


def test_the_floor_never_rejects_a_combination_on_lightness_alone():
    """Decision 8 allows dark backgrounds; decision 11 must not quietly undo it."""
    dark_grounds = [
        combination_id
        for combination_id, permutation in offered("box")
        if lightness(
            assign_roles(wada.combination_by_id(combination_id), "box", permutation)[
                "background"
            ]
        )
        < 40
    ]
    assert dark_grounds


# --- the palette ---------------------------------------------------------


def test_the_box_layout_repeats_the_tile_colour_into_the_second_slot():
    palette = wada_palette(THREE_COLOUR, "box", 0, "none")
    assert palette.tile_b == palette.tile_a


def test_the_shapes_layout_paints_the_box_in_the_background():
    """Section 12's table: the box is invisible, exactly as classic mode's
    `box_color="bg"` makes it."""
    palette = wada_palette(THREE_COLOUR, "shapes", 0, "none")
    assert palette.box == palette.background
    assert palette.tile_b != palette.tile_a


def test_the_full_layout_fills_four_distinct_roles():
    palette = wada_palette(FOUR_COLOUR, "full", 0, "none")
    assert len({palette.background, palette.box, palette.tile_a, palette.tile_b}) == 4


def test_auto_overlap_blends_the_first_tile_halfway_to_the_box():
    """The phase 13 re-specification. Classic mode's branch on
    `tile_color == "white"` is meaningless once a tile is an arbitrary RGB."""
    palette = wada_palette(THREE_COLOUR, "box", 0, "auto")
    assert palette.overlap == blend(palette.tile_a, palette.box, WADA_OVERLAP_BLEND)


#: The overlap colour must stay visible against the tile it sits on, or overlap
#: colouring silently does nothing. This is NOT implied by the contrast floor --
#: an RGB midpoint is not a Lab midpoint, and an earlier draft of section 12
#: claimed it was. The measured worst case across every offered assignment is
#: 10.66 dE (median ~30); this threshold sits below that with room to spare, so
#: it catches a broken blend rather than tracking the data.
MIN_VISIBLE_OVERLAP = 8.0


@pytest.mark.parametrize("layout", sorted(ROLE_LAYOUTS))
def test_the_overlap_colour_stays_visible_against_its_own_tile(layout):
    for combination_id, permutation in offered(layout):
        palette = wada_palette(combination_id, layout, permutation, "auto")
        assert delta_e(palette.overlap, palette.tile_a) >= MIN_VISIBLE_OVERLAP
        assert delta_e(palette.overlap, palette.box) >= MIN_VISIBLE_OVERLAP


def test_overlap_none_and_explicit_hex_behave_as_they_do_in_classic_mode():
    assert wada_overlap("none", (1, 2, 3), (4, 5, 6)) is None
    assert wada_overlap("#102030", (1, 2, 3), (4, 5, 6)) == (16, 32, 48)


def test_a_wada_palette_still_gets_its_border_from_the_border_flag():
    params = CoverSpec(mode="wada", border="black").render_params(10, 10)
    from shatter.color import resolve_palette

    assert resolve_palette(params).border == (0, 0, 0)


# --- how the mode reaches the renderer -----------------------------------


def test_the_layout_owns_the_split_in_wada_mode_and_not_in_classic():
    for layout, split in LAYOUT_SPLITS.items():
        assert effective_tile_split("wada", layout, "single") == split
        assert effective_tile_split("wada", layout, "by_type") == split
    # classic mode hands the field straight back, so phases 11-12 are untouched
    assert effective_tile_split("classic", "shapes", "single") == "single"
    assert effective_tile_split("classic", "shapes", "by_type") == "by_type"


def test_the_spec_carries_the_wada_fields_into_render_params():
    spec = CoverSpec(
        mode="wada", wada_combination=THREE_COLOUR, role_layout="shapes",
        role_permutation=4,
    )
    params = spec.render_params(10, 20)
    assert params.mode == "wada"
    assert params.wada_combination == THREE_COLOUR
    assert params.role_layout == "shapes"
    assert params.role_permutation == 4
    assert params.tile_split == "by_type"  # the layout decided it


def test_a_config_written_before_phase_13_still_loads():
    """Hard rule 4: new fields are additive with defaults."""
    old = {"family": "p3", "zoom": 150, "bg": "#F2D9E6", "tile_color": "dark"}
    spec = CoverSpec.from_dict(old)
    assert spec.mode == "classic"
    assert spec.wada_combination == DEFAULT_WADA_COMBINATION
    assert spec.role_layout == "box"
    assert spec.role_permutation == 0


def test_a_wada_spec_round_trips_through_its_config():
    spec = CoverSpec(
        mode="wada", wada_combination=FOUR_COLOUR, role_layout="full",
        role_permutation=11,
    )
    assert CoverSpec.from_dict(spec.to_dict()) == spec


def test_the_wada_fields_do_not_disturb_a_classic_cover():
    """Decision 5 in miniature: the mode decides which fields are read."""
    from shatter.color import resolve_palette

    plain = RenderParams(width=10, height=10)
    fiddled = RenderParams(
        width=10, height=10, wada_combination=7, role_layout="full",
        role_permutation=13,
    )
    assert resolve_palette(plain) == resolve_palette(fiddled)
