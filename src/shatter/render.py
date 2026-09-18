"""Layout -> front panel image.

The one renderer both producers feed (section 4 of the design doc). Edits are
applied in patch units and only then mapped to pixels, so a layout renders the
same at any DPI.

Since phase 10 this module does no colour reasoning: it asks color.py for a
resolved Palette and draws with it. The colour *settings* still arrive on
RenderParams, because they are what the CLI and the config file carry.
"""

import math
import statistics
from collections.abc import Callable
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageDraw, ImageFont

from covers.tiling.base import Polygon
from shatter.color import (
    DEFAULT_WADA_COMBINATION,
    RGB,
    Palette,
    resolve_palette,
)
from shatter.geometry import (
    BoundingBox,
    Point,
    bounding_box,
    inset_about_centroid,
    prototile_types,
    rotate_about_centroid,
    translate,
    whole_tiles,
)
from shatter.model import ShatterLayout

Shape = list[Point]

LABEL_COLOR = (204, 20, 60)


@dataclass
class RenderParams:
    """Presentation, as opposed to the arrangement held in a ShatterLayout."""

    width: int  # trim width in pixels, excluding bleed
    height: int
    bleed: int = 0  # pixels added to every side of the canvas
    mode: str = "classic"  # which colour model reads the fields below
    bg: str = "#F2D9E6"
    tile_color: str = "dark"
    box_color: str = "white"
    overlap_color: str = "auto"  # "auto" | "none" | "#RRGGBB"
    border: str = "none"  # "none" | "black" | "white"
    border_width: float = 0.12  # fraction of the median tile radius, NOT pixels
    box_corner: float = 0.0  # corner radius as a fraction of the box's shorter side
    clip_tiles: bool = False  # cut the tiles off at the box edge (phase 17)
    tile_split: str = "single"  # "single" | "by_type" (colour by prototile shape)
    tile_color_b: str = "bg"  # second prototile's fill; only read when by_type
    # Read only when mode="wada" (phase 13). `tile_split` above is a classic-mode
    # field: in wada mode the role layout decides the split, and CoverSpec has
    # already resolved it through color.effective_tile_split by the time it gets here.
    wada_combination: int = DEFAULT_WADA_COMBINATION
    role_layout: str = "box"  # "box" | "shapes" | "full"
    role_permutation: int = 0
    tile_gap: float = 0.08
    box_margin: float = 0.15
    title_band: float = 0.30
    side_margin: float = 0.10
    bottom_margin: float = 0.10
    supersample: int = 2


def canvas_size(params: RenderParams, scale: int = 1) -> tuple[int, int]:
    return (
        (params.width + 2 * params.bleed) * scale,
        (params.height + 2 * params.bleed) * scale,
    )


def box_rect(params: RenderParams, scale: int = 1) -> BoundingBox:
    """The feature box, in pixels, as fractions of the TRIM rect (section 8).

    Offset by the bleed so the composition is measured from the trimmed edge --
    what the reader actually sees -- not from the oversized canvas.
    """
    width, height = params.width * scale, params.height * scale
    bleed = params.bleed * scale
    return (
        bleed + params.side_margin * width,
        bleed + params.title_band * height,
        bleed + width - params.side_margin * width,
        bleed + height - params.bottom_margin * height,
    )


def box_corner_px(params: "RenderParams", scale: int = 1) -> float:
    """The feature box's corner radius in pixels, from the fraction on the spec.

    A fraction of the box's **shorter side** rather than a pixel count, for the
    same reason `tile_gap` and the margins are fractions (section 8): a chooser
    thumbnail and a 300dpi print have to describe the same shape, and a radius in
    pixels would be a different corner on each.

    At 0.5 the short ends are semicircles and the box is a stadium. Pillow
    saturates quietly above that rather than failing -- 0.5, 0.6 and 1.0 all draw
    the same shape -- so the clamp is applied here, where it can be documented,
    instead of being left as an accident of the drawing library.
    """
    x0, y0, x1, y1 = box_rect(params, scale)
    return min(max(params.box_corner, 0.0), 0.5) * min(x1 - x0, y1 - y0)


