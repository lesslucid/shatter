"""The colour model (phase 10).

Most of these moved here from test_render.py when colour resolution moved out of
the renderer. They test the same things; only the import changed.
"""

import pytest

from shatter.color import (
    DARKEN_FACTOR,
    Palette,
    blend,
    classic_overlap,
    classic_palette,
    darken,
    parse_hex,
    resolve_border,
    resolve_color,
    resolve_palette,
)
from shatter.render import RenderParams
from shatter.spec import CoverSpec

BG = "#F2D9E6"


def test_parse_hex():
    assert parse_hex("#F2D9E6") == (242, 217, 230)
    assert parse_hex("F2D9E6") == (242, 217, 230)


def test_parse_hex_rejects_bad_input():
    with pytest.raises(ValueError):
        parse_hex("#FFF")


def test_darken():
    assert darken((100, 200, 0), 0.7) == (70, 140, 0)


def test_blend():
    assert blend((0, 0, 0), (100, 200, 50), 0.5) == (50, 100, 25)
    assert blend((10, 20, 30), (90, 80, 70), 0.0) == (10, 20, 30)


def test_resolve_color():
    bg = parse_hex(BG)
    assert resolve_color("white", bg) == (255, 255, 255)
    assert resolve_color("bg", bg) == bg
    assert resolve_color("dark", bg) == darken(bg)
    with pytest.raises(ValueError):
        resolve_color("puce", bg)


# --- the overlap rule ------------------------------------------------------


def test_overlap_color_is_darker_for_dark_tiles():
    bg = parse_hex(BG)
    overlap = classic_overlap("auto", "dark", bg)
    assert overlap == darken(bg, DARKEN_FACTOR**2)
    assert sum(overlap) < sum(darken(bg))


def test_overlap_color_moves_white_tiles_toward_the_background():
    """White multiplied by white is still white, so white needs its own rule."""
    bg = parse_hex(BG)
    overlap = classic_overlap("auto", "white", bg)
    assert overlap == blend((255, 255, 255), bg, 0.5)
    assert sum(bg) < sum(overlap) < 255 * 3


def test_overlap_color_accepts_an_explicit_hex():
    assert classic_overlap("#102030", "dark", parse_hex(BG)) == (16, 32, 48)


def test_overlap_none_becomes_no_overlap_colour():
    """'none' is the renderer's switch between flat fills and coverage counting,
    so it has to arrive as None rather than as a string to compare."""
    assert classic_overlap("none", "dark", parse_hex(BG)) is None


def test_bg_tiles_keep_their_longstanding_overlap_colour():
    """Undocumented in section 8 but longstanding, so pinned rather than tidied."""
    bg = parse_hex(BG)
    assert classic_overlap("auto", "bg", bg) == darken(bg)


# --- the Palette ------------------------------------------------------------


def test_classic_palette_fills_every_role():
    palette = classic_palette(BG, "dark", "white", "auto")
    bg = parse_hex(BG)
    assert palette.background == bg
    assert palette.box == (255, 255, 255)
    assert palette.tile_a == darken(bg)
    assert palette.overlap == darken(bg, DARKEN_FACTOR**2)


def test_classic_mode_does_not_split_tiles_by_shape():
    """Phase 12 gives tile_b its own colour; until then the two must agree, so a
    renderer reading either one gets the same answer."""
    for tile in ("white", "dark", "bg"):
        box = "white" if tile != "white" else "dark"
        palette = classic_palette(BG, tile, box, "auto")
        assert palette.tile_a == palette.tile_b


def test_classic_mode_draws_no_border():
    """Phase 11 fills this in; None is what 'borderless' means to the renderer."""
    assert classic_palette(BG, "dark", "white", "auto").border is None


def test_palette_is_immutable():
    palette = classic_palette(BG, "dark", "white", "auto")
    with pytest.raises(Exception):
        palette.background = (0, 0, 0)


# --- mode dispatch ----------------------------------------------------------


def test_resolve_palette_reads_the_flat_fields():
    params = RenderParams(width=10, height=10, bg=BG, tile_color="white")
    assert resolve_palette(params) == classic_palette(BG, "white", "white", "auto")


def test_classic_is_the_default_mode():
    assert CoverSpec().mode == "classic"
    assert RenderParams(width=10, height=10).mode == "classic"


