"""Colour roles, and how a cover's settings resolve to concrete RGB.

Phase 10. Before this module, `render.py` reasoned about the strings "white",
"dark" and "bg" at the moment of drawing. It now receives a `Palette` of resolved
RGB and does no colour reasoning at all -- which is the whole point: phases 11-13
add borders, per-shape tile colours and Wada schemes by teaching *this* module new
ways to fill a Palette, without touching the drawing code again.

The settings stay flat on CoverSpec rather than nesting into a scheme object, so
config JSON stays flat and hand-editable and breed.py's gene registry keeps
addressing plain field names.
"""

import itertools
import math
from dataclasses import dataclass, replace
from functools import lru_cache

from shatter.wada import WadaCombination
from shatter import wada

RGB = tuple[int, int, int]

WHITE: RGB = (255, 255, 255)
BLACK: RGB = (0, 0, 0)

#: How much darker "dark" is than the background. Squared for the auto overlap
#: colour under dark tiles, so a shard reads as one more step down.
DARKEN_FACTOR = 0.7

NAMED_COLORS = ("white", "dark", "bg")

#: Tile outline styles (phase 11). Deliberately not the three names above: a
#: border exists to separate a tile from its neighbours, so it is drawn in an
#: absolute colour rather than one derived from the background.
BORDER_STYLES = ("none", "black", "white")

#: How many colours the tiles take (phase 12). "by_type" colours each prototile
#: shape separately -- the engine tags every tile, and every family has exactly
#: two tags, so this always means two colours.
TILE_SPLITS = ("single", "by_type")


def parse_hex(value: str) -> RGB:
    text = value.lstrip("#")
    if len(text) != 6:
        raise ValueError(f"Expected a #RRGGBB colour, got {value!r}")
    return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))


def darken(rgb: RGB, factor: float = DARKEN_FACTOR) -> RGB:
    return tuple(round(channel * factor) for channel in rgb)


def blend(a: RGB, b: RGB, t: float) -> RGB:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def resolve_color(name: str, bg: RGB) -> RGB:
    """One of the three classic-mode names, against a background."""
    if name == "white":
        return WHITE
    if name == "dark":
        return darken(bg)
    if name == "bg":
        return bg
    raise ValueError(f"Expected 'white', 'dark' or 'bg', got {name!r}")


@dataclass(frozen=True)
class Palette:
    """Every colour the renderer needs, already resolved to RGB.

    Six roles, because that is what the planned modes between them require. Two
    are carried but not yet drawn:

    - `tile_b` is the second prototile's fill, used when `tile_split="by_type"`.
      When tiles are not split by shape it simply equals `tile_a`, so a renderer
      that ignores the split still gets a consistent answer.
    - `border` is the tile outline. `None` means borderless.

    `overlap` is `None` when overlap colouring is off -- that is what turns
    section 8's `overlap_color="none"` into a plain flag the renderer can branch
    on without parsing a string.
    """

    background: RGB
    box: RGB
    tile_a: RGB
    tile_b: RGB
    border: RGB | None
    overlap: RGB | None


def classic_overlap(overlap_color: str, tile_color: str, bg: RGB) -> RGB | None:
    """Colour for pixels covered by two or more tiles.

    "auto" means one step darker than the tile, but the step differs by tile
    colour: darkening twice works for dark tiles, while white multiplied by white
    is still white, so white tiles instead move halfway to the pastel.
    """
    if overlap_color == "none":
        return None
    if overlap_color != "auto":
        return parse_hex(overlap_color)
    if tile_color == "white":
        return blend(WHITE, bg, 0.5)
    if tile_color == "dark":
        return darken(bg, DARKEN_FACTOR**2)
    # tile_color == "bg": undocumented in section 8, but longstanding, so it is
    # preserved deliberately rather than tidied into one of the cases above.
    return darken(bg)


def resolve_border(style: str) -> RGB | None:
    """Tile outline colour, or None for borderless.

    Independent of the colour mode: a Wada scheme gets its borders the same way
    classic mode does, which is why this is applied over a finished palette
    rather than passed into each mode's resolver.
    """
    if style == "none":
        return None
    if style == "black":
        return BLACK
    if style == "white":
        return WHITE
    raise ValueError(
        f"Unknown border style {style!r}. Choose from: {', '.join(BORDER_STYLES)}"
    )


