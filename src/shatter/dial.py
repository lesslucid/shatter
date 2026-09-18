"""Ordered navigation of the colour space (phase 16).

`Further` finds palettes by surprise, which is what it is for. This module is the
other half: a deterministic walk through every colour a cover could take, so a
half-remembered scheme can be hunted down instead of waited for.

Nothing here consumes a random draw. That is not incidental -- it is why phase 16
could be built without breaking a single saved `--breed-seed`, unlike almost
everything in phases 9-14.

The order is the design problem, not the enumeration; see section 12.1, decisions
20 and 21. In short: one step is one *combination*, because the pairs
`offered()` returns are combination-major and a naive page would show the same
three colours rearranged five times; and the order is the background's hue,
because hunting a colour is a perceptual search and a combination id is
arbitrary.
"""

import colorsys
import math

from shatter import wada
from shatter.breed import PALETTES
from shatter.color import (
    assign_roles,
    offered_by_combination,
    parse_hex,
    srgb_to_lab,
)
from shatter.spec import CoverSpec

RGB = tuple[int, int, int]

#: How many covers a page of the dial shows -- one chooser row.
PAGE = 5


def _hue_key(rgb: RGB) -> tuple[float, float]:
    """Sort key: hue, then the more colourful of a tie first.

    Deliberately no achromatic bucket. An earlier draft grouped near-neutral
    grounds separately, and measurement showed no threshold can tell "a pale
    colour" from "a grey" -- there is nothing there to separate (decision 21).
    Chroma as the tiebreak is enough: a near-neutral lands at the muted end of
    whatever hue it leans towards, which is where you would look for it.
    """
    hue = colorsys.rgb_to_hsv(*[channel / 255 for channel in rgb])[0]
    return (hue, -math.hypot(*srgb_to_lab(rgb)[1:]))


def representative_permutation(role_layout: str, combination: int) -> int:
    """The assignment a combination is shown under on the dial.

    The lowest that passes the contrast floor -- 0 whenever 0 is legal, which is
    the house look (decision 10). Not every combination can take permutation 0,
    so this cannot simply be the constant it looks like it should be.
    """
    return min(offered_by_combination(role_layout)[combination])


def wada_order(role_layout: str) -> tuple[int, ...]:
    """Combination ids for one role layout, in dial order."""
    return tuple(
        sorted(
            offered_by_combination(role_layout),
            key=lambda combination: _hue_key(
                assign_roles(
                    wada.combination_by_id(combination),
                    role_layout,
                    representative_permutation(role_layout, combination),
                )["background"]
            ),
        )
    )


def classic_order() -> tuple[tuple[str, str, str], ...]:
    """The curated classic palettes, in dial order.

    Sorted on the background for the same reason as the Wada side, so the two
    modes behave identically under the same controls even though the spaces they
    walk have nothing in common.
    """
    return tuple(sorted(PALETTES, key=lambda palette: _hue_key(parse_hex(palette[0]))))


def entries(spec: CoverSpec) -> tuple[CoverSpec, ...]:
    """Every colour this cover could take, in dial order.

    Only colour changes: the family, seed, shatter knobs and corners are carried
    through untouched, which is what makes the dial a way of recolouring *this*
    cover rather than a way of browsing covers in general.
    """
    if spec.mode == "wada":
        layout = spec.role_layout
        return tuple(
            spec.with_changes(
                wada_combination=combination,
                role_permutation=representative_permutation(layout, combination),
            )
            for combination in wada_order(layout)
        )
    return tuple(
        spec.with_changes(bg=bg, tile_color=tile, box_color=box)
        for bg, tile, box in classic_order()
    )


def position(spec: CoverSpec) -> int:
    """Where this cover sits on its own dial; 0 if it is not on it at all.

    A hand-written config can name a combination the floor rejects, or a palette
    outside the curated classic set. Those are legal to render (decision 12) and
    simply have no place in the ordering, so the dial starts from the beginning
    rather than refusing.
    """
    if spec.mode == "wada":
        order = wada_order(spec.role_layout)
        target = spec.wada_combination
    else:
        order = classic_order()
        target = (spec.bg, spec.tile_color, spec.box_color)
    try:
        return order.index(target)
    except ValueError:
        return 0


def page_count(spec: CoverSpec, size: int = PAGE) -> int:
    return -(-len(entries(spec)) // size)


def page(spec: CoverSpec, index: int, size: int = PAGE) -> list[CoverSpec]:
    """One page of the dial. The *index* wraps at both ends.

    Wrapping rather than stopping, because hue is a circle: paging past the reds
    at one end should arrive at the reds at the other, not hit a wall.

    The wrap is on the page number, not on the entries. A dial whose last page
    filled itself by repeating the first few covers would show the same cover
    twice in one sweep, which is worse than a short row -- and the window already
    draws a short row as blanks.
    """
    items = entries(spec)
    start = (index % page_count(spec, size)) * size
    return list(items[start : start + size])


def next_permutation(spec: CoverSpec) -> CoverSpec:
    """The next floor-passing role assignment for this cover's combination.

    Decision 22: having found a combination worth keeping, its six or twenty-four
    arrangements are the obvious next question, and reaching them through
    `Further` means waiting for roughly every second row.

    Classic mode has no permutations and a combination the floor rejects has no
    legal ones to cycle; both return the cover unchanged, so the caller can say
    so rather than having to know which case it is in.
    """
    if spec.mode != "wada":
        return spec
    legal = offered_by_combination(spec.role_layout).get(spec.wada_combination)
    if not legal:
        return spec
    order = sorted(legal)
    try:
        nxt = order[(order.index(spec.role_permutation) + 1) % len(order)]
    except ValueError:
        nxt = order[0]
    return spec.with_changes(role_permutation=nxt)
