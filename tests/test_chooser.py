"""The window is a thin shell, but its state machine is worth pinning.

Skipped wherever tkinter cannot open a display (CI, headless sessions).
"""

import random

import pytest

tk = pytest.importorskip("tkinter")

from shatter.breed import GENES  # noqa: E402
from shatter.chooser import (  # noqa: E402
    COLUMNS,
    CORNER_PRESETS,
    Chooser,
    corner_preset_name,
)
from shatter.spec import CoverSpec  # noqa: E402


@pytest.fixture
def root():
    try:
        window = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    window.withdraw()
    yield window
    window.destroy()


@pytest.fixture
def chooser(root, tmp_path):
    return Chooser(
        root, CoverSpec(zoom=60, box_color="bg"), tmp_path, random.Random(1)
    )


def test_opens_with_one_full_row_and_nothing_selected(chooser):
    assert len(chooser.rows[0]) == COLUMNS
    assert chooser.rows[1] == []
    assert chooser.selected is None


def test_breeding_without_a_selection_asks_for_one(chooser):
    chooser.breed("closer")
    assert "Pick a cover" in chooser.status.cget("text")
    assert chooser.rows[1] == []


def test_clicking_an_empty_cell_selects_nothing(chooser):
    chooser.select(1, 0)
    assert chooser.selected is None


def test_breeding_from_the_top_row_fills_the_bottom(chooser):
    chooser.select(0, 2)
    top = list(chooser.rows[0])
    chooser.breed("closer")

    assert chooser.rows[0] == top, "the top row should not move yet"
    assert len(chooser.rows[1]) == COLUMNS
    assert chooser.selected == (0, 2)


def test_breeding_from_the_bottom_row_promotes_it(chooser):
    chooser.select(0, 0)
    chooser.breed("closer")
    children = list(chooser.rows[1])

    chooser.select(1, 3)
    chooser.breed("further")

    assert chooser.rows[0] == children
    assert chooser.selected == (0, 3), "selection follows the parent upward"
    assert chooser.rows[1] != children


def test_children_descend_from_the_selection(chooser):
    chooser.select(0, 1)
    parent = chooser.rows[0][1]
    chooser.breed("closer")

    # closer keeps the seed most of the time, so most children share the parent's
    assert sum(1 for kid in chooser.rows[1] if kid.seed == parent.seed) >= 3


@pytest.mark.parametrize("bad", ["", "nope", "0", "-4"])
def test_print_rejects_a_bad_page_count(chooser, bad):
    chooser.select(0, 0)
    chooser.pages_entry.delete(0, "end")
    chooser.pages_entry.insert(0, bad)
    chooser.print_cover()
    assert "Pages must be" in chooser.status.cget("text")


def test_print_without_a_selection_asks_for_one(chooser):
    chooser.print_cover()
    assert "Pick a cover" in chooser.status.cget("text")


def test_print_writes_the_cover_and_the_recipe(chooser, tmp_path):
    """A printed cover has to be reproducible, so the spec goes out with it."""
    chooser.select(0, 0)
    chooser.print_cover()

    written = {path.name for path in tmp_path.iterdir()}
    assert {"front.png", "back.png", "cover_wrap.png", "spec.json"} <= written

    reloaded = CoverSpec.load(tmp_path / "spec.json")
    assert reloaded == chooser.rows[0][0]


# --- Phase 9: the lock checkboxes ------------------------------------------


def test_opens_with_nothing_locked(chooser):
    assert chooser.locked_genes() == frozenset()


def test_starting_locks_are_applied_to_the_checkboxes(root, tmp_path):
    from shatter.chooser import Chooser

    started = Chooser(
        root, CoverSpec(zoom=60, box_color="bg"), tmp_path, random.Random(1),
        locked=["colour", "tiling"],
    )
    assert started.locked_genes() == frozenset({"colour", "tiling"})


def test_a_locked_gene_is_held_across_the_children(chooser):
    chooser.lock_vars["colour"].set(True)
    chooser.select(0, 0)
    parent = chooser.rows[0][0]
    chooser.breed("further")

    for child in chooser.rows[1]:
        assert (child.bg, child.tile_color, child.box_color) == (
            parent.bg, parent.tile_color, parent.box_color
        )


def test_locking_everything_refuses_to_breed_and_says_why(chooser):
    """Breeding a row of five identical covers reads as a bug. Refusing also
    leaves the children you already had in place, rather than wiping them."""
    for var in chooser.lock_vars.values():
        var.set(True)
    chooser.select(0, 0)
    chooser.breed("further")

    assert chooser.rows[1] == [], "row 2 must be left alone"
    assert "all locked" in chooser.status.cget("text")