def classic_palette(
    bg: str,
    tile_color: str,
    box_color: str,
    overlap_color: str,
    tile_color_b: str | None = None,
) -> Palette:
    """The original three-value scheme (section 8).

    `tile_color_b` is the second prototile's fill; None means the tiles are not
    split by shape and both roles take `tile_color`.

    The "auto" overlap colour follows `tile_color` even when the tiles are split.
    One overlap colour covers every kind of overlap (section 12.1, decision 3), so
    it has to follow one of the two, and following the first keeps a split cover's
    overlaps identical to the unsplit one it was bred from.
    """
    background = parse_hex(bg)
    tile = resolve_color(tile_color, background)
    return Palette(
        background=background,
        box=resolve_color(box_color, background),
        tile_a=tile,
        tile_b=tile if tile_color_b is None else resolve_color(tile_color_b, background),
        border=None,
        overlap=classic_overlap(overlap_color, tile_color, background),
    )


# --------------------------------------------------------------------------
# Phase 13: the Sanzo Wada colour mode.
# --------------------------------------------------------------------------

Lab = tuple[float, float, float]

#: sRGB -> CIE XYZ (D65) -> L*a*b*. Written out rather than pulled from a colour
#: library: it is a dozen lines, and section 3 keeps Pillow as the only runtime
#: dependency.
D65_WHITE = (0.95047, 1.00000, 1.08883)


@lru_cache(maxsize=1024)
def srgb_to_lab(rgb: RGB) -> Lab:
    """Perceptual coordinates for a colour that is about to be rendered.

    Note what this does *not* do: read the `lab` field the Wada dataset ships.
    Upstream derived that from the CMYK values while re-converting the RGB
    separately, so the two disagree by up to 20 dE, and at a floor of 25 that
    flips six pairs -- nearly all of them in the dangerous direction, passing a
    pair that renders almost identically. Section 12.1, decision 13.
    """

    def linear(channel: int) -> float:
        u = channel / 255
        return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(channel) for channel in rgb)
    xyz = (
        0.4124 * r + 0.3576 * g + 0.1805 * b,
        0.2126 * r + 0.7152 * g + 0.0722 * b,
        0.0193 * r + 0.1192 * g + 0.9505 * b,
    )

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (841 / 108) * t + 4 / 29

    fx, fy, fz = (f(value / white) for value, white in zip(xyz, D65_WHITE))
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def lightness(rgb: RGB) -> float:
    """L* alone -- what the default role assignment sorts on."""
    return srgb_to_lab(rgb)[0]


def delta_e(a: RGB, b: RGB) -> float:
    """CIE76: Euclidean distance in L*a*b*.

    Deliberately not CIEDE2000. The floor asks a coarse "are these two visibly
    different" question against hand-set constants, and CIE76's known weakness is
    that it *under*-states the difference between saturated hues -- so it errs
    toward rejecting a usable combination rather than shipping an invisible one.
    """
    return math.dist(srgb_to_lab(a), srgb_to_lab(b))


#: Which roles each layout fills, **in lightness order, lightest first**. This
#: ordering is the whole of `role_permutation = 0` (section 12.1, decision 10):
#: the box takes the lightest colour because that is what the classic default
#: does -- measured at box L*=100 over a background at 89.0 over tiles at 64.5 --
#: so a Wada cover starts from the house look and permutes away from it.
#:
#: `shapes` looks like an exception and is not one: its box is deliberately
#: invisible, so the background genuinely is the lightest thing on the cover.
ROLE_LAYOUTS: dict[str, tuple[str, ...]] = {
    "box": ("box", "background", "tile_a"),
    "shapes": ("background", "tile_a", "tile_b"),
    "full": ("box", "background", "tile_a", "tile_b"),
}

