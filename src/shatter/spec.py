"""CoverSpec: the whole recipe for a cover as one serialisable object.

This is what `--config` saves and loads, and what the chooser breeds
(section 11.2). Output concerns -- trim, DPI, page count, where to write --
are deliberately *not* here: they describe the print job, not the design.
"""

import json
import math
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

from shatter.autoshatter import ShatterParams, auto_shatter
from shatter.color import DEFAULT_WADA_COMBINATION, effective_tile_split
from shatter.geometry import resolve_depth
from shatter.model import ShatterLayout
from shatter.render import RenderParams


@dataclass
class CoverSpec:
    family: str = "p3"
    zoom: int = 150
    depth: int | None = None  # raw override; zoom is used when this is None
    seed: int = 42
    drop_partial_tiles: bool = True

    core_fraction: float = 0.6
    falloff: float = 2.0
    max_push: float = 0.5
    jitter: float = 0.12
    max_rotation: float = 40.0  # degrees here; radians only inside ShatterParams
    dropout: float = 0.3

    # Which colour model reads the fields below (phase 10). Additive with a
    # default, so configs written before it existed still load.
    mode: str = "classic"
    bg: str = "#F2D9E6"
    tile_color: str = "dark"
    box_color: str = "white"
    overlap_color: str = "auto"
    border: str = "none"  # "none" | "black" | "white" (phase 11)
    border_width: float = 0.12  # fraction of the median tile radius
    tile_split: str = "single"  # "single" | "by_type" (phase 12)
    tile_color_b: str = "bg"  # second prototile's fill; only read when by_type
    # Read only when mode="wada" (phase 13); additive with defaults, so a config
    # written before phase 13 still loads.
    wada_combination: int = DEFAULT_WADA_COMBINATION
    role_layout: str = "box"  # "box" | "shapes" | "full"
    role_permutation: int = 0
    tile_gap: float = 0.08
    box_margin: float = 0.15
    # Corner radius as a fraction of the box's shorter side; 0 is square, 0.5 a
    # stadium (phase 15). Not a bred gene -- see section 12.2.
    box_corner: float = 0.0
    title_band: float = 0.30
    side_margin: float = 0.10
    bottom_margin: float = 0.10

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CoverSpec":
        unknown = set(data) - SPEC_FIELDS
        if unknown:
            raise ValueError(f"Unknown config keys: {sorted(unknown)}")
        return cls(**data)

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path

    @classmethod
    def load(cls, path: Path) -> "CoverSpec":
        return cls.from_dict(json.loads(path.read_text()))

    def with_changes(self, **changes) -> "CoverSpec":
        return replace(self, **changes)

    def shatter_params(self) -> ShatterParams:
        return ShatterParams(
            core_fraction=self.core_fraction,
            falloff=self.falloff,
            max_push=self.max_push,
            jitter=self.jitter,
            max_rotation=math.radians(self.max_rotation),
            dropout=self.dropout,
        )

    def render_params(
        self, width: int, height: int, bleed: int = 0, supersample: int = 2
    ) -> RenderParams:
        return RenderParams(
            width=width,
            height=height,
            bleed=bleed,
            mode=self.mode,
            bg=self.bg,
            tile_color=self.tile_color,
            box_color=self.box_color,
            overlap_color=self.overlap_color,
            border=self.border,
            border_width=self.border_width,
            # In wada mode the role layout owns the split, not this field
            # (section 12's table); classic mode gets it back untouched.
            tile_split=effective_tile_split(self.mode, self.role_layout, self.tile_split),
            tile_color_b=self.tile_color_b,
            wada_combination=self.wada_combination,
            role_layout=self.role_layout,
            role_permutation=self.role_permutation,
            tile_gap=self.tile_gap,
            box_margin=self.box_margin,
            box_corner=self.box_corner,
            title_band=self.title_band,
            side_margin=self.side_margin,
            bottom_margin=self.bottom_margin,
            supersample=supersample,
        )

    def resolved_depth(self) -> int:
        if self.depth is not None:
            return self.depth
        return resolve_depth(self.family, self.zoom, self.drop_partial_tiles)

    def build_layout(self) -> ShatterLayout:
        return auto_shatter(
            family=self.family,
            depth=self.resolved_depth(),
            seed=self.seed,
            params=self.shatter_params(),
            drop_partial_tiles=self.drop_partial_tiles,
        )


SPEC_FIELDS = {field.name for field in fields(CoverSpec)}
