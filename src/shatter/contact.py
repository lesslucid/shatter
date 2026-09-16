"""Thumbnails and labelled contact sheets.

The chooser shows these on screen; `shatter contact` writes them to a file. Both
show real renders at small size, so what you pick is what prints.
"""

from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from shatter.render import render_front
from shatter.spec import CoverSpec

SHEET_BG = (250, 250, 250)
LABEL_RGB = (30, 30, 30)
DETAIL_RGB = (120, 120, 120)


@dataclass
class SheetStyle:
    thumb_width: int = 260
    thumb_height: int = 390
    columns: int = 5
    padding: int = 10
    caption: int = 46  # index line, then describe()'s two lines
    supersample: int = 3


def thumbnail(spec: CoverSpec, style: SheetStyle) -> Image.Image:
    params = spec.render_params(
        style.thumb_width, style.thumb_height, supersample=style.supersample
    )
    return render_front(spec.build_layout(), params)


def describe_colour(spec: CoverSpec) -> str:
    """The palette half of a caption, in whichever model the spec is in."""
    if spec.mode == "wada":
        text = (
            f"wada{spec.wada_combination} {spec.role_layout} "
            f"perm{spec.role_permutation}"
        )
    else:
        text = f"{spec.bg} {spec.tile_color}-on-{spec.box_color}"
        if spec.tile_split == "by_type":
            text += f"/{spec.tile_color_b}"
    if spec.border != "none":
        text += f" {spec.border}-border"
    return text


def describe(spec: CoverSpec) -> str:
    """Two lines: what the shatter is doing, then what the colour is doing.

    The colour line is phase 14. Before it, breeding could only move the palette
    between nine classic combinations and the caption never needed to mention it;
    now `wada` mode varies the palette as the main event, and a caption that
    cannot tell two panels apart is worse than no caption at all.
    """
    return (
        f"{spec.family} seed{spec.seed} core{spec.core_fraction:.2f} "
        f"push{spec.max_push:.2f} jit{spec.jitter:.2f}\n"
        f"{describe_colour(spec)}"
    )


def contact_sheet(
    specs: list[CoverSpec], style: SheetStyle | None = None
) -> Image.Image:
    """One labelled panel per spec, in reading order."""
    if not specs:
        raise ValueError("A contact sheet needs at least one spec")

    style = style or SheetStyle()
    columns = min(style.columns, len(specs))
    rows = -(-len(specs) // columns)

    cell_w = style.thumb_width + style.padding
    cell_h = style.thumb_height + style.padding + style.caption
    sheet = Image.new(
        "RGB",
        (columns * cell_w + style.padding, rows * cell_h + style.padding),
        SHEET_BG,
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=13)

    for index, spec in enumerate(specs):
        x = style.padding + (index % columns) * cell_w
        y = style.padding + (index // columns) * cell_h
        sheet.paste(thumbnail(spec, style), (x, y))
        draw.text((x, y + style.thumb_height + 3), f"{index:02d}", font=font, fill=LABEL_RGB)
        draw.multiline_text(
            (x, y + style.thumb_height + 17),
            describe(spec),
            font=font,
            fill=DETAIL_RGB,
            spacing=1,
        )
    return sheet
