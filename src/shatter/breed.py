"""Mutation rules for the chooser (section 11.2) and the genes it can lock.

Pure functions over CoverSpec, so the breeding behaviour can be tested properly
even though the window that drives it cannot.

The mutable fields are grouped into six named **genes** (section 12.1, decision
1), held as data in `GENES` rather than as a chain of conditionals. Any gene can
be locked, which is what lets you hold the colour scheme or the tiling still while
everything else keeps rolling.
"""

import random
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from shatter.spec import CoverSpec

#: Sensible range for each mutable knob. Mutations are scaled to the span and
#: clamped to the ends, so a knob sitting at its limit still produces legal
#: children instead of drifting out of bounds.
KNOB_RANGES: dict[str, tuple[float, float]] = {
    "core_fraction": (0.20, 0.90),
    "falloff": (0.80, 4.00),
    "max_push": (0.05, 1.20),
    "jitter": (0.00, 0.60),
    "max_rotation": (0.0, 90.0),
    "dropout": (0.00, 0.70),
    "tile_gap": (0.02, 0.18),
    "box_margin": (0.05, 0.30),
}

#: The knobs that shape the shatter itself, and the two that govern spacing.
#: Split because they are separately lockable -- holding the spacing while the
#: shatter keeps moving is a normal thing to want.
SHATTER_KNOBS = (
    "core_fraction", "falloff", "max_push", "jitter", "max_rotation", "dropout",
)
SPACING_KNOBS = ("tile_gap", "box_margin")

SEED_LIMIT = 1_000_000

FAMILIES = ("p2", "p3", "pinwheel")

#: Tile density, as targets for the whole-tile depth resolver. Stops short of the
#: ~400 mark where the shatter stops reading as tiles (section 8).
ZOOM_CHOICES = (60, 100, 150, 250, 400)

#: Curated rather than free-form: a random hex would wander out of the pastel
#: register, and pastels that are nearly white make white tiles disappear.
BACKGROUNDS = (
    "#F2D9E6",  # pink
    "#DCE8F2",  # blue
    "#E2EFE4",  # green
    "#F7E7CE",  # champagne
    "#EDE4F3",  # lilac
    "#E8F1F2",  # ice
    "#F5EFE0",  # cream
    "#E9E4D8",  # stone
    "#DCEEF0",  # aqua
    "#F3E3E1",  # blush
)

#: (tile, box) pairs. Equal values are excluded because the box fill is what
#: shows through the tile gaps -- same colour on both means invisible tiles.
COLOR_COMBOS = tuple(
    (tile, box)
    for tile in ("white", "dark", "bg")
    for box in ("white", "dark", "bg")
    if tile != box
)

PALETTES = tuple(
    (bg, tile, box) for bg in BACKGROUNDS for tile, box in COLOR_COMBOS
)


@dataclass(frozen=True)
class Radius:
    """How far a child may drift from its parent.

    `seed_probability` matters more than it looks: the seed drives every per-tile
    random draw, so re-rolling it changes the arrangement completely however small
    the knob mutations are. Keeping the seed is what lets "closer" be close.

    The three `*_probability` fields below govern the *major* genes -- the ones
    that change what kind of cover this is rather than how it is tuned. They are
    per child, so across a row of five you get roughly one or two that jumped.
    """

    knob_scale: float
    seed_probability: float
    family_probability: float = 0.0
    palette_probability: float = 0.0
    zoom_probability: float = 0.0


CLOSER = Radius(knob_scale=0.10, seed_probability=0.20)
FURTHER = Radius(
    knob_scale=0.35,
    seed_probability=0.80,
    family_probability=0.12,
    palette_probability=0.18,
    zoom_probability=0.12,
)

RADII = {"closer": CLOSER, "further": FURTHER}

Changes = dict[str, object]


def _other(options, current, rng: random.Random):
    """Pick a value that is not the current one, so a mutation always shows."""
    alternatives = [option for option in options if option != current]
    return rng.choice(alternatives) if alternatives else current


def _drift(spec: CoverSpec, radius: Radius, rng: random.Random, knobs) -> Changes:
    changes: Changes = {}
    for knob in knobs:
        low, high = KNOB_RANGES[knob]
        drift = rng.gauss(0.0, radius.knob_scale * (high - low))
        changes[knob] = min(high, max(low, getattr(spec, knob) + drift))
    return changes


def _mutate_shatter(spec: CoverSpec, radius: Radius, rng: random.Random) -> Changes:
    return _drift(spec, radius, rng, SHATTER_KNOBS)


def _mutate_spacing(spec: CoverSpec, radius: Radius, rng: random.Random) -> Changes:
    return _drift(spec, radius, rng, SPACING_KNOBS)


def _mutate_seed(spec: CoverSpec, radius: Radius, rng: random.Random) -> Changes:
    if rng.random() < radius.seed_probability:
        return {"seed": rng.randrange(SEED_LIMIT)}
    return {}


def _mutate_tiling(spec: CoverSpec, radius: Radius, rng: random.Random) -> Changes:
    if rng.random() < radius.family_probability:
        return {"family": _other(FAMILIES, spec.family, rng)}
    return {}