#: The combination a `wada` cover starts from when none is chosen. Ivory Buff /
#: Yellow Ocher / Deep Lyons Blue: a three-colour combination that passes the
#: floor at permutation 0 with a wide lightness spread (box 85, background 76,
#: tiles 29), so the medallion reads clearly and the debris stays visible against
#: the ground. A restrained, recognisably Wada pairing rather than the loudest
#: one available -- but it is a bolder ground than classic's pastel, which is the
#: point of opting into the mode (decision 2). Changing it moves only the
#: starting point; every other combination is a flag away.
DEFAULT_WADA_COMBINATION = 126

#: The layout decides whether the tiles are split by shape, because that is what
#: having a `tile_b` role *means* (section 12's table). So `tile_split` is a
#: classic-mode field and is ignored in `wada` mode -- see `effective_tile_split`.
LAYOUT_SPLITS: dict[str, str] = {"box": "single", "shapes": "by_type", "full": "by_type"}

#: Minimum perceptual distance between two roles' colours (section 12.1,
#: decision 11). Two-tier, and that is what makes reshuffling meaningful at all:
#: under a single floor the pairwise distances do not change when roles are
#: permuted, so no permutation could ever rescue a combination.
#:
#: Two adjacent tiles from the same patch sitting close together read as texture;
#: a close tile/box or tile/background pair reads as a broken render. Starting
#: values, to be confirmed by eye once there are covers to look at.
STRICT_FLOOR = 25.0
TILE_PAIR_FLOOR = 12.0

#: How far "auto" moves the overlap colour from the tile toward the box, in
#: `wada` mode. Replaces classic mode's branch on `tile_color == "white"`, which
#: is meaningless once a tile is an arbitrary RGB.
#:
#: Note this does *not* inherit a guarantee from the contrast floor: an RGB
#: midpoint is not a Lab midpoint. The separation is a measured property instead
#: -- 10.7 dE at worst across every offered assignment, median ~30, against a
#: just-noticeable difference of about 2.3 -- and `test_wada.py` pins it.
WADA_OVERLAP_BLEND = 0.5


def roles_for_layout(role_layout: str) -> tuple[str, ...]:
    try:
        return ROLE_LAYOUTS[role_layout]
    except KeyError:
        raise ValueError(
            f"Unknown role layout {role_layout!r}. "
            f"Choose from: {', '.join(ROLE_LAYOUTS)}"
        ) from None


@lru_cache(maxsize=8)
def _orderings(count: int) -> tuple[tuple[int, ...], ...]:
    """Every ordering of `count` items, identity first.

    Identity first is load-bearing: it is what makes `role_permutation = 0` the
    house look. `itertools.permutations` guarantees it for a sorted input.
    """
    return tuple(itertools.permutations(range(count)))


def permutation_count(role_layout: str) -> int:
    return len(_orderings(len(roles_for_layout(role_layout))))


def assign_roles(
    combination: WadaCombination, role_layout: str, role_permutation: int = 0
) -> dict[str, RGB]:
    """Give each role in the layout one of the combination's colours.

    The colours are sorted lightest-first and handed to the layout's roles in
    order, which is permutation 0; `role_permutation` selects a different
    ordering. It indexes **all** k! orderings and is taken modulo k! rather than
    being rejected -- the floor filters what the mode *offers*, never what a
    config can express, so that changing a floor constant can never alter what an
    already-saved config renders (section 12.1, decision 12).
    """
    roles = roles_for_layout(role_layout)
    if combination.size != len(roles):
        raise ValueError(
            f"Wada combination {combination.id} has {combination.size} colours, "
            f"but role layout {role_layout!r} needs {len(roles)}"
        )
    ordered = sorted(combination.colors, key=lambda color: -lightness(color.rgb))
    order = _orderings(len(roles))[role_permutation % len(_orderings(len(roles)))]
    return {role: ordered[index].rgb for role, index in zip(roles, order)}


def role_floor(role_a: str, role_b: str) -> float:
    if {role_a, role_b} == {"tile_a", "tile_b"}:
        return TILE_PAIR_FLOOR
    return STRICT_FLOOR


