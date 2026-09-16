"""Loads the vendored Sanzo Wada colour-combination dataset (phase 13).

The data file is `shatter/data/sanzo_wada_colors.json`, copied verbatim under
section 2's narrow exception; `data/SOURCE.md` carries its provenance and licence.
It is stored **colour-major** -- 159 named colours, each tagged with which of the
348 combinations it belongs to -- so the one job this module has beyond reading
the file is inverting that into combination -> colours.

This is a rewrite of the old project's `wada_data.py`, not a copy. That one
reaches for `covers.assets.REPO_ROOT`, a coupling there is no reason to inherit;
this one goes through `importlib.resources`, so it works the same from a source
tree, a wheel or a zipimport.

Like `covers.tiling`, this module imports **only the standard library and knows
nothing about colour models** -- it hands back plain RGB. Deciding what a colour
means perceptually is `color.py`'s job, which is also why the dependency runs one
way: `color` imports `wada`, never the reverse.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files

RGB = tuple[int, int, int]

#: `data/` is deliberately not a package -- section 3 lists it as plain package
#: data -- so it is reached as a path under `shatter` rather than imported.
DATA_FILE = "sanzo_wada_colors.json"

#: The combination sizes the dataset actually contains: 120 of two colours, 120
#: of three, 108 of four. Section 12's role-layout table is built on this split,
#: so it is asserted at load rather than trusted.
EXPECTED_SIZES = {2: 120, 3: 120, 4: 108}


@dataclass(frozen=True)
class WadaColor:
    """One named colour.

    The dataset also ships `cmyk` and `lab`, and neither is carried here. The
    `lab` omission is deliberate and is section 12.1 decision 13: upstream
    derived it from the CMYK while re-converting the RGB separately, so the two
    disagree by up to 20 dE, and the contrast floor must measure the colour that
    is actually rendered. Not carrying it is what stops it being reached for by
    accident.
    """

    name: str
    rgb: RGB
    hex: str


@dataclass(frozen=True)
class WadaCombination:
    """One of Wada's 348 palettes: an *unordered* bag of two to four colours.

    Unordered is the point -- the colours arrive with no roles attached, which is
    the design problem section 12 hands to `color.py`.
    """

    id: int
    colors: tuple[WadaColor, ...]

    @property
    def size(self) -> int:
        return len(self.colors)


@lru_cache(maxsize=1)
def _load() -> tuple[WadaCombination, ...]:
    raw = json.loads(
        files("shatter").joinpath("data", DATA_FILE).read_text(encoding="utf-8")
    )

    by_id: dict[int, list[WadaColor]] = {}
    for entry in raw:
        color = WadaColor(
            name=entry["name"], rgb=tuple(entry["rgb"]), hex=entry["hex"]
        )
        for combo_id in entry["combinations"]:
            by_id.setdefault(combo_id, []).append(color)

    return tuple(
        WadaCombination(id=combo_id, colors=tuple(colors))
        for combo_id, colors in sorted(by_id.items())
    )


def all_combinations() -> tuple[WadaCombination, ...]:
    """Every combination, ordered by id. Ids run 1-348 with no gaps."""
    return _load()


def combination_by_id(combo_id: int) -> WadaCombination:
    combos = _load()
    if not 1 <= combo_id <= len(combos):
        raise KeyError(
            f"No Wada combination with id {combo_id} "
            f"(valid range 1-{len(combos)})"
        )
    # Ids are contiguous from 1, asserted by `check_dataset`, so this indexes
    # rather than scans.
    return combos[combo_id - 1]


def combinations_of_size(size: int) -> tuple[WadaCombination, ...]:
    """The combinations holding exactly `size` colours.

    Section 12's role layouts are chosen by combination size: the three-colour
    ones fill `box` or `shapes`, the four-colour ones fill `full`.
    """
    return tuple(combo for combo in _load() if combo.size == size)


def check_dataset() -> None:
    """Assert the shape section 12's arithmetic depends on.

    Cheap, and it turns a silently truncated or re-scraped data file into a loud
    failure rather than a mode that quietly offers fewer covers.
    """
    combos = _load()
    ids = [combo.id for combo in combos]
    if ids != list(range(1, len(combos) + 1)):
        raise ValueError("Wada combination ids are not contiguous from 1")

    sizes: dict[int, int] = {}
    for combo in combos:
        sizes[combo.size] = sizes.get(combo.size, 0) + 1
    if sizes != EXPECTED_SIZES:
        raise ValueError(
            f"Wada combination sizes are {dict(sorted(sizes.items()))}, "
            f"expected {EXPECTED_SIZES}"
        )
