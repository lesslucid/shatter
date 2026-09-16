"""Tiling family name -> class, used by CLI validation and CoverSpec resolution."""

from covers.tiling.base import Tiling
from covers.tiling.penrose import PenroseP3Tiling
from covers.tiling.penrose_p2 import PenroseP2Tiling
from covers.tiling.pinwheel import PinwheelTiling

TILING_REGISTRY: dict[str, type[Tiling]] = {
    "p2": PenroseP2Tiling,
    "p3": PenroseP3Tiling,
    "pinwheel": PinwheelTiling,
}


def get_tiling(name: str) -> Tiling:
    try:
        cls = TILING_REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Unknown tiling family {name!r}, expected one of {sorted(TILING_REGISTRY)}"
        ) from None
    return cls()
