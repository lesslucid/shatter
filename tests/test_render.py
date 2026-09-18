import pytest
from conftest import has_label_pixels
from PIL import Image, ImageChops

from shatter.autoshatter import ShatterParams, auto_shatter
from shatter.geometry import bounding_box, prototile_types, whole_tiles
from shatter.model import ShatterLayout, TileEdit
from shatter.color import parse_hex, resolve_color, resolve_palette
from shatter.render import (
    LABEL_COLOR,
    RenderParams,
    at_least,
    border_width_px,
    box_corner_px,
    box_rect,
    canvas_size,
    draw_box,
    coverage_map,
    draw_tile_labels,
    draw_tiles,
    fill_groups,
    fit_to_box,
    median_tile_radius,
    placed_shapes,
    placed_tiles,
    render_front,
)

BG = "#F2D9E6"


def layout_for(family, depth, **kwargs):
    tiles = whole_tiles(family, depth)
    return ShatterLayout(
        family=family,
        depth=depth,
        drop_partial_tiles=True,
        seed=0,
        edits=[TileEdit(**kwargs) for _ in tiles],
    )


def test_box_rect_follows_the_fractions():
    params = RenderParams(width=1000, height=2000)
    x0, y0, x1, y1 = box_rect(params)
    assert (x0, x1) == (100.0, 900.0)
    assert (y0, y1) == (600.0, 1800.0)


def test_box_rect_scales_with_supersampling():
    params = RenderParams(width=1000, height=2000)
    assert box_rect(params, 2) == tuple(v * 2 for v in box_rect(params))


def test_fit_to_box_centres_and_flips_y():
    transform = fit_to_box((-1.0, -1.0, 1.0, 1.0), (0.0, 0.0, 100.0, 100.0), margin=0.0)
    assert transform((0.0, 0.0)) == pytest.approx((50.0, 50.0))
    # patch y is up, image y is down
    assert transform((0.0, 1.0)) == pytest.approx((50.0, 0.0))
    assert transform((1.0, 0.0)) == pytest.approx((100.0, 50.0))


def test_fit_to_box_margin_shrinks_the_patch():
    transform = fit_to_box((-1.0, -1.0, 1.0, 1.0), (0.0, 0.0, 100.0, 100.0), margin=0.1)
    assert transform((1.0, 0.0)) == pytest.approx((90.0, 50.0))


def test_placed_tiles_rejects_a_layout_built_for_another_patch():
    layout = layout_for("p3", 3)
    layout.depth = 4
    with pytest.raises(ValueError, match="different patch"):
        placed_tiles(layout, whole_tiles("p3", 4), 0.08)


def test_placed_tiles_skips_hidden():
    layout = layout_for("p3", 3, hidden=True)
    assert placed_tiles(layout, whole_tiles("p3", 3), 0.08) == []


def test_placed_tiles_applies_translation_in_patch_units():
    tiles = whole_tiles("p3", 3)
    layout = layout_for("p3", 3, dx=10.0)
    index, moved = placed_tiles(layout, tiles, tile_gap=0.0)[0]
    assert index == 0
    assert moved.points[0][0] == pytest.approx(tiles[0].points[0][0] + 10.0)


def test_placed_tiles_keeps_the_edit_index_after_hidden_tiles():
    """Position in the result is not identity once tiles are dropped."""
    tiles = whole_tiles("p3", 3)
    layout = layout_for("p3", 3)
    layout.edits[0].hidden = True
    layout.edits[1].hidden = True

    placed = placed_tiles(layout, tiles, tile_gap=0.08)
    assert placed[0][0] == 2


SQUARE_A = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
SQUARE_B = [(5.0, 5.0), (15.0, 5.0), (15.0, 15.0), (5.0, 15.0)]


def test_coverage_counts_tiles_per_pixel():
    coverage = coverage_map([SQUARE_A, SQUARE_B], (20, 20))
    assert coverage.getpixel((2, 2)) == 1
    assert coverage.getpixel((7, 7)) == 2
    assert coverage.getpixel((12, 12)) == 1
    assert coverage.getpixel((18, 18)) == 0


def test_coverage_ignores_tiles_off_canvas():
    far_away = [(500.0, 500.0), (510.0, 500.0), (510.0, 510.0)]
    coverage = coverage_map([SQUARE_A, far_away], (20, 20))
    assert coverage.getpixel((2, 2)) == 1