def test_closer_goes_inert_long_before_every_gene_is_locked(chooser):
    """Closer only ever moves the minor genes (section 11.2), so three locks are
    enough to kill it -- and a dead button must say so, not sit there."""
    for name in ("shatter", "spacing", "seed"):
        chooser.lock_vars[name].set(True)
    chooser.select(0, 0)
    chooser.breed("closer")

    assert chooser.rows[1] == []
    text = chooser.status.cget("text")
    assert "Closer" in text and "all locked" in text


def test_further_still_works_with_the_minor_genes_locked(chooser):
    """The escape route: hold the design still and let only the palette move."""
    for name in ("shatter", "spacing", "seed", "tiling", "zoom"):
        chooser.lock_vars[name].set(True)
    chooser.select(0, 0)
    chooser.breed("further")

    assert len(chooser.rows[1]) == COLUMNS


def test_locking_a_button_dead_is_flagged_when_the_box_is_ticked(chooser):
    """Said at the moment of ticking, not saved up for the next button press."""
    for name in ("shatter", "spacing"):
        chooser.lock_vars[name].set(True)
    gene = next(g for g in GENES if g.name == "seed")
    chooser.lock_vars["seed"].set(True)
    chooser.explain_lock(gene)
    assert "all locked" in chooser.status.cget("text")


def test_the_status_line_names_what_is_being_held(chooser):
    chooser.lock_vars["spacing"].set(True)
    chooser.select(0, 0)
    chooser.breed("closer")
    assert "holding spacing" in chooser.status.cget("text")


def test_toggling_a_lock_explains_it(chooser):
    gene = next(g for g in GENES if g.name == "shatter")
    chooser.lock_vars["shatter"].set(True)
    chooser.explain_lock(gene)
    assert "held" in chooser.status.cget("text")
    chooser.lock_vars["shatter"].set(False)
    chooser.explain_lock(gene)
    assert "free" in chooser.status.cget("text")


# --- the colour-model switch -------------------------------------------------


def test_the_radio_starts_on_the_mode_it_was_launched_with(root, tmp_path):
    window = Chooser(root, CoverSpec(zoom=60, mode="wada"), tmp_path, random.Random(1))
    assert window.mode_var.get() == "wada"
    assert all(spec.mode == "wada" for spec in window.rows[0])


def test_switching_converts_only_the_selected_cover(chooser):
    chooser.select(0, 2)
    chooser.mode_var.set("wada")
    chooser.switch_mode()

    assert chooser.rows[0][2].mode == "wada"
    assert [spec.mode for spec in chooser.rows[0]] == [
        "classic", "classic", "wada", "classic", "classic"
    ]


def test_switching_without_a_selection_converts_nothing(chooser):
    chooser.mode_var.set("wada")
    chooser.switch_mode()
    assert all(spec.mode == "classic" for spec in chooser.rows[0])
    assert "Pick a cover" in chooser.status.cget("text")


def test_the_radio_follows_the_selection(chooser):
    chooser.select(0, 0)
    chooser.mode_var.set("wada")
    chooser.switch_mode()
    assert chooser.mode_var.get() == "wada"

    # a neighbour was never converted, so selecting it must report classic
    chooser.select(0, 1)
    assert chooser.mode_var.get() == "classic"


def test_switching_back_and_forth_loses_nothing(chooser):
    chooser.select(0, 0)
    before = chooser.rows[0][0]

    chooser.mode_var.set("wada")
    chooser.switch_mode()
    chooser.mode_var.set("classic")
    chooser.switch_mode()

    assert chooser.rows[0][0] == before


def test_breeding_after_a_switch_stays_in_the_new_mode(chooser):
    """Decision 5 survives the switch: the user crosses between aesthetics,
    Further never does."""
    chooser.select(0, 0)
    chooser.mode_var.set("wada")
    chooser.switch_mode()
    chooser.breed("further")

    assert chooser.rows[1]
    assert all(child.mode == "wada" for child in chooser.rows[1])


# --- the feature-box corner control ------------------------------------------


def test_the_corner_radio_starts_on_the_launched_value(root, tmp_path):
    window = Chooser(root, CoverSpec(zoom=60, box_corner=0.2), tmp_path, random.Random(1))
    assert window.corner_var.get() == "round"


def test_a_cli_set_radius_that_matches_no_preset_lights_nothing(root, tmp_path):
    """`--box-corner 0.22` is legal and is not one of the four. Lighting the
    nearest preset would misreport the cover; an empty string lights none."""
    window = Chooser(root, CoverSpec(zoom=60, box_corner=0.22), tmp_path, random.Random(1))
    assert window.corner_var.get() == ""
    assert all(spec.box_corner == 0.22 for spec in window.rows[0])