def contrast_failures(assignment: dict[str, RGB]) -> list[tuple[str, str, float, float]]:
    """(role, role, distance, floor) for every pair that is too close.

    Only the roles the layout actually declares are compared. That matters: a
    `box` layout copies `tile_a` into `tile_b`, and comparing a colour with
    itself would fail every time.
    """
    return [
        (role_a, role_b, distance, floor)
        for (role_a, rgb_a), (role_b, rgb_b) in itertools.combinations(
            assignment.items(), 2
        )
        if (distance := delta_e(rgb_a, rgb_b)) < (floor := role_floor(role_a, role_b))
    ]


def passes_contrast_floor(assignment: dict[str, RGB]) -> bool:
    return not contrast_failures(assignment)


@lru_cache(maxsize=8)
def offered(role_layout: str) -> tuple[tuple[int, int], ...]:
    """Every (combination id, permutation) this layout may offer.

    This is the filter decision 12 puts at *selection* time: it is what the
    breeder picks from (phase 14) and what "every combination the mode offers
    passes the contrast floor" means. Rendering an assignment that is not in here
    still works, because a hand-written config is the expert path (section 11.1)
    and silently rendering something other than what it says would be worse.
    """
    roles = roles_for_layout(role_layout)
    return tuple(
        (combination.id, permutation)
        for combination in wada.combinations_of_size(len(roles))
        for permutation in range(permutation_count(role_layout))
        if passes_contrast_floor(assign_roles(combination, role_layout, permutation))
    )


def effective_tile_split(mode: str, role_layout: str, tile_split: str) -> str:
    """The split the renderer should actually use.

    In `wada` mode the layout decides it (`LAYOUT_SPLITS`), because a layout with
    a `tile_b` role exists precisely to colour the two prototiles differently.
    In `classic` mode the field is returned untouched, so nothing about phases
    11-12 changes.
    """
    if mode != "wada":
        return tile_split
    return LAYOUT_SPLITS[role_layout]


def wada_overlap(overlap_color: str, tile_a: RGB, box: RGB) -> RGB | None:
    if overlap_color == "none":
        return None
    if overlap_color != "auto":
        return parse_hex(overlap_color)
    return blend(tile_a, box, WADA_OVERLAP_BLEND)


def wada_palette(
    wada_combination: int,
    role_layout: str,
    role_permutation: int,
    overlap_color: str,
) -> Palette:
    """A palette drawn from one of Wada's 348 combinations.

    Two roles are filled by implication rather than by a colour of their own:
    `shapes` leaves the box invisible by painting it the background (section 12's
    table, and the same first-class look classic mode gets from
    `box_color="bg"`), and `box` has no second tile colour, so `tile_b` repeats
    `tile_a` exactly as it does for an unsplit classic cover.
    """
    combination = wada.combination_by_id(wada_combination)
    roles = assign_roles(combination, role_layout, role_permutation)

    background = roles["background"]
    box = roles.get("box", background)
    tile_a = roles["tile_a"]
    return Palette(
        background=background,
        box=box,
        tile_a=tile_a,
        tile_b=roles.get("tile_b", tile_a),
        border=None,
        overlap=wada_overlap(overlap_color, tile_a, box),
    )


MODES = ("classic", "wada")


def resolve_palette(params) -> Palette:
    """Dispatch on the colour mode. `params` is anything with the flat fields --
    a RenderParams today, and nothing else needs to know."""
    if params.tile_split not in TILE_SPLITS:
        raise ValueError(
            f"Unknown tile split {params.tile_split!r}. "
            f"Choose from: {', '.join(TILE_SPLITS)}"
        )

    if params.mode == "classic":
        split = params.tile_color_b if params.tile_split == "by_type" else None
        palette = classic_palette(
            params.bg,
            params.tile_color,
            params.box_color,
            params.overlap_color,
            split,
        )
    elif params.mode == "wada":
        palette = wada_palette(
            params.wada_combination,
            params.role_layout,
            params.role_permutation,
            params.overlap_color,
        )
    else:
        raise ValueError(
            f"Unknown colour mode {params.mode!r}. Choose from: {', '.join(MODES)}"
        )
    return replace(palette, border=resolve_border(params.border))
