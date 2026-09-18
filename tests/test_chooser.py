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