def test_switching_corners_converts_only_the_selected_cover(chooser):
    chooser.select(0, 2)
    chooser.corner_var.set("stadium")
    chooser.switch_corner()

    assert chooser.rows[0][2].box_corner == 0.5
    assert [spec.box_corner for spec in chooser.rows[0]] == [0.0, 0.0, 0.5, 0.0, 0.0]


def test_switching_corners_without_a_selection_converts_nothing(chooser):
    chooser.corner_var.set("round")
    chooser.switch_corner()
    assert all(spec.box_corner == 0.0 for spec in chooser.rows[0])
    assert "Pick a cover" in chooser.status.cget("text")


def test_the_corner_radio_follows_the_selection(chooser):
    chooser.select(0, 0)
    chooser.corner_var.set("soft")
    chooser.switch_corner()
    assert chooser.corner_var.get() == "soft"

    chooser.select(0, 1)
    assert chooser.corner_var.get() == "square"


def test_children_inherit_the_chosen_corner(chooser):
    """`box_corner` is not a gene (decision 18), so breeding must carry it
    through untouched -- which is what makes choosing one here worth doing."""
    chooser.select(0, 0)
    chooser.corner_var.set("round")
    chooser.switch_corner()
    chooser.breed("further")

    assert chooser.rows[1]
    assert all(child.box_corner == 0.2 for child in chooser.rows[1])


def test_the_corner_and_colour_controls_are_independent(chooser):
    chooser.select(0, 0)
    chooser.corner_var.set("stadium")
    chooser.switch_corner()
    chooser.mode_var.set("wada")
    chooser.switch_mode()

    spec = chooser.rows[0][0]
    assert spec.box_corner == 0.5 and spec.mode == "wada"


def test_corner_preset_names_round_trip():
    for name, value in CORNER_PRESETS.items():
        assert corner_preset_name(value) == name
    assert corner_preset_name(0.22) == ""


# --- the colour dial ---------------------------------------------------------


@pytest.fixture
def wada_chooser(root, tmp_path):
    return Chooser(root, CoverSpec(zoom=60, mode="wada"), tmp_path, random.Random(1))


def test_stepping_the_dial_without_a_selection_asks_for_one(chooser):
    chooser.dial_step(1)
    assert chooser.rows[1] == []
    assert "Pick a cover" in chooser.status.cget("text")


def test_the_dial_fills_the_variations_row_with_recolourings(wada_chooser):
    """It recolours the selected cover: everything but the palette must survive."""
    wada_chooser.select(0, 0)
    parent = wada_chooser.rows[0][0]
    wada_chooser.dial_step(1)

    assert len(wada_chooser.rows[1]) == COLUMNS
    for child in wada_chooser.rows[1]:
        assert child.seed == parent.seed
        assert child.family == parent.family
        assert child.core_fraction == parent.core_fraction
    combinations = [child.wada_combination for child in wada_chooser.rows[1]]
    assert len(set(combinations)) == COLUMNS


def test_the_dial_makes_no_random_draws(wada_chooser):
    """Phase 16's whole advantage: stepping colours cannot disturb the breeding
    stream, so a saved --breed-seed still reproduces its row afterwards."""
    wada_chooser.select(0, 0)
    before = wada_chooser.rng.getstate()
    wada_chooser.dial_step(1)
    wada_chooser.dial_step(1)
    wada_chooser.cycle_roles()
    assert wada_chooser.rng.getstate() == before


def test_stepping_forward_and_back_returns_to_the_same_page(wada_chooser):
    wada_chooser.select(0, 0)
    wada_chooser.dial_step(1)
    there = [spec.wada_combination for spec in wada_chooser.rows[1]]
    wada_chooser.dial_step(1)
    wada_chooser.dial_step(-1)
    assert [spec.wada_combination for spec in wada_chooser.rows[1]] == there


def test_picking_a_cover_the_dial_offered_does_not_lose_your_place(wada_chooser):
    """Decision 23: browsing is continuous. Clicking one of the results to look
    at it must not re-anchor the sweep."""
    wada_chooser.select(0, 0)
    wada_chooser.dial_step(1)
    wada_chooser.dial_step(1)
    page_before = wada_chooser.colour_page

    wada_chooser.select(1, 2)                      # a cover the dial put there
    assert wada_chooser.colour_page == page_before
    wada_chooser.dial_step(1)
    assert wada_chooser.colour_page == page_before + 1


def test_choosing_a_different_parent_re_anchors_the_dial(wada_chooser):
    wada_chooser.select(0, 0)
    wada_chooser.dial_step(1)
    assert wada_chooser.dial_anchor is not None

    wada_chooser.select(0, 3)
    assert wada_chooser.dial_anchor is None
    assert wada_chooser.colour_page is None


