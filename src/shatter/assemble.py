"""Panels -> the finished wrap. PNG only (section 9)."""

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from shatter.dimensions import (
    BLEED_INCHES,
    DEFAULT_DPI,
    DEFAULT_TRIM,
    Trim,
    inches_to_pixels,
    panel_pixels,
    spine_width_inches,
)
from shatter.model import ShatterLayout
from shatter.render import draw_tile_labels, render_back, render_front
from shatter.spec import CoverSpec

SAFE_MARGIN_INCHES = 0.25

GUIDE_TRIM = (214, 69, 69)
GUIDE_SPINE = (32, 148, 96)
GUIDE_SAFE = (54, 106, 196)


def save_png(image: Image.Image, path: Path, dpi: int = DEFAULT_DPI) -> Path:
    """Write a PNG that declares its own resolution, so whoever opens it next
    places it at true physical size rather than assuming 72 DPI."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG", dpi=(dpi, dpi))
    return path


def build_wrap(
    front: Image.Image, back: Image.Image, spine_px: int, bleed_px: int
) -> Image.Image:
    """Lay out back | spine | front, left to right.

    Each panel arrives with bleed on all four sides; the wrap only wants bleed
    around its outside, so the inner edge of each panel is cropped away and the
    spine fills the gap.
    """
    if front.size != back.size:
        raise ValueError(f"Panel sizes differ: front {front.size}, back {back.size}")

    width, height = front.size
    back_panel = back.crop((0, 0, width - bleed_px, height))
    front_panel = front.crop((bleed_px, 0, width, height))

    spine_color = back.getpixel((0, 0))
    wrap = Image.new(
        "RGB",
        (back_panel.width + spine_px + front_panel.width, height),
        spine_color,
    )
    wrap.paste(back_panel, (0, 0))
    wrap.paste(front_panel, (back_panel.width + spine_px, 0))
    return wrap


@dataclass
class WrapGeometry:
    panel_width: int
    panel_height: int
    bleed: int
    spine: int
    title_band: float
    dpi: int = DEFAULT_DPI


def annotate_wrap(wrap: Image.Image, geometry: WrapGeometry) -> Image.Image:
    """A throwaway reference copy showing where the panels and margins fall.

    The wrap is a flat pastel field with an invisible spine, so whoever sets the
    type cannot otherwise tell the three panels apart. Never a print output.
    """
    guides = wrap.convert("RGB")
    draw = ImageDraw.Draw(guides)

    bleed, spine = geometry.bleed, geometry.spine
    panel_w, panel_h = geometry.panel_width, geometry.panel_height
    safe = round(SAFE_MARGIN_INCHES * geometry.dpi)
    line = max(1, round(geometry.dpi / 150))
    font = ImageFont.load_default(size=max(12, round(geometry.dpi / 7)))

    spine_left = bleed + panel_w
    front_left = spine_left + spine
    trim_right = front_left + panel_w
    trim_bottom = bleed + panel_h

    for x in (bleed, trim_right):
        draw.line([(x, 0), (x, guides.height)], fill=GUIDE_TRIM, width=line)
    for y in (bleed, trim_bottom):
        draw.line([(0, y), (guides.width, y)], fill=GUIDE_TRIM, width=line)

    for x in (spine_left, front_left):
        draw.line([(x, 0), (x, guides.height)], fill=GUIDE_SPINE, width=line)

    for left in (bleed, front_left):
        draw.rectangle(
            [
                (left + safe, bleed + safe),
                (left + panel_w - safe, trim_bottom - safe),
            ],
            outline=GUIDE_SAFE,
            width=line,
        )

    band_bottom = bleed + round(geometry.title_band * panel_h)
    draw.line(
        [(front_left, band_bottom), (trim_right, band_bottom)],
        fill=GUIDE_SAFE,
        width=line,
    )

    pad = round(geometry.dpi / 12)
    size = font.size
    draw.text((bleed + safe + pad, bleed + safe + pad), "BACK", font=font, fill=GUIDE_TRIM)
    draw.text(
        (front_left + safe + pad, bleed + safe + pad),
        "FRONT - title goes above this line",
        font=font,
        fill=GUIDE_TRIM,
    )

    # The spine is only ~80px wide, far too narrow for a horizontal label, so the
    # colours are explained in the back panel's empty space instead.
    legend = (
        (GUIDE_TRIM, "trim edge - cut here"),
        (GUIDE_SPINE, "spine"),
        (GUIDE_SAFE, "safe margin / title band"),
    )
    swatch = size * 2
    y = trim_bottom - safe - pad - len(legend) * size * 2
    for color, label in legend:
        draw.line([(bleed + safe + pad, y), (bleed + safe + pad + swatch, y)], fill=color, width=line * 2)
        draw.text((bleed + safe + pad + swatch + pad, y - size // 2), label, font=font, fill=color)
        y += size * 2
    return guides


@dataclass
class PrintJob:
    """The print job, as opposed to the design held in a CoverSpec."""

    out: Path
    trim: Trim = DEFAULT_TRIM
    dpi: int = DEFAULT_DPI
    supersample: int = 2
    only: str = "all"
    pages: int | None = None
    paper: str = "white"
    guides: bool = False
    label_tiles: bool = False


def write_cover(
    layout: ShatterLayout, spec: CoverSpec, job: PrintJob
) -> list[Path]:
    """Render and save the requested panels. The single output path, shared by
    the CLI and the chooser."""
    width, height = panel_pixels(job.trim, job.dpi)
    bleed = inches_to_pixels(BLEED_INCHES, job.dpi)
    params = spec.render_params(width, height, bleed, job.supersample)

    front = render_front(layout, params) if job.only != "back" else None
    back = render_back(params) if job.only in ("back", "wrap", "all") else None

    written = []
    if job.only in ("front", "all"):
        written.append(save_png(front, job.out / "front.png", job.dpi))
    if job.label_tiles and front is not None:
        labelled = draw_tile_labels(front, layout, params)
        written.append(save_png(labelled, job.out / "front_labels.png", job.dpi))
    if job.only in ("back", "all"):
        written.append(save_png(back, job.out / "back.png", job.dpi))

    if job.only in ("wrap", "all"):
        spine = inches_to_pixels(spine_width_inches(job.pages, job.paper), job.dpi)
        wrap = build_wrap(front, back, spine, bleed)
        written.append(save_png(wrap, job.out / "cover_wrap.png", job.dpi))

        if job.guides:
            geometry = WrapGeometry(
                panel_width=width,
                panel_height=height,
                bleed=bleed,
                spine=spine,
                title_band=spec.title_band,
                dpi=job.dpi,
            )
            guides = annotate_wrap(wrap, geometry)
            written.append(
                save_png(guides, job.out / "cover_wrap_guides.png", job.dpi)
            )
    return written