def draw_box(
    image: Image.Image, params: "RenderParams", color: RGB, scale: int = 1
) -> None:
    """Paint the feature box, square or rounded (phase 15).

    Radius 0 deliberately takes the old `rectangle` path rather than calling
    `rounded_rectangle(radius=0)`. The two ought to agree, but "ought to" is not
    what the golden suite tests: this way every cover that does not ask for a
    rounded corner is drawn by exactly the code that drew it before phase 15.
    """
    draw = ImageDraw.Draw(image)
    rect = box_rect(params, scale)
    radius = box_corner_px(params, scale)
    if radius <= 0:
        draw.rectangle(rect, fill=color)
    else:
        draw.rounded_rectangle(rect, radius=radius, fill=color)


def box_mask(params: "RenderParams", size: tuple[int, int], scale: int = 1) -> Image.Image:
    """An L-mode mask that is white inside the feature box and black outside.

    Drawn from the same rect and radius as `draw_box`, so a clipped cover cuts
    exactly where its box is painted -- including when the corners are rounded
    (phase 15), which is the whole reason the two compose for free.
    """
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    rect = box_rect(params, scale)
    radius = box_corner_px(params, scale)
    if radius <= 0:
        draw.rectangle(rect, fill=255)
    else:
        draw.rounded_rectangle(rect, radius=radius, fill=255)
    return mask


def fit_to_box(
    patch: BoundingBox, box: BoundingBox, margin: float
) -> Callable[[Point], Point]:
    """Uniform scale + translate putting the patch inside the box with margin.

    A **negative** margin is legal and is how the solid look is reached (phase
    17): the patch scales past the box edge instead of stopping short of it, and
    `clip_tiles` then cuts it off there. The arithmetic is unchanged -- `1 - 2m`
    simply grows above 1 -- which is why this needed no second knob (decision 25).

    Flips the y axis: patches use maths convention (y up), images don't.
    """
    px0, py0, px1, py1 = patch
    bx0, by0, bx1, by1 = box
    scale = min(
        (bx1 - bx0) * (1 - 2 * margin) / (px1 - px0),
        (by1 - by0) * (1 - 2 * margin) / (py1 - py0),
    )
    patch_cx, patch_cy = (px0 + px1) / 2, (py0 + py1) / 2
    box_cx, box_cy = (bx0 + bx1) / 2, (by0 + by1) / 2

    def transform(point: Point) -> Point:
        x, y = point
        return (box_cx + (x - patch_cx) * scale, box_cy - (y - patch_cy) * scale)

    return transform


def placed_tiles(
    layout: ShatterLayout, tiles: list[Polygon], tile_gap: float
) -> list[tuple[int, Polygon]]:
    """Apply each tile's edit, in patch units.

    Returns (index, polygon) pairs: hidden tiles are dropped, so position in the
    result is not the tile's identity -- the index into `edits` is.
    """
    if len(layout.edits) != len(tiles):
        raise ValueError(
            f"Layout has {len(layout.edits)} edits but "
            f"{layout.family} depth {layout.depth} "
            f"(drop_partial_tiles={layout.drop_partial_tiles}) has {len(tiles)} "
            "tiles. The layout was built for a different patch."
        )
    placed = []
    for index, (tile, edit) in enumerate(zip(tiles, layout.edits)):
        if edit.hidden:
            continue
        shape = inset_about_centroid(tile, tile_gap)
        shape = rotate_about_centroid(shape, edit.rot)
        placed.append((index, translate(shape, edit.dx, edit.dy)))
    return placed


@dataclass(frozen=True)
class PlacedTile:
    """A tile ready to draw: where it ended up, and what shape it started as."""

    index: int  # position in layout.edits -- the handle section 11 edits by
    tile_type: str  # prototile tag; what tile_split="by_type" colours on
    points: Shape


