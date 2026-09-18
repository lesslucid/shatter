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
from dataclasses import dataclass, replace
from functools import lru_cache

from shatter.color import (
    BORDER_STYLES,
    NAMED_COLORS,
    ROLE_LAYOUTS,
    TILE_SPLITS,
    neighbouring_permutations,
    offered_by_combination,
)
from shatter.spec import CoverSpec
from shatter.wada import combination_by_id

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

#: How far `box_margin` may drift for a clipped cover. `KNOB_RANGES` stops at
#: 0.05, which would drag a solid cover back to a floating one on its first
#: mutation and silently lose the look (decision 25). Past about -0.25 the intact
#: core fills the frame and the shatter stops being visible, so that is the floor.
#:
#: Changing a clamp costs nothing in the mutation stream: `_drift` draws its
#: gaussian either way, and only where the result lands moves.
CLIPPED_BOX_MARGIN_FLOOR = -0.25

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


#: Every (layout, combination, permutation) the wada mode may offer, as one flat
#: pool. Flat because the three move together and cannot be drawn independently:
#: `box` and `shapes` need a three-colour combination and `full` a four-colour
#: one, so a layout and a combination have to agree on size (decision 15). Every
#: entry has already passed the contrast floor, which is what makes "the breeder
#: only offers covers that pass" true by construction rather than by checking.
@lru_cache(maxsize=1)
def wada_schemes() -> tuple[tuple[str, int], ...]:
    return tuple(
        (layout, combination)
        for layout in ROLE_LAYOUTS
        for combination in offered_by_combination(layout)
    )


def _carry_permutation(spec: CoverSpec, role_layout: str, combination: int) -> int:
    """The role assignment to use after the combination moves under it.

    Decision 10 wants a role assignment you like to *survive* while the colours
    roam -- that is the whole point of giving the permutation its own low rate.
    Drawing a fresh permutation with every new combination would undo it: at
    `palette_probability` the assignment would be scrambled roughly every fifth
    child, and no alternate layout could ever be held long enough to choose.

    So the parent's permutation is carried across whenever it is still legal.
    When the *layout* changes the index means something else entirely -- three
    roles become four -- so there is nothing to carry, and the lowest legal
    permutation is used instead, which lands back on the house look.
    """
    legal = offered_by_combination(role_layout)[combination]
    if role_layout == spec.role_layout and spec.role_permutation in legal:
        return spec.role_permutation
    return min(legal)


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
    #: How often the *role assignment* shifts, independently of the combination
    #: and by a single swap (decision 10). Deliberately lower than
    #: `palette_probability`: it is what makes the house look the statistical
    #: centre rather than merely the starting point, and what lets an alternate
    #: role layout survive long enough to be chosen. Only read in wada mode.
    #:
    #: 0.10 was measured, not chosen (decision 10 asks for that explicitly).
    #: Across rows of five bred from the stock wada spec: 45% of rows offer at
    #: least one alternate assignment -- so you meet one every second row or so --
    #: while 4.44 of 5 children still carry the parent's, which is what keeps a
    #: track you have chosen from drifting out from under you. 0.06 made an
    #: alternate too rare to find (33% of rows, a median of 10 generations to
    #: meet one); 0.20 put one in two rows out of three and stopped the current
    #: assignment reading as the default.
    permutation_probability: float = 0.0


CLOSER = Radius(knob_scale=0.10, seed_probability=0.20)
FURTHER = Radius(
    knob_scale=0.35,
    seed_probability=0.80,
    family_probability=0.12,
    palette_probability=0.18,
    zoom_probability=0.12,
    permutation_probability=0.10,
)

RADII = {"closer": CLOSER, "further": FURTHER}

Changes = dict[str, object]


def _other(options, current, rng: random.Random):
    """Pick a value that is not the current one, so a mutation always shows."""
    alternatives = [option for option in options if option != current]
    return rng.choice(alternatives) if alternatives else current


def knob_bounds(knob: str, spec: CoverSpec) -> tuple[float, float]:
    """The range a knob may drift in, for this cover.

    Only `box_margin` reads the spec, and only to let a clipped cover keep
    overfilling its box (decision 25). Everything else is `KNOB_RANGES` as it
    stands.
    """
    low, high = KNOB_RANGES[knob]
    if knob == "box_margin" and spec.clip_tiles:
        return (CLIPPED_BOX_MARGIN_FLOOR, high)
    return (low, high)


def _drift(spec: CoverSpec, radius: Radius, rng: random.Random, knobs) -> Changes:
    changes: Changes = {}
    for knob in knobs:
        low, high = knob_bounds(knob, spec)
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


