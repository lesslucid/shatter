import pytest

from shatter.dimensions import (
    PAGE_THICKNESS_INCHES,
    inches_to_pixels,
    panel_pixels,
    parse_trim,
    spine_width_inches,
    wrap_pixels,
)


def test_parse_trim():
    assert parse_trim("6x9") == (6.0, 9.0)
    assert parse_trim("8.5X11") == (8.5, 11.0)


@pytest.mark.parametrize("bad", ["6", "6x9x2", "sixxnine", "0x9", "-6x9"])
def test_parse_trim_rejects_nonsense(bad):
    with pytest.raises(ValueError):
        parse_trim(bad)


def test_panel_pixels():
    assert panel_pixels((6.0, 9.0), 300) == (1800, 2700)


def test_inches_to_pixels_rounds():
    assert inches_to_pixels(0.125, 300) == 38


def test_spine_width_scales_with_pages():
    assert spine_width_inches(120, "white") == pytest.approx(0.27024)
    assert spine_width_inches(240, "white") == pytest.approx(2 * 0.27024)


def test_cream_is_thicker_than_white():
    assert spine_width_inches(100, "cream") > spine_width_inches(100, "white")


def test_spine_width_rejects_bad_input():
    with pytest.raises(ValueError, match="at least 1"):
        spine_width_inches(0, "white")
    with pytest.raises(ValueError, match="Unknown paper"):
        spine_width_inches(100, "papyrus")


def test_every_paper_stock_has_a_thickness():
    for paper in PAGE_THICKNESS_INCHES:
        assert spine_width_inches(100, paper) > 0


def test_wrap_is_two_panels_plus_spine_and_outer_bleed():
    trim, dpi = (6.0, 9.0), 300
    width, height = wrap_pixels(trim, 120, "white", dpi)
    panel_w, panel_h = panel_pixels(trim, dpi)
    bleed = inches_to_pixels(0.125, dpi)
    spine = inches_to_pixels(spine_width_inches(120, "white"), dpi)

    assert width == 2 * panel_w + 2 * bleed + spine
    assert height == panel_h + 2 * bleed


def test_more_pages_widens_only_the_spine():
    thin = wrap_pixels((6.0, 9.0), 100, "white")
    thick = wrap_pixels((6.0, 9.0), 400, "white")
    assert thick[0] > thin[0]
    assert thick[1] == thin[1]