def placed_shapes(
    layout: ShatterLayout, params: "RenderParams", scale: int = 1
) -> list[PlacedTile]:
    """Visible tiles in pixel space at the requested scale."""
    tiles = whole_tiles(layout.family, layout.depth, layout.drop_partial_tiles)
    # Fit from the UNEDITED patch, so raising max_push shrinks nothing.
    transform = fit_to_box(
        bounding_box(tiles), box_rect(params, scale), params.box_margin
    )
    return [
        PlacedTile(
            index=index,
            tile_type=polygon.tile_type,
            points=[transform(point) for point in polygon.points],
        )
        for index, polygon in placed_tiles(layout, tiles, params.tile_gap)
    ]


def coverage_map(shapes: list[Shape], size: tuple[int, int]) -> Image.Image:
    """How many tiles cover each pixel, saturating at 255.

    Accumulated inside each tile's own bounding box rather than over the whole
    canvas, so the cost tracks total tile area instead of tiles x canvas.
    """
    coverage = Image.new("L", size, 0)
    for points in shapes:
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        x0, y0 = max(0, math.floor(min(xs))), max(0, math.floor(min(ys)))
        x1 = min(size[0], math.ceil(max(xs)) + 1)
        y1 = min(size[1], math.ceil(max(ys)) + 1)
        if x1 <= x0 or y1 <= y0:
            continue

        tile = Image.new("L", (x1 - x0, y1 - y0), 0)
        ImageDraw.Draw(tile).polygon([(x - x0, y - y0) for x, y in points], fill=1)
        box = (x0, y0, x1, y1)
        coverage.paste(ImageChops.add(coverage.crop(box), tile), box)
    return coverage


def at_least(coverage: Image.Image, count: int) -> Image.Image:
    """Mask of pixels covered by `count` or more tiles."""
    return coverage.point(lambda value: 255 if value >= count else 0)


def median_tile_radius(shapes: list[Shape]) -> float:
    """Typical tile size in pixels: the median over tiles of each tile's mean
    distance from its own centroid to its vertices.

    Median across tiles because the shatter's outermost debris is no guide to the
    core, and mean within a tile because a rhombus's half-diagonals differ wildly
    and the long one says nothing about how thick the tile is.
    """
    radii = []
    for points in shapes:
        cx = sum(x for x, _ in points) / len(points)
        cy = sum(y for _, y in points) / len(points)
        radii.append(
            sum(math.hypot(x - cx, y - cy) for x, y in points) / len(points)
        )
    return statistics.median(radii) if radii else 0.0


def border_width_px(shapes: list[Shape], params: RenderParams) -> int:
    """Border width in pixels at whatever scale `shapes` are already in.

    Taken as a fraction of tile size rather than an absolute width, because the
    same layout is drawn at 170px wide in the chooser and 1800px wide for print.
    A fixed pixel width would vanish in the thumbnail and hairline the print, and
    the chooser would stop being an honest preview of what it prints (section
    11.2). At least 1px, or a border set deliberately would silently not appear.
    """
    return max(1, round(params.border_width * median_tile_radius(shapes)))


def draw_borders(
    image: Image.Image, shapes: list[Shape], color: RGB, width: int
) -> None:
    """Outline every tile, over the fills.

    Pillow strokes a polygon outline *inside* the shape, which is what makes this
    safe: the border eats into the tile's own fill rather than into the gap
    between tiles, so `tile_gap` keeps meaning what section 8 says it means
    however heavy the border gets. Measured at a 5px width: this takes **0%** of
    its pixels from the gap, where stroking the same path centred with
    `ImageDraw.line` takes 43.5%.

    The exception is `width == 1`, where a single-pixel path has no inside to be
    on and straddles the boundary, costing the gap about 15% of the border. That
    only arises on small thumbnails, where the gap is a pixel or two anyway.
    """
    draw = ImageDraw.Draw(image)
    for points in shapes:
        draw.polygon(points, outline=color, width=width)


def render_back(params: RenderParams) -> Image.Image:
    """Plain pastel, nothing else (section 8)."""
    return Image.new("RGB", canvas_size(params), resolve_palette(params).background)


Group = tuple[RGB, list[Shape]]


