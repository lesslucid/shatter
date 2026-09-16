import pytest
from PIL import Image

from shatter.assemble import (
    GUIDE_SAFE,
    GUIDE_SPINE,
    GUIDE_TRIM,
    WrapGeometry,
    annotate_wrap,
    build_wrap,
    save_png,
)
from shatter.autoshatter import ShatterParams, auto_shatter
from shatter.dimensions import (
    inches_to_pixels,
    panel_pixels,
    spine_width_inches,
    wrap_pixels,
)
from shatter.color import parse_hex
from shatter.render import RenderParams, render_back, render_front

TRIM, DPI, PAGES = (6.0, 9.0), 50, 120
BG = "#F2D9E6"


def panels():
    width, height = panel_pixels(TRIM, DPI)
    params = RenderParams(
        width=width,
        height=height,
        bleed=inches_to_pixels(0.125, DPI),
        bg=BG,
        box_color="bg",
        tile_color="dark",
        supersample=1,
    )
    layout = auto_shatter("p3", 3, 1, ShatterParams())
    return render_front(layout, params), render_back(params), params


def test_back_is_plain_background():
    _front, back, _params = panels()
    assert back.getcolors() == [(back.width * back.height, parse_hex(BG))]


def test_wrap_matches_the_computed_dimensions():
    front, back, params = panels()
    spine = inches_to_pixels(spine_width_inches(PAGES, "white"), DPI)
    wrap = build_wrap(front, back, spine, params.bleed)
    assert wrap.size == wrap_pixels(TRIM, PAGES, "white", DPI)


def test_front_panel_lands_on_the_right():
    """KDP wraps read back | spine | front, so the art must be right of centre."""
    front, back, params = panels()
    spine = inches_to_pixels(spine_width_inches(PAGES, "white"), DPI)
    wrap = build_wrap(front, back, spine, params.bleed)

    midpoint = wrap.width // 2
    left = wrap.crop((0, 0, midpoint, wrap.height))
    right = wrap.crop((midpoint, 0, wrap.width, wrap.height))

    assert len(left.getcolors(1 << 24)) == 1  # back cover: flat pastel
    assert len(right.getcolors(1 << 24)) > 1  # front cover: the shatter


def test_wrap_rejects_mismatched_panels():
    front, _back, params = panels()
    with pytest.raises(ValueError, match="Panel sizes differ"):
        build_wrap(front, Image.new("RGB", (10, 10)), 20, params.bleed)


def test_saved_png_declares_its_resolution(tmp_path):
    """PNG stores resolution as integer pixels-per-metre, so 300 DPI comes back
    as 299.9994. That is the format, not a rounding bug."""
    _front, back, _params = panels()
    path = save_png(back, tmp_path / "nested" / "back.png", dpi=300)
    with Image.open(path) as reopened:
        assert reopened.info["dpi"] == pytest.approx((300, 300), abs=0.01)


def test_save_png_creates_missing_directories(tmp_path):
    _front, back, _params = panels()
    assert save_png(back, tmp_path / "a" / "b" / "c.png").exists()


def wrap_with_geometry():
    front, back, params = panels()
    spine = inches_to_pixels(spine_width_inches(PAGES, "white"), DPI)
    wrap = build_wrap(front, back, spine, params.bleed)
    geometry = WrapGeometry(
        panel_width=params.width,
        panel_height=params.height,
        bleed=params.bleed,
        spine=spine,
        title_band=params.title_band,
        dpi=DPI,
    )
    return wrap, geometry


def test_guides_mark_up_without_resizing():
    wrap, geometry = wrap_with_geometry()
    guides = annotate_wrap(wrap, geometry)
    assert guides.size == wrap.size

    colors = {color for _count, color in guides.getcolors(1 << 24)}
    for guide in (GUIDE_TRIM, GUIDE_SPINE, GUIDE_SAFE):
        assert guide in colors


def test_guides_do_not_touch_the_wrap_itself():
    wrap, geometry = wrap_with_geometry()
    before = wrap.tobytes()
    annotate_wrap(wrap, geometry)
    assert wrap.tobytes() == before