def test_breeding_re_anchors_the_dial(wada_chooser):
    """After breeding you are working from a different cover, so the old
    position means nothing (decision 23)."""
    wada_chooser.select(0, 0)
    wada_chooser.dial_step(1)
    wada_chooser.breed("further")
    assert wada_chooser.dial_anchor is None
    assert wada_chooser.colour_page is None


def test_cycling_roles_changes_only_the_assignment(wada_chooser):
    wada_chooser.select(0, 1)
    before = wada_chooser.rows[0][1]
    wada_chooser.cycle_roles()
    after = wada_chooser.rows[0][1]

    assert after.role_permutation != before.role_permutation
    assert after.with_changes(role_permutation=before.role_permutation) == before


def test_cycling_roles_on_a_classic_cover_says_why_it_did_nothing(chooser):
    chooser.select(0, 0)
    before = chooser.rows[0][0]
    chooser.cycle_roles()
    assert chooser.rows[0][0] == before
    assert "wada" in chooser.status.cget("text")


def test_cycling_roles_without_a_selection_asks_for_one(wada_chooser):
    wada_chooser.cycle_roles()
    assert "Pick a cover" in wada_chooser.status.cget("text")


# --- the tiles (float / clipped / solid) control ------------------------------


def test_the_tiles_radio_starts_on_the_launched_look(root, tmp_path):
    window = Chooser(
        root, CoverSpec(zoom=60, clip_tiles=True, box_margin=-0.1), tmp_path,
        random.Random(1),
    )
    assert window.fit_var.get() == "solid"


def test_the_three_looks_are_derived_from_the_two_fields(chooser):
    from shatter.chooser import tile_fit_name

    assert tile_fit_name(CoverSpec()) == "float"
    assert tile_fit_name(CoverSpec(clip_tiles=True)) == "clipped"
    assert tile_fit_name(CoverSpec(clip_tiles=True, box_margin=-0.1)) == "solid"


def test_choosing_solid_clips_and_overfills(chooser):
    chooser.select(0, 0)
    chooser.fit_var.set("solid")
    chooser.switch_fit()

    spec = chooser.rows[0][0]
    assert spec.clip_tiles is True and spec.box_margin < 0


def test_coming_back_from_solid_drops_the_overfill(chooser):
    """Otherwise it would still read as solid and the radio would fight you."""
    chooser.select(0, 0)
    chooser.fit_var.set("solid")
    chooser.switch_fit()
    chooser.fit_var.set("clipped")
    chooser.switch_fit()

    spec = chooser.rows[0][0]
    assert spec.clip_tiles is True and spec.box_margin >= 0
    assert chooser.fit_var.get() == "clipped"


def test_switching_tiles_converts_only_the_selected_cover(chooser):
    chooser.select(0, 2)
    chooser.fit_var.set("solid")
    chooser.switch_fit()
    assert [spec.clip_tiles for spec in chooser.rows[0]] == [
        False, False, True, False, False
    ]


def test_switching_tiles_without_a_selection_converts_nothing(chooser):
    chooser.fit_var.set("solid")
    chooser.switch_fit()
    assert all(spec.clip_tiles is False for spec in chooser.rows[0])
    assert "Pick a cover" in chooser.status.cget("text")


# --- the grid checkbox --------------------------------------------------------


def test_the_grid_checkbox_starts_on_the_launched_value(root, tmp_path):
    window = Chooser(root, CoverSpec(zoom=60, grid_lines=True), tmp_path, random.Random(1))
    assert window.grid_var.get() is True


def test_ticking_the_grid_converts_only_the_selected_cover(chooser):
    chooser.select(0, 1)
    chooser.grid_var.set(True)
    chooser.switch_grid()
    assert [spec.grid_lines for spec in chooser.rows[0]] == [
        False, True, False, False, False
    ]


def test_the_grid_checkbox_follows_the_selection(chooser):
    chooser.select(0, 0)
    chooser.grid_var.set(True)
    chooser.switch_grid()
    chooser.select(0, 1)
    assert chooser.grid_var.get() is False


def test_ticking_the_grid_without_a_selection_converts_nothing(chooser):
    chooser.grid_var.set(True)
    chooser.switch_grid()
    assert all(spec.grid_lines is False for spec in chooser.rows[0])
    assert "Pick a cover" in chooser.status.cget("text")
    assert chooser.grid_var.get() is False, "the box should not stay ticked"


def test_the_grid_warns_when_solid_tiles_would_hide_it(chooser):
    chooser.select(0, 0)
    chooser.fit_var.set("solid")
    chooser.switch_fit()
    chooser.grid_var.set(True)
    chooser.switch_grid()
    assert "invisible" in chooser.status.cget("text").lower()