def test_at_least_thresholds_coverage():
    coverage = coverage_map([SQUARE_A, SQUARE_B], (20, 20))
    once, twice = at_least(coverage, 1), at_least(coverage, 2)
    assert (once.getpixel((2, 2)), twice.getpixel((2, 2))) == (255, 0)
    assert (once.getpixel((7, 7)), twice.getpixel((7, 7))) == (255, 255)


def test_overlapping_tiles_render_in_the_overlap_colour():
    layout = auto_shatter("p3", 4, 42, ShatterParams(jitter=0.45))
    params = RenderParams(width=600, height=900, box_color="bg", tile_color="dark")
    image = render_front(layout, params)
    colors = {color for _count, color in image.getcolors(1 << 24)}
    assert resolve_palette(params).overlap in colors


def test_overlap_none_keeps_tiles_flat():
    layout = auto_shatter("p3", 4, 42, ShatterParams(jitter=0.45))
    flat = RenderParams(
        width=600, height=900, box_color="bg", tile_color="dark", overlap_color="none"
    )
    auto = RenderParams(width=600, height=900, box_color="bg", tile_color="dark")

    colors = {color for _count, color in render_front(layout, flat).getcolors(1 << 24)}
    assert resolve_palette(auto).overlap not in colors


def deepest_coverage(tile_gap):
    tiles = whole_tiles("p3", 3)
    layout = ShatterLayout("p3", 3, True, 0, [TileEdit() for _ in tiles])
    params = RenderParams(width=600, height=900, tile_gap=tile_gap)
    shapes = [tile.points for tile in placed_shapes(layout, params)]
    coverage = coverage_map(shapes, canvas_size(params))
    return max(value for value, count in enumerate(coverage.histogram()) if count)


def test_intact_patch_has_no_overlap_at_the_default_gap():
    """The gap separates neighbours, so an unshattered patch is flat colour."""
    assert deepest_coverage(0.08) == 1


def test_zero_gap_makes_neighbours_share_edge_pixels():
    """Known limitation: at tile_gap=0 adjacent tiles double-cover their shared
    edges, so overlap colouring paints seams along every join. Harmless in
    practice because gap 0 renders the core as one solid blob anyway."""
    assert deepest_coverage(0.0) > 1


def test_label_colour_is_unmistakable_against_the_palette():
    red, green, blue = LABEL_COLOR
    assert red > green + 40 and red > blue + 40


def test_labels_are_drawn_without_resizing_or_mutating():
    layout = layout_for("p3", 2)
    params = RenderParams(width=300, height=450)
    image = render_front(layout, params)
    before = image.tobytes()

    labelled = draw_tile_labels(image, layout, params)
    assert labelled.size == image.size
    assert image.tobytes() == before
    assert has_label_pixels(labelled)
    assert not has_label_pixels(image)


def test_hidden_tiles_get_no_label():
    """Labels name what you can see; a hidden tile has nothing to point at."""
    layout = layout_for("p3", 2, hidden=True)
    params = RenderParams(width=300, height=450)
    labelled = draw_tile_labels(render_front(layout, params), layout, params)
    assert not has_label_pixels(labelled)


def test_render_front_produces_the_requested_size():
    layout = layout_for("p3", 2)
    image = render_front(layout, RenderParams(width=300, height=450))
    assert image.size == (300, 450)


