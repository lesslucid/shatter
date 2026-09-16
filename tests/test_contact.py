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
