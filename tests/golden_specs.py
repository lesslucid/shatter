"""The specs the golden-image guard renders (phase 10).

Kept apart from the test so the regeneration script and the test cannot drift
onto different inputs.

Chosen to exercise every branch the colour code currently has, not to look nice:
all six legal tile/box pairs, all three overlap modes, all three families, and --
the one that is easy to miss -- a high-jitter spec. Overlaps cover only ~0.1% of
pixels at the default knobs (section 8), so without that case a golden suite can
pass while the overlap path is quietly broken.
"""

from shatter.spec import CoverSpec

#: Small, but not tiny: big enough that the fit transform, the tile gap and the
#: LANCZOS downscale all do real work.
GOLDEN_SIZE = (200, 300)

GOLDEN_SPECS: dict[str, CoverSpec] = {
    "default": CoverSpec(zoom=60),
    "white_on_dark": CoverSpec(zoom=60, tile_color="white", box_color="dark"),
    "dark_on_bg": CoverSpec(zoom=60, tile_color="dark", box_color="bg"),
    "white_on_bg": CoverSpec(zoom=60, tile_color="white", box_color="bg"),
    "bg_on_white": CoverSpec(zoom=60, tile_color="bg", box_color="white"),
    "bg_on_dark": CoverSpec(zoom=60, tile_color="bg", box_color="dark"),
    # The three overlap modes, each on p2 -- measured at ~31% of covered pixels
    # overlapping, against ~0.02% for p3 at the default knobs. Testing the modes
    # on a sparse patch would let the whole second coverage level break silently.
    "overlap_none": CoverSpec(zoom=60, family="p2", overlap_color="none", jitter=0.45),
    "overlap_hex": CoverSpec(zoom=60, family="p2", overlap_color="#102030", jitter=0.45),
    "overlap_auto_dark": CoverSpec(
        zoom=60, family="p2", tile_color="dark", jitter=0.45
    ),
    "overlap_auto_white": CoverSpec(
        zoom=60, family="p2", tile_color="white", box_color="dark", jitter=0.45
    ),
    "family_p2": CoverSpec(zoom=60, family="p2"),
    "family_pinwheel": CoverSpec(zoom=60, family="pinwheel"),
    "deep_pastel": CoverSpec(zoom=60, bg="#E9E4D8", tile_color="white", box_color="dark"),
    "gap_wide": CoverSpec(zoom=60, tile_gap=0.17),
    # Phase 11. "border_over_overlap" is the one that matters: borders are drawn
    # after the coverage composite, so it is the only case where the two passes
    # meet.
    "border_black": CoverSpec(zoom=60, border="black", tile_color="bg"),
    "border_white": CoverSpec(
        zoom=60, border="white", tile_color="dark", box_color="dark"
    ),
    "border_wide": CoverSpec(zoom=60, border="black", border_width=0.25),
    "border_over_overlap": CoverSpec(
        zoom=60, family="p2", border="black", tile_color="bg", jitter=0.45
    ),
    # Phase 12. One per family, because the prototile tags differ by family and
    # the tile_a/tile_b mapping is what must stay stable.
    "split_p3": CoverSpec(
        zoom=60, tile_split="by_type", tile_color="dark", tile_color_b="bg"
    ),
    "split_p2": CoverSpec(
        zoom=60, family="p2", tile_split="by_type",
        tile_color="dark", tile_color_b="white", box_color="bg",
    ),
    "split_pinwheel": CoverSpec(
        zoom=60, family="pinwheel", tile_split="by_type",
        tile_color="dark", tile_color_b="bg",
    ),
    # Both new features at once, over an overlap region: the busiest the renderer
    # gets, and the only case where all three passes meet.
    "split_bordered_overlap": CoverSpec(
        zoom=60, family="p2", tile_split="by_type", border="black",
        tile_color="dark", tile_color_b="white", jitter=0.45,
    ),
    # Phase 13. One per role layout, because each fills the six roles
    # differently: `box` repeats tile_a into tile_b, `shapes` paints the box in
    # the background, and only `full` gives all four a colour of their own.
    # Permutations are pinned explicitly -- a golden that tracked the default
    # ordering would go quietly green if decision 10's ordering were inverted.
    "wada_box": CoverSpec(zoom=60, mode="wada", wada_combination=126),
    "wada_shapes": CoverSpec(
        zoom=60, mode="wada", wada_combination=123, role_layout="shapes"
    ),
    "wada_full": CoverSpec(
        zoom=60, mode="wada", wada_combination=243, role_layout="full"
    ),
    "wada_permuted": CoverSpec(
        zoom=60, mode="wada", wada_combination=126, role_permutation=3
    ),
    # The busiest wada path: a split layout, a border and a real overlap region
    # at once, which is the only place the three drawing passes meet in this mode.
    "wada_bordered_overlap": CoverSpec(
        zoom=60, family="p2", mode="wada", wada_combination=243,
        role_layout="full", border="black", jitter=0.45,
    ),
}


def render_golden(spec: CoverSpec):
    from shatter.render import render_front

    return render_front(spec.build_layout(), spec.render_params(*GOLDEN_SIZE))