def _mutate_classic_colour(spec: CoverSpec, radius: Radius, rng: random.Random) -> Changes:
    changes: Changes = {}
    if rng.random() < radius.palette_probability:
        current = (spec.bg, spec.tile_color, spec.box_color)
        bg, tile, box = _other(PALETTES, current, rng)
        changes.update({"bg": bg, "tile_color": tile, "box_color": box})
    if rng.random() < radius.palette_probability:
        split = _other(TILE_SPLITS, spec.tile_split, rng)
        changes["tile_split"] = split
        if split == "by_type":
            # The second fill only means anything once the tiles are split, and
            # it must not match the box: the box is what shows through the gaps,
            # so equal values would make that prototile disappear.
            box = changes.get("box_color", spec.box_color)
            options = tuple(name for name in NAMED_COLORS if name != box)
            changes["tile_color_b"] = _other(options, spec.tile_color_b, rng)
    return changes


def _mutate_wada_colour(spec: CoverSpec, radius: Radius, rng: random.Random) -> Changes:
    """The wada equivalent, and deliberately not the classic one with extra fields.

    Decision 15: `bg`, `tile_color` and `box_color` are left alone here, because
    wada mode never reads them -- drifting them would fill a saved config with
    values that do nothing while every panel came back the same colour.
    """
    changes: Changes = {}
    if rng.random() < radius.palette_probability:
        current = (spec.role_layout, spec.wada_combination)
        layout, combination = _other(wada_schemes(), current, rng)
        changes.update({
            "role_layout": layout,
            "wada_combination": combination,
            "role_permutation": _carry_permutation(spec, layout, combination),
        })

    # The role assignment draws separately and more rarely (decision 10), so a
    # layout worth keeping survives a few generations of combinations roaming.
    if rng.random() < radius.permutation_probability:
        layout = changes.get("role_layout", spec.role_layout)
        combination = changes.get("wada_combination", spec.wada_combination)
        permutation = changes.get("role_permutation", spec.role_permutation)
        neighbours = neighbouring_permutations(
            combination_by_id(combination), layout, permutation
        )
        if neighbours:
            changes["role_permutation"] = rng.choice(neighbours)
    return changes


def _mutate_colour(spec: CoverSpec, radius: Radius, rng: random.Random) -> Changes:
    """The colour gene, which reads whichever model the spec is in (decision 15).

    `border` is drawn for both, because a tile outline is independent of where
    the colours came from -- which is also why `color.resolve_border` sits
    outside the mode dispatch.
    """
    if spec.mode == "wada":
        changes = _mutate_wada_colour(spec, radius, rng)
    else:
        changes = _mutate_classic_colour(spec, radius, rng)

    if rng.random() < radius.palette_probability:
        changes["border"] = _other(BORDER_STYLES, spec.border, rng)
    return changes


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
        "colour",
        (
            "bg", "tile_color", "box_color", "tile_color_b", "tile_split",
            "border", "wada_combination", "role_layout", "role_permutation",
        ),
        "the colour scheme",
        _mutate_colour,
        "palette_probability",
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
    child = spec.with_changes(**changes)
    if child == spec:
        child = _force_a_difference(spec, radius, rng, locked)
    return child


def _force_a_difference(
    spec: CoverSpec, radius: Radius, rng: random.Random, locked: frozenset[str]
) -> CoverSpec:
    """Decision 9: a child identical to its parent wastes one of five slots.

    Section 11.2 already refuses a mutation that re-picks the current value, for
    exactly this reason, and row 1 of the chooser already shows the parent -- so
    row 2 has no need of a copy. Rather than scaling the mutation rates up when
    genes are locked, draw as normal and repair the one case that matters.

    **This never fires for unlocked breeding**, which is what keeps the unlocked
    stream bit-identical: the eight continuous knobs drift on every child, so an
    exact copy is only reachable once `shatter` and `spacing` are both held.
    Measured at 0 exact copies in 20,000 unlocked children.

    A gene is forced by re-running its own mutation with its gate opened to
    certainty, so it uses the same rules it always does -- nothing here knows how
    any particular gene moves. If every free gene refuses (all its alternatives
    equal the current value), the parent comes back unchanged and the caller
    treats it as the refusal it is; that is the `Closer`-is-exempt case, where
    only major genes are free and the radius cannot move them.
    """
    free = [
        gene
        for gene in GENES
        if gene.name not in locked and getattr(radius, gene.gate) > 0
    ]
    if not free:
        return spec

    # Random order, so the same gene is not always the one that gives way.
    order = free[:]
    rng.shuffle(order)
    for gene in order:
        forced = replace(radius, **{gene.gate: 1.0})
        child = spec.with_changes(**gene.mutate(spec, forced, rng))
        if child != spec:
            return child
    return spec


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