def fill_groups(
    placed: list[PlacedTile], palette: Palette, params: RenderParams, family: str
) -> list[Group]:
    """Bucket the tiles by the colour they take.

    `single` is one bucket; `by_type` is one per prototile shape, lined up against
    the family's declared `tile_types` order -- first tag takes `tile_a`, the rest
    `tile_b`. Every family has exactly two tags, so "the rest" is one bucket, and
    the fallback only matters if a future family declares more.
    """
    if params.tile_split == "single":
        return [(palette.tile_a, [tile.points for tile in placed])]
    if params.tile_split != "by_type":
        raise ValueError(
            f"Unknown tile split {params.tile_split!r}. Choose from: single, by_type"
        )

    first = prototile_types(family)[0]
    groups: dict[RGB, list[Shape]] = {palette.tile_a: [], palette.tile_b: []}
    for tile in placed:
        color = palette.tile_a if tile.tile_type == first else palette.tile_b
        groups[color].append(tile.points)
    return [(color, shapes) for color, shapes in groups.items() if shapes]


def draw_tiles(
    image: Image.Image, groups: list[Group], palette: Palette, size: tuple[int, int]
) -> None:
    """Fill the tiles, and the places where they pile up.

    Two paths, and the difference is visible: a flat fill paints each tile in
    turn, while overlap colouring counts coverage first so a shard's second layer
    can take its own colour (section 8). `palette.overlap is None` is the switch.

    With overlap colouring on, the result does not depend on the order the groups
    are painted in: any pixel two groups both cover has total coverage >= 2, so it
    is overpainted with the overlap colour regardless of who got there first.
    With overlap colouring off there is no third colour to reach for, and opaque
    tiles must simply stack -- `tile_a`'s group is painted first, so `tile_b` wins
    a shared pixel. That is what "opaque" means, and it is deterministic.
    """
    if palette.overlap is None:
        draw = ImageDraw.Draw(image)
        for color, shapes in groups:
            for points in shapes:
                draw.polygon(points, fill=color)
        return

    region = (0, 0, size[0], size[1])
    total = Image.new("L", size, 0)
    for color, shapes in groups:
        coverage = coverage_map(shapes, size)
        image.paste(color, region, at_least(coverage, 1))
        total = ImageChops.add(total, coverage)
    image.paste(palette.overlap, region, at_least(total, 2))


def render_front(layout: ShatterLayout, params: RenderParams) -> Image.Image:
    scale = params.supersample
    palette = resolve_palette(params)
    size = canvas_size(params, scale)

    image = Image.new("RGB", size, palette.background)
    draw_box(image, params, palette.box, scale)

    placed = placed_shapes(layout, params, scale)
    shapes = [tile.points for tile in placed]

    # With clipping on, the tiles go onto their own copy of the canvas and are
    # composited back through the box mask. Doing it with one mask at the end,
    # rather than clipping each pass, is what keeps the fills, the overlap
    # composite and the borders cut at exactly the same edge.
    target = image.copy() if params.clip_tiles else image
    draw_tiles(target, fill_groups(placed, palette, params, layout.family), palette, size)
    if palette.border is not None:
        draw_borders(target, shapes, palette.border, border_width_px(shapes, params))
    if params.clip_tiles:
        image.paste(target, (0, 0), box_mask(params, size, scale))

    if scale > 1:
        image = image.resize(canvas_size(params), Image.LANCZOS)
    return image


def draw_tile_labels(
    image: Image.Image, layout: ShatterLayout, params: RenderParams
) -> Image.Image:
    """A reference copy with each visible tile's index drawn on it.

    The index is the tile's position in `layout.edits`, which is exactly what you
    edit by hand (section 11). Never a print output.
    """
    labelled = image.convert("RGB")
    draw = ImageDraw.Draw(labelled)
    font = ImageFont.load_default(size=max(9, round(labelled.width / 90)))

    for tile in placed_shapes(layout, params):
        cx = sum(x for x, _ in tile.points) / len(tile.points)
        cy = sum(y for _, y in tile.points) / len(tile.points)
        draw.text((cx, cy), str(tile.index), font=font, fill=LABEL_COLOR, anchor="mm")
    return labelled
