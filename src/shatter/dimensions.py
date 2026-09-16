"""Physical print spec: trim, bleed, and the KDP spine-width formula.

The per-page thickness constants are Amazon's and are the one thing here likely
to go stale, so they live alone at the top where they are easy to correct.
"""

DEFAULT_DPI = 300
DEFAULT_TRIM = (6.0, 9.0)
BLEED_INCHES = 0.125

#: Inches of spine per interior page, by paper stock (KDP black-and-white).
PAGE_THICKNESS_INCHES = {
    "white": 0.002252,
    "cream": 0.0025,
}

Trim = tuple[float, float]


def parse_trim(value: str) -> Trim:
    """'6x9' -> (6.0, 9.0), in inches."""
    parts = value.lower().split("x")
    if len(parts) != 2:
        raise ValueError(f"Expected a trim size like '6x9', got {value!r}")
    try:
        width, height = (float(part) for part in parts)
    except ValueError:
        raise ValueError(f"Expected a trim size like '6x9', got {value!r}") from None
    if width <= 0 or height <= 0:
        raise ValueError(f"Trim dimensions must be positive, got {value!r}")
    return width, height


def inches_to_pixels(inches: float, dpi: int = DEFAULT_DPI) -> int:
    return round(inches * dpi)


def panel_pixels(trim: Trim, dpi: int = DEFAULT_DPI) -> tuple[int, int]:
    """Trim size in pixels, before bleed."""
    width, height = trim
    return inches_to_pixels(width, dpi), inches_to_pixels(height, dpi)


def spine_width_inches(pages: int, paper: str) -> float:
    if pages < 1:
        raise ValueError(f"Page count must be at least 1, got {pages}")
    try:
        thickness = PAGE_THICKNESS_INCHES[paper]
    except KeyError:
        raise ValueError(
            f"Unknown paper {paper!r}, expected one of "
            f"{sorted(PAGE_THICKNESS_INCHES)}"
        ) from None
    return pages * thickness


def wrap_pixels(
    trim: Trim, pages: int, paper: str, dpi: int = DEFAULT_DPI
) -> tuple[int, int]:
    """Full wrap canvas: bleed | back | spine | front | bleed."""
    trim_width, trim_height = panel_pixels(trim, dpi)
    bleed = inches_to_pixels(BLEED_INCHES, dpi)
    spine = inches_to_pixels(spine_width_inches(pages, paper), dpi)
    return (2 * trim_width + 2 * bleed + spine, trim_height + 2 * bleed)
