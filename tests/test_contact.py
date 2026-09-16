import pytest

from shatter.contact import SheetStyle, contact_sheet, describe, thumbnail
from shatter.spec import CoverSpec

STYLE = SheetStyle(thumb_width=60, thumb_height=90, columns=3, supersample=1)


def specs(count):
    return [CoverSpec(seed=index, zoom=60) for index in range(count)]


def test_thumbnail_is_the_requested_size():
    assert thumbnail(CoverSpec(zoom=60), STYLE).size == (60, 90)


def test_sheet_lays_out_rows_and_columns():
    sheet = contact_sheet(specs(7), STYLE)
    cell_w = STYLE.thumb_width + STYLE.padding
    cell_h = STYLE.thumb_height + STYLE.padding + STYLE.caption
    assert sheet.size == (3 * cell_w + STYLE.padding, 3 * cell_h + STYLE.padding)


def test_a_short_sheet_does_not_reserve_empty_columns():
    sheet = contact_sheet(specs(2), STYLE)
    cell_w = STYLE.thumb_width + STYLE.padding
    assert sheet.width == 2 * cell_w + STYLE.padding


def test_empty_sheet_is_rejected():
    with pytest.raises(ValueError, match="at least one"):
        contact_sheet([], STYLE)


def test_panel_n_shows_spec_n():
    """Panel order must match config order, or the saved configs point at the
    wrong picture."""
    wanted = specs(4)
    sheet = contact_sheet(wanted, STYLE)

    cell_w = STYLE.thumb_width + STYLE.padding
    cell_h = STYLE.thumb_height + STYLE.padding + STYLE.caption
    for index, spec in enumerate(wanted):
        x = STYLE.padding + (index % STYLE.columns) * cell_w
        y = STYLE.padding + (index // STYLE.columns) * cell_h
        panel = sheet.crop((x, y, x + STYLE.thumb_width, y + STYLE.thumb_height))
        assert panel.tobytes() == thumbnail(spec, STYLE).tobytes()


def test_description_names_what_varies():
    text = describe(CoverSpec(family="p2", seed=9))
    assert "p2" in text and "seed9" in text


def test_the_description_tells_two_palettes_apart():
    """Phase 14. Once breeding moves the palette, two panels that differ only in
    colour must not share a caption -- that is worse than no caption at all."""
    a = describe(CoverSpec(mode="wada", wada_combination=126))
    b = describe(CoverSpec(mode="wada", wada_combination=243, role_layout="full"))
    assert a != b
    assert "wada126" in a and "wada243" in b


def test_the_description_follows_the_colour_mode():
    classic = describe(CoverSpec(bg="#F2D9E6", tile_color="dark"))
    assert "#F2D9E6" in classic and "wada" not in classic

    wada = describe(CoverSpec(mode="wada", role_layout="shapes", role_permutation=4))
    assert "shapes" in wada and "perm4" in wada


def test_the_description_mentions_a_border_only_when_there_is_one():
    assert "border" not in describe(CoverSpec(border="none"))
    assert "black-border" in describe(CoverSpec(border="black"))


def test_a_split_names_its_second_colour():
    """Otherwise two split covers differing only in the second fill caption
    identically."""
    text = describe(CoverSpec(tile_split="by_type", tile_color_b="white"))
    assert "white" in text.splitlines()[1]