def test_an_unknown_mode_is_rejected_by_name():
    # Was "wada" until phase 13 made that a real mode; the claim under test is
    # about the error, not about which name happens to be unknown today.
    params = RenderParams(width=10, height=10, mode="bauhaus")
    with pytest.raises(ValueError, match="Unknown colour mode"):
        resolve_palette(params)


def test_the_spec_carries_its_mode_into_render_params():
    assert CoverSpec(mode="classic").render_params(10, 20).mode == "classic"


def test_a_palette_has_exactly_the_six_documented_roles():
    assert set(Palette.__dataclass_fields__) == {
        "background", "box", "tile_a", "tile_b", "border", "overlap",
    }


# --- borders (phase 11) -----------------------------------------------------


def test_resolve_border_styles():
    assert resolve_border("none") is None
    assert resolve_border("black") == (0, 0, 0)
    assert resolve_border("white") == (255, 255, 255)


def test_unknown_border_style_is_rejected_by_name():
    with pytest.raises(ValueError, match="Unknown border style"):
        resolve_border("dotted")


def test_borderless_is_the_default():
    assert CoverSpec().border == "none"
    assert RenderParams(width=10, height=10).border == "none"
    assert resolve_palette(RenderParams(width=10, height=10)).border is None


def test_the_border_reaches_the_palette():
    params = RenderParams(width=10, height=10, border="black")
    assert resolve_palette(params).border == (0, 0, 0)


def test_the_border_is_independent_of_the_tile_and_box_colours():
    """A border separates a tile from its neighbour, so it must not be derived
    from the background the way 'dark' is."""
    for bg in ("#F2D9E6", "#E9E4D8"):
        for tile in ("white", "dark", "bg"):
            box = "white" if tile != "white" else "dark"
            params = RenderParams(
                width=10, height=10, bg=bg, tile_color=tile,
                box_color=box, border="black",
            )
            assert resolve_palette(params).border == (0, 0, 0)


# --- two tile colours (phase 12) --------------------------------------------


def test_tiles_are_not_split_by_default():
    assert CoverSpec().tile_split == "single"
    assert RenderParams(width=10, height=10).tile_split == "single"


def test_an_unsplit_palette_gives_both_tile_roles_the_same_colour():
    palette = resolve_palette(RenderParams(width=10, height=10, tile_color="dark"))
    assert palette.tile_a == palette.tile_b


def test_a_split_palette_resolves_the_second_tile_colour():
    params = RenderParams(
        width=10, height=10, tile_split="by_type",
        tile_color="dark", tile_color_b="white",
    )
    palette = resolve_palette(params)
    assert palette.tile_a == darken(parse_hex(BG))
    assert palette.tile_b == (255, 255, 255)


def test_tile_color_b_is_ignored_when_the_tiles_are_not_split():
    """Otherwise setting it would quietly change a cover that never asked to split."""
    base = RenderParams(width=10, height=10, tile_color="dark")
    with_b = RenderParams(width=10, height=10, tile_color="dark", tile_color_b="white")
    assert resolve_palette(base) == resolve_palette(with_b)


def test_the_overlap_colour_follows_the_first_tile_colour_when_split():
    """One overlap colour covers every kind of overlap (decision 3), so it has to
    follow one of the two; following tile_a keeps a split cover's overlaps the
    same as the unsplit one it was bred from."""
    unsplit = RenderParams(width=10, height=10, tile_color="dark")
    split = RenderParams(
        width=10, height=10, tile_split="by_type",
        tile_color="dark", tile_color_b="white",
    )
    assert resolve_palette(split).overlap == resolve_palette(unsplit).overlap


def test_an_unknown_tile_split_is_rejected_by_name():
    params = RenderParams(width=10, height=10, tile_split="threeway")
    with pytest.raises(ValueError, match="Unknown tile split"):
        resolve_palette(params)


def test_a_border_and_a_split_compose():
    params = RenderParams(
        width=10, height=10, border="black", tile_split="by_type",
        tile_color="dark", tile_color_b="white",
    )
    palette = resolve_palette(params)
    assert palette.border == (0, 0, 0)
    assert palette.tile_a != palette.tile_b