def test_render_front_leaves_the_title_band_as_background():
    """Nothing is drawn above the box -- that space is reserved for type.

    Sampled clear of the box edge, where LANCZOS ringing shifts the flat
    background by a single level.
    """
    layout = layout_for("p3", 2)
    params = RenderParams(width=300, height=450, bg=BG)
    image = render_front(layout, params)
    band_bottom = int(params.title_band * params.height)

    for y in (0, band_bottom // 2, band_bottom - 4):
        assert image.getpixel((params.width // 2, y)) == parse_hex(BG)

    band = image.crop((0, 0, params.width, band_bottom))
    tile_rgb = resolve_color(params.tile_color, parse_hex(BG))
    assert tile_rgb not in {color for _count, color in band.getcolors(1 << 24)}


# --- borders (phase 11) -----------------------------------------------------


def bordered(**kwargs):
    from shatter.spec import CoverSpec

    return CoverSpec(zoom=60, seed=42, **kwargs)


def test_median_tile_radius_is_the_typical_tile_size():
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    big = [(0.0, 0.0), (30.0, 0.0), (30.0, 30.0), (0.0, 30.0)]
    # each vertex of a 10-square is sqrt(50) from its centre
    assert median_tile_radius([square]) == pytest.approx(50**0.5)
    assert median_tile_radius([square, square, big]) == pytest.approx(50**0.5)


def test_median_tile_radius_of_nothing_is_zero():
    assert median_tile_radius([]) == 0.0


def test_border_width_is_never_rounded_away():
    """A border asked for and then silently not drawn is the worst outcome."""
    spec = bordered(border="black", border_width=0.0001)
    params = spec.render_params(60, 90)
    shapes = [t.points for t in placed_shapes(spec.build_layout(), params, 1)]
    assert border_width_px(shapes, params) >= 1


def test_border_width_tracks_tile_size_not_canvas_size():
    """The point of the phase: a chooser thumbnail must show the print's border.

    A fixed pixel width would vanish at 170px wide and hairline at 1800px, and the
    chooser would stop being an honest preview of what it prints (section 11.2).
    """
    spec = bordered(border="black", border_width=0.12)
    ratios = []
    for width, height in [(200, 300), (600, 900), (1800, 2700)]:
        params = spec.render_params(width, height)
        shapes = [t.points for t in placed_shapes(spec.build_layout(), params, 2)]
        ratios.append(border_width_px(shapes, params) / median_tile_radius(shapes))

    assert all(r == pytest.approx(0.12, abs=0.03) for r in ratios), ratios


def test_a_border_paints_its_colour():
    spec = bordered(border="black", tile_color="bg")
    image = render_front(spec.build_layout(), spec.render_params(200, 300))
    assert (0, 0, 0) in {color for _count, color in image.getcolors(1 << 24)}


def test_no_border_paints_no_border():
    spec = bordered(border="none", tile_color="bg")
    image = render_front(spec.build_layout(), spec.render_params(200, 300))
    assert (0, 0, 0) not in {color for _count, color in image.getcolors(1 << 24)}


def test_a_border_eats_the_tile_not_the_gap():
    """Section 1 makes the gap load-bearing, so the border must not close it up.

    Measured at supersample 1 so LANCZOS cannot blur the boundary, and at a size
    where the border is several pixels wide -- at width 1 the stroke is a single
    path with no inside to sit on, and it does straddle the edge.
    """
    from shatter.color import resolve_palette

    def box_pixels(border):
        spec = bordered(border=border, tile_color="bg", box_color="white")
        params = spec.render_params(900, 1350, supersample=1)
        image = render_front(spec.build_layout(), params)
        box = resolve_palette(params).box
        return sum(c for c, px in image.getcolors(1 << 24) if px == box)

    assert box_pixels("black") == box_pixels("none")


def test_a_wider_border_covers_more():
    spec_thin = bordered(border="black", border_width=0.06, tile_color="bg")
    spec_wide = bordered(border="black", border_width=0.24, tile_color="bg")

    def black(spec):
        image = render_front(spec.build_layout(), spec.render_params(600, 900))
        return sum(c for c, px in image.getcolors(1 << 24) if px == (0, 0, 0))

    assert black(spec_wide) > black(spec_thin)


# --- two-colour tiles by prototile shape (phase 12) -------------------------


def split_spec(**kwargs):
    from shatter.spec import CoverSpec

    return CoverSpec(zoom=60, seed=42, **kwargs)


def rendered(spec):
    return render_front(spec.build_layout(), spec.render_params(200, 300))


def test_fill_groups_makes_one_bucket_when_tiles_are_not_split():
    spec = split_spec(tile_split="single")
    params = spec.render_params(200, 300)
    placed = placed_shapes(spec.build_layout(), params, 1)
    groups = fill_groups(placed, resolve_palette(params), params, spec.family)

    assert len(groups) == 1
    assert len(groups[0][1]) == len(placed)


def test_fill_groups_splits_on_the_prototile_tag():
    spec = split_spec(tile_split="by_type", tile_color="dark", tile_color_b="white")
    params = spec.render_params(200, 300)
    placed = placed_shapes(spec.build_layout(), params, 1)
    groups = fill_groups(placed, resolve_palette(params), params, spec.family)

    first = prototile_types(spec.family)[0]
    expected = sum(1 for tile in placed if tile.tile_type == first)
    assert len(groups) == 2
    assert len(groups[0][1]) == expected
    assert len(groups[0][1]) + len(groups[1][1]) == len(placed)


def test_the_first_prototile_tag_takes_tile_a():
    """The mapping has to be stable, or a saved cover changes colour on re-render."""
    spec = split_spec(tile_split="by_type", tile_color="dark", tile_color_b="white")
    params = spec.render_params(200, 300)
    palette = resolve_palette(params)
    placed = placed_shapes(spec.build_layout(), params, 1)
    groups = fill_groups(placed, palette, params, spec.family)
    assert groups[0][0] == palette.tile_a
    assert groups[1][0] == palette.tile_b


def test_splitting_into_the_same_colour_twice_changes_nothing():
    """The cleanest statement that the split is opt-in and additive."""
    single = rendered(split_spec(tile_split="single", tile_color="dark"))
    split = rendered(
        split_spec(tile_split="by_type", tile_color="dark", tile_color_b="dark")
    )
    assert single.tobytes() == split.tobytes()


def test_splitting_into_two_colours_changes_the_render():
    single = rendered(split_spec(tile_split="single", tile_color="dark"))
    split = rendered(
        split_spec(tile_split="by_type", tile_color="dark", tile_color_b="white")
    )
    assert single.tobytes() != split.tobytes()


def test_tile_color_b_is_ignored_unless_the_tiles_are_split():
    a = rendered(split_spec(tile_color="dark", tile_color_b="bg"))
    b = rendered(split_spec(tile_color="dark", tile_color_b="white"))
    assert a.tobytes() == b.tobytes()


@pytest.mark.parametrize("family", ["p3", "p2", "pinwheel"])
def test_every_family_splits_into_exactly_two_colours(family):
    """Every family tags its tiles with one of exactly two prototile types, so
    by_type never leaves a bucket empty and never needs a third colour."""
    spec = split_spec(family=family, tile_split="by_type",
                      tile_color="dark", tile_color_b="white")
    params = spec.render_params(200, 300)
    placed = placed_shapes(spec.build_layout(), params, 1)
    groups = fill_groups(placed, resolve_palette(params), params, family)

    assert len(groups) == 2
    assert all(shapes for _color, shapes in groups)
    assert {tile.tile_type for tile in placed} <= set(prototile_types(family))


#: Knobs chosen to make the two prototile groups genuinely collide. The default
#: shatter barely overlaps at all (~0.1% of covered pixels, section 8), and an
#: order-independence test with nothing overlapping passes for the wrong reason.
COLLIDING = dict(
    family="p2", jitter=0.6, max_rotation=90.0, tile_gap=0.02,
    tile_split="by_type", tile_color="dark", tile_color_b="white",
)


def cross_coverage(groups, size):
    """Pixels covered by BOTH groups -- the A-on-B region."""
    a, b = (at_least(coverage_map(shapes, size), 1) for _color, shapes in groups)
    both = ImageChops.multiply(a, b)
    return sum(count for count, value in both.getcolors() if value == 255)


def test_overlap_colouring_does_not_depend_on_group_order():
    """The reason draw_tiles counts coverage instead of painting in turn: a pixel
    two groups both cover reaches count 2 and is overpainted either way."""
    spec = split_spec(**COLLIDING)
    params = spec.render_params(200, 300)
    palette = resolve_palette(params)
    placed = placed_shapes(spec.build_layout(), params, 2)
    size = canvas_size(params, 2)
    groups = fill_groups(placed, palette, params, spec.family)

    assert cross_coverage(groups, size) > 100, "nothing overlaps; test is vacuous"

    def draw(order):
        image = Image.new("RGB", size, palette.background)
        draw_tiles(image, order, palette, size)
        return image.tobytes()

    assert draw(groups) == draw(list(reversed(groups)))


def test_flat_fills_stack_in_a_defined_order():
    """With overlap colouring off there is no third colour to reach for, so opaque
    tiles must stack. Order is then visible -- it just has to be deterministic."""
    spec = split_spec(**{**COLLIDING, "overlap_color": "none"})
    params = spec.render_params(200, 300)
    palette = resolve_palette(params)
    placed = placed_shapes(spec.build_layout(), params, 2)
    size = canvas_size(params, 2)
    groups = fill_groups(placed, palette, params, spec.family)

    def draw(order):
        image = Image.new("RGB", size, palette.background)
        draw_tiles(image, order, palette, size)
        return image.tobytes()

    assert draw(groups) != draw(list(reversed(groups))), "order should matter here"
    assert draw(groups) == draw(groups), "but it must be deterministic"


def test_one_overlap_colour_covers_every_kind_of_overlap():
    """Section 12.1 decision 3: A-on-A, B-on-B and A-on-B all read the same."""
    spec = split_spec(family="p2", tile_split="by_type", jitter=0.45,
                      tile_color="dark", tile_color_b="white")
    params = spec.render_params(400, 600)
    palette = resolve_palette(params)
    colors = {c for _n, c in rendered(spec).getcolors(1 << 24)}
    assert palette.overlap in colors


def test_an_unknown_tile_split_is_rejected_by_name():
    spec = split_spec(tile_split="rainbow")
    with pytest.raises(ValueError, match="Unknown tile split"):
        rendered(spec)


# --- Phase 15: rounded feature-box corners -----------------------------------

CORNER_BG, CORNER_BOX = (0, 0, 0), (255, 255, 255)


def box_corners_and_centre(corner, width=200, height=300, scale=1):
    """Draw just the box on a blank canvas and sample its four corners."""
    params = RenderParams(width=width, height=height, box_corner=corner)
    image = Image.new("RGB", (width * scale, height * scale), CORNER_BG)
    draw_box(image, params, CORNER_BOX, scale)
    x0, y0, x1, y1 = (round(v) for v in box_rect(params, scale))
    corners = [
        image.getpixel(point)
        for point in ((x0 + 1, y0 + 1), (x1 - 2, y0 + 1),
                      (x0 + 1, y1 - 2), (x1 - 2, y1 - 2))
    ]
    return corners, image.getpixel(((x0 + x1) // 2, (y0 + y1) // 2))


def test_a_square_box_fills_its_corners():
    corners, centre = box_corners_and_centre(0.0)
    assert corners == [CORNER_BOX] * 4
    assert centre == CORNER_BOX


@pytest.mark.parametrize("corner", [0.1, 0.25, 0.5])
def test_a_rounded_box_cuts_all_four_corners_away(corner):
    corners, centre = box_corners_and_centre(corner)
    assert corners == [CORNER_BG] * 4, "a corner survived the rounding"
    assert centre == CORNER_BOX, "rounding must not eat the middle of the box"


def test_the_radius_is_a_fraction_of_the_shorter_side():
    params = RenderParams(width=200, height=300, box_corner=0.5)
    x0, y0, x1, y1 = box_rect(params)
    assert box_corner_px(params) == pytest.approx(0.5 * min(x1 - x0, y1 - y0))


def test_the_radius_scales_with_the_output_size():
    """The whole reason it is a fraction: a thumbnail and a print must describe
    the same shape, which a radius in pixels could not do."""
    small = RenderParams(width=150, height=225, box_corner=0.25)
    large = RenderParams(width=600, height=900, box_corner=0.25)
    assert box_corner_px(large) == pytest.approx(4 * box_corner_px(small))


def test_the_radius_scales_with_supersampling():
    params = RenderParams(width=200, height=300, box_corner=0.25)
    assert box_corner_px(params, 2) == pytest.approx(2 * box_corner_px(params))


@pytest.mark.parametrize("corner", [0.5, 0.6, 1.0, 4.0])
def test_the_radius_is_capped_at_a_stadium(corner):
    """Pillow saturates above half the shorter side rather than failing, so the
    cap is applied in `box_corner_px` where it can be documented."""
    params = RenderParams(width=200, height=300, box_corner=corner)
    x0, y0, x1, y1 = box_rect(params)
    assert box_corner_px(params) == pytest.approx(0.5 * min(x1 - x0, y1 - y0))


def test_a_negative_radius_is_treated_as_square():
    assert box_corner_px(RenderParams(width=200, height=300, box_corner=-1.0)) == 0.0
    corners, _ = box_corners_and_centre(-1.0)
    assert corners == [CORNER_BOX] * 4


def test_radius_zero_is_byte_identical_to_the_pre_phase_15_drawing():
    """`draw_box` takes the old `rectangle` path at radius 0 deliberately. This
    is what lets every golden captured before phase 15 stay green."""
    from PIL import ImageDraw

    params = RenderParams(width=200, height=300, box_corner=0.0)
    drawn = Image.new("RGB", (200, 300), CORNER_BG)
    draw_box(drawn, params, CORNER_BOX)

    expected = Image.new("RGB", (200, 300), CORNER_BG)
    ImageDraw.Draw(expected).rectangle(box_rect(params), fill=CORNER_BOX)

    assert drawn.tobytes() == expected.tobytes()


def test_the_corner_reaches_the_renderer_from_the_spec():
    from shatter.spec import CoverSpec

    assert CoverSpec(box_corner=0.3).render_params(10, 20).box_corner == 0.3
    assert CoverSpec().render_params(10, 20).box_corner == 0.0