def _mutate_colour(spec: CoverSpec, radius: Radius, rng: random.Random) -> Changes:
    if rng.random() < radius.palette_probability:
        current = (spec.bg, spec.tile_color, spec.box_color)
        bg, tile, box = _other(PALETTES, current, rng)
        return {"bg": bg, "tile_color": tile, "box_color": box}
    return {}


def _mutate_zoom(spec: CoverSpec, radius: Radius, rng: random.Random) -> Changes:
    if rng.random() < radius.zoom_probability:
        # An explicit depth would override zoom and make the mutation a no-op.
        return {"zoom": _other(ZOOM_CHOICES, spec.zoom, rng), "depth": None}
    return {}


@dataclass(frozen=True)
class Gene:
    """One independently lockable part of the genome.

    `fields` is the CoverSpec fields this gene owns -- used by tests and by the
    chooser's captions, and the thing a lock actually protects.
    """

    name: str
    fields: tuple[str, ...]
    describe: str
    mutate: Callable[[CoverSpec, Radius, random.Random], Changes]
    #: The Radius field that gates this gene. When it is zero the gene cannot
    #: move at that radius at all -- Closer, for instance, leaves every major
    #: gene alone by design, so locking the rest makes Closer a dead button.
    gate: str


#: The six genes, in the order their random draws are made. That order is part of
#: the contract: it reproduces the pre-lock mutation stream exactly, so an old
#: breed seed still breeds the same row.
GENES: tuple[Gene, ...] = (
    Gene(
        "shatter", SHATTER_KNOBS, "how the tiles break out",
        _mutate_shatter, "knob_scale",
    ),
    Gene(
        "spacing", SPACING_KNOBS, "tile gap and box margin",
        _mutate_spacing, "knob_scale",
    ),
    Gene("seed", ("seed",), "the arrangement", _mutate_seed, "seed_probability"),
    Gene("tiling", ("family",), "the tiling family", _mutate_tiling, "family_probability"),
    Gene(
        "colour", ("bg", "tile_color", "box_color"), "the colour scheme",
        _mutate_colour, "palette_probability",
    ),
    Gene("zoom", ("zoom", "depth"), "tile density", _mutate_zoom, "zoom_probability"),
)

GENE_NAMES: tuple[str, ...] = tuple(gene.name for gene in GENES)

#: The CLI spells colours the American way elsewhere (--tile-color), so accept
#: both rather than making the user remember which this one is.
GENE_ALIASES = {"color": "colour"}


def parse_locks(text: str) -> frozenset[str]:
    """Parse a comma-separated --lock value into gene names."""
    names = [part.strip() for part in text.split(",") if part.strip()]
    return resolve_locks(names)


def resolve_locks(names: Iterable[str]) -> frozenset[str]:
    resolved = {GENE_ALIASES.get(name, name) for name in names}
    unknown = resolved - set(GENE_NAMES)
    if unknown:
        raise ValueError(
            f"Unknown gene(s) {sorted(unknown)}. Choose from: {', '.join(GENE_NAMES)}"
        )
    return frozenset(resolved)


def locks_everything(locked: Iterable[str]) -> bool:
    """True when nothing is left free, so every child is a copy of its parent."""
    return set(GENE_NAMES) <= set(locked)


def movable_genes(radius: Radius) -> frozenset[str]:
    """The genes this radius can actually move.

    Not every gene moves at every radius: Closer deliberately leaves the major
    genes alone (section 11.2), so `movable_genes(CLOSER)` is the three minor ones.
    """
    return frozenset(
        gene.name for gene in GENES if getattr(radius, gene.gate) > 0
    )


def is_inert(radius: Radius, locked: Iterable[str]) -> bool:
    """True when everything this radius could move is locked, so it can do nothing.

    Worth asking separately from `locks_everything`: Closer is already inert with
    only `shatter`, `spacing` and `seed` held, and a button that silently does
    nothing reads as a bug rather than as a locked gene doing its job.
    """
    return movable_genes(radius) <= frozenset(resolve_locks(locked))


def mutate(
    spec: CoverSpec,
    radius: Radius,
    rng: random.Random,
    locked: Iterable[str] = frozenset(),
) -> CoverSpec:
    """One child of `spec`, with `locked` genes inherited unchanged.

    **A locked gene still makes its random draws; the result is thrown away.**
    That looks wasteful and is deliberate -- it keeps the random stream aligned, so
    locking the tiling does not also re-roll the shatter knobs. It is the same
    reasoning as section 7's "random draws are made for every tile, including
    intact ones": a lock should re-classify what moves, not scramble what didn't.
    """
    locked = resolve_locks(locked)
    changes: Changes = {}
    for gene in GENES:
        proposed = gene.mutate(spec, radius, rng)
        if gene.name not in locked:
            changes.update(proposed)
    return spec.with_changes(**changes)


def generation(
    spec: CoverSpec,
    count: int,
    radius: Radius,
    rng: random.Random,
    locked: Iterable[str] = frozenset(),
) -> list[CoverSpec]:
    locked = resolve_locks(locked)
    return [mutate(spec, radius, rng, locked) for _ in range(count)]


def random_seeds(spec: CoverSpec, count: int, rng: random.Random) -> list[CoverSpec]:
    """Same knobs, fresh arrangements -- the plain 'show me more' case."""
    return [spec.with_changes(seed=rng.randrange(SEED_LIMIT)) for _ in range(count)]
