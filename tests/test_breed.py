import hashlib
import json
import random

import pytest

from shatter.breed import (
    BACKGROUNDS,
    CLOSER,
    COLOR_COMBOS,
    FAMILIES,
    FURTHER,
    GENES,
    GENE_NAMES,
    KNOB_RANGES,
    SHATTER_KNOBS,
    SPACING_KNOBS,
    ZOOM_CHOICES,
    Radius,
    generation,
    is_inert,
    locks_everything,
    movable_genes,
    mutate,
    parse_locks,
    random_seeds,
)
from shatter.spec import CoverSpec

FROZEN = Radius(knob_scale=0.0, seed_probability=0.0)

#: Never mutated at any radius. The title band and margins are the composition the
#: collaborator sets type into; overlap_color is "auto", which already follows
#: whatever tile colour is chosen, so mutating it would add nothing.
ALWAYS_FIXED = (
    "drop_partial_tiles",
    "overlap_color",
    "title_band",
    "side_margin",
    "bottom_margin",
)

#: The "major" genes: what kind of cover this is, rather than how it is tuned.
MAJOR = ("family", "zoom", "bg", "tile_color", "box_color")


def test_zero_radius_is_a_no_op():
    spec = CoverSpec()
    assert mutate(spec, FROZEN, random.Random(1)) == spec


def test_same_rng_seed_breeds_the_same_children():
    spec = CoverSpec()
    a = generation(spec, 5, CLOSER, random.Random(7))
    b = generation(spec, 5, CLOSER, random.Random(7))
    assert a == b


def test_generation_returns_the_requested_count():
    assert len(generation(CoverSpec(), 5, CLOSER, random.Random(0))) == 5


@pytest.mark.parametrize("radius", [CLOSER, FURTHER])
def test_knobs_stay_in_range_across_many_generations(radius):
    """Clamping must hold even when a parent already sits at a limit."""
    rng = random.Random(3)
    spec = CoverSpec()
    for _ in range(60):
        spec = mutate(spec, radius, rng)
        for knob, (low, high) in KNOB_RANGES.items():
            assert low <= getattr(spec, knob) <= high, knob


@pytest.mark.parametrize("radius", [CLOSER, FURTHER])
def test_composition_never_drifts(radius):
    """The type area must stay put whatever else changes (section 11.2)."""
    rng = random.Random(11)
    spec = CoverSpec()
    for _ in range(40):
        child = mutate(spec, radius, rng)
        for field in ALWAYS_FIXED:
            assert getattr(child, field) == getattr(spec, field), field
        spec = child


def test_closer_holds_the_major_genes_still():
    """Closer means closer; jumping family or palette is not a small step."""
    rng = random.Random(11)
    spec = CoverSpec()
    for _ in range(60):
        child = mutate(spec, CLOSER, rng)
        for field in MAJOR:
            assert getattr(child, field) == getattr(spec, field), field
        spec = child


def test_further_lets_every_major_gene_move():
    rng = random.Random(4)
    base = CoverSpec()
    moved = {field: False for field in MAJOR}
    for _ in range(300):
        child = mutate(base, FURTHER, rng)
        for field in MAJOR:
            if getattr(child, field) != getattr(base, field):
                moved[field] = True
    assert all(moved.values()), moved


def test_further_jumps_once_or_twice_per_row_of_five():
    """Enough that a row usually offers a surprise, not so much that the row
    stops being recognisably related to its parent."""
    rng = random.Random(0)
    base = CoverSpec()
    counts = []
    for _ in range(200):
        children = generation(base, 5, FURTHER, rng)
        counts.append(
            sum(
                1
                for child in children
                if any(
                    getattr(child, field) != getattr(base, field) for field in MAJOR
                )
            )
        )
    average = sum(counts) / len(counts)
    assert 1.0 <= average <= 2.5, average


@pytest.mark.parametrize("radius", [CLOSER, FURTHER])
def test_mutated_values_are_always_legal(radius):
    rng = random.Random(8)
    spec = CoverSpec()
    for _ in range(200):
        spec = mutate(spec, radius, rng)
        assert spec.family in FAMILIES
        assert spec.zoom in ZOOM_CHOICES or spec.zoom == CoverSpec().zoom
        assert spec.bg in BACKGROUNDS or spec.bg == CoverSpec().bg
        assert (spec.tile_color, spec.box_color) in COLOR_COMBOS


def test_tiles_are_never_the_same_colour_as_their_box():
    """Same colour on both means the gaps vanish and so does the pattern."""
    assert all(tile != box for tile, box in COLOR_COMBOS)

    rng = random.Random(19)
    spec = CoverSpec()
    for _ in range(300):
        spec = mutate(spec, FURTHER, rng)
        assert spec.tile_color != spec.box_color


def test_a_major_mutation_always_actually_changes_something():
    """Re-picking the current value would waste one of only five slots."""
    rng = random.Random(6)
    always = Radius(
        knob_scale=0.0,
        seed_probability=0.0,
        family_probability=1.0,
        palette_probability=1.0,
        zoom_probability=1.0,
    )
    spec = CoverSpec()
    for _ in range(100):
        child = mutate(spec, always, rng)
        assert child.family != spec.family
        assert child.zoom != spec.zoom
        assert (child.bg, child.tile_color, child.box_color) != (
            spec.bg,
            spec.tile_color,
            spec.box_color,
        )
        spec = child


def test_zoom_mutation_clears_an_explicit_depth():
    """A set depth overrides zoom, which would make the mutation invisible."""
    rng = random.Random(6)
    always_zoom = Radius(knob_scale=0.0, seed_probability=0.0, zoom_probability=1.0)
    child = mutate(CoverSpec(depth=4), always_zoom, rng)
    assert child.depth is None


def seed_changes(radius, trials=300):
    rng = random.Random(23)
    spec = CoverSpec()
    return sum(1 for _ in range(trials) if mutate(spec, radius, rng).seed != spec.seed)


def test_closer_usually_keeps_the_seed_and_further_usually_does_not():
    """The seed drives every per-tile draw, so keeping it is what makes
    'closer' close. This is the main difference between the two buttons."""
    closer, further = seed_changes(CLOSER), seed_changes(FURTHER)
    assert closer < 100  # ~20% of 300
    assert further > 200  # ~80% of 300
    assert closer < further


def test_closer_moves_knobs_less_than_further():
    rng_a, rng_b = random.Random(5), random.Random(5)
    spec = CoverSpec()

    def spread(radius, rng):
        children = generation(spec, 40, radius, rng)
        return sum(abs(child.max_push - spec.max_push) for child in children)

    assert spread(CLOSER, rng_a) < spread(FURTHER, rng_b)


def test_random_seeds_changes_only_the_seed():
    spec = CoverSpec()
    for child in random_seeds(spec, 10, random.Random(2)):
        assert child.seed != spec.seed
        assert child.with_changes(seed=spec.seed) == spec


# --- Phase 9: locking genes -------------------------------------------------

LOCKABLE = [gene.name for gene in GENES]


def test_every_mutable_field_belongs_to_exactly_one_gene():
    """A new gene that forgets to claim its fields would silently be unlockable."""
    owned = [field for gene in GENES for field in gene.fields]
    assert len(owned) == len(set(owned)), "a field is claimed by two genes"

    expected = set(KNOB_RANGES) | set(MAJOR) | {"seed", "depth"}
    assert set(owned) == expected


def test_no_gene_claims_a_field_that_must_never_move():
    owned = {field for gene in GENES for field in gene.fields}
    assert owned.isdisjoint(ALWAYS_FIXED)


def test_gene_draw_order_matches_the_knob_range_order():
    """The knob genes must consume KNOB_RANGES in its own order, or an old breed
    seed stops reproducing the row it used to."""
    assert SHATTER_KNOBS + SPACING_KNOBS == tuple(KNOB_RANGES)


@pytest.mark.parametrize("gene", GENES, ids=LOCKABLE)
def test_locking_a_gene_changes_only_that_gene(gene):
    """The heart of phase 9, and it asserts two things at once.

    Locked fields must not move -- and nothing *else* may move either, which is
    what proves a locked gene still consumes its random draws instead of shifting
    the stream underneath its neighbours.
    """
    base = CoverSpec()
    free = generation(base, 60, FURTHER, random.Random(11))
    held = generation(base, 60, FURTHER, random.Random(11), {gene.name})

    for loose, locked in zip(free, held):
        for field in gene.fields:
            assert getattr(locked, field) == getattr(base, field)
        differing = {f for f in vars(loose) if getattr(loose, f) != getattr(locked, f)}
        assert differing <= set(gene.fields)


def test_locking_a_gene_still_lets_everything_else_move():
    """The complement of the test above: a lock must not freeze the whole genome."""
    base = CoverSpec()
    held = generation(base, 60, FURTHER, random.Random(11), {"colour"})
    assert len({spec.seed for spec in held}) > 1
    assert len({spec.core_fraction for spec in held}) > 1


def test_locking_everything_yields_copies_of_the_parent():
    base = CoverSpec(jitter=0.31)
    children = generation(base, 5, FURTHER, random.Random(3), LOCKABLE)
    assert children == [base] * 5
    assert locks_everything(LOCKABLE)
    assert not locks_everything(LOCKABLE[:-1])


def test_locking_nothing_is_the_unlocked_default():
    base = CoverSpec()
    assert generation(base, 20, FURTHER, random.Random(5)) == generation(
        base, 20, FURTHER, random.Random(5), frozenset()
    )


@pytest.mark.parametrize("radius", [CLOSER, FURTHER], ids=["closer", "further"])
def test_locked_knobs_stay_put_over_many_generations(radius):
    """Drift is cumulative, so one generation proves very little."""
    spec = CoverSpec()
    rng = random.Random(2)
    for _ in range(40):
        spec = mutate(spec, radius, rng, {"spacing"})
    assert spec.tile_gap == CoverSpec().tile_gap
    assert spec.box_margin == CoverSpec().box_margin


def test_parse_locks_accepts_a_comma_separated_list():
    assert parse_locks("colour,tiling") == frozenset({"colour", "tiling"})
    assert parse_locks(" colour , zoom ") == frozenset({"colour", "zoom"})
    assert parse_locks("") == frozenset()


def test_parse_locks_accepts_the_american_spelling():
    """--tile-color is spelled that way, so --lock color must work too."""
    assert parse_locks("color") == parse_locks("colour")


@pytest.mark.parametrize("bad", ["nope", "colour,nope", "family"])
def test_unknown_genes_are_rejected_by_name(bad):
    with pytest.raises(ValueError, match="Unknown gene"):
        parse_locks(bad)


def test_mutate_rejects_an_unknown_lock():
    with pytest.raises(ValueError, match="Unknown gene"):
        mutate(CoverSpec(), CLOSER, random.Random(0), {"palette"})


#: One row bred from the stock spec at breed seed 1234, recorded from the
#: implementation that predates phase 9 and verified identical after it. This is
#: the permanent guard on the draw order documented on `GENES`: reordering the
#: genes, or skipping a locked gene's draws, shifts the stream and breaks this.
#: A saved --breed-seed is a promise that the same row comes back.
GOLDEN_FURTHER_1234 = [
    (248313, "p2", 150, "#F2D9E6", 0.858283812272, 0.141733275843),
    (488530, "p2", 60, "#F2D9E6", 0.496246175360, 0.214507279978),
    (6061, "p3", 150, "#F2D9E6", 0.427501507753, 0.245470461625),
    (703072, "p3", 150, "#F7E7CE", 0.648547203138, 0.121784851132),
]


def test_the_mutation_stream_is_unchanged_by_phase_9():
    children = generation(CoverSpec(), 4, FURTHER, random.Random(1234))
    actual = [
        (c.seed, c.family, c.zoom, c.bg, round(c.core_fraction, 12), round(c.jitter, 12))
        for c in children
    ]
    assert actual == GOLDEN_FURTHER_1234


def _spec_digest(spec: CoverSpec) -> str:
    """A short, stable fingerprint of every field on a spec."""
    return hashlib.sha256(
        json.dumps(spec.to_dict(), sort_keys=True).encode()
    ).hexdigest()[:12]


#: The same promise as `GOLDEN_FURTHER_1234`, but over **sixteen** children and
#: **every** field rather than four children and six fields.
#:
#: Widened before phase 14, after the narrow version was measured letting a real
#: break through: a prototype that shifted the stream for 22 of 30 children still
#: passed, because the divergence began at child 4 -- one past the end of what was
#: recorded -- and `zoom`, which draws after `colour`, happened to land on the same
#: value anyway. A guard that only looks at the first four children cannot see a
#: break that starts at the fifth, and both the chooser (rows of five) and
#: `contact --count 10` routinely go further than that.
#:
#: Digests rather than values because sixteen specs of fifteen mutable fields is an
#: unreadable wall; the index of the first mismatch is the diagnostic, and the
#: table above says what the early children should actually contain.
GOLDEN_FURTHER_1234_DIGESTS = [
    "808ed8fdb878", "3a9af06ddecc", "6192d66bae82", "a3767c50541c",
    "a70434a60287", "994888996ffc", "55fd4752a635", "70c2ce5a3ca3",
    "415e78e51422", "162b6f9b5762", "0e62def64d8b", "4bfe2606ccb4",
    "4926c95b6d4c", "b966b3a438b7", "010c6662ce68", "7c27501426d7",
]

#: Closer draws from the same stream -- a gated gene still calls `rng.random()`
#: even when its probability is zero -- so it is a second, independent witness
#: that the draw order has not moved.
GOLDEN_CLOSER_1234_DIGESTS = [
    "a92ac921b4b6", "74af0b1385c9", "0ee7ee535817", "de0c885ef9d4",
    "01f3e71dc8d2", "5b40b554ab18", "1b6ad017d7ca", "342e010663c4",
    "e86e418d5197", "d92daa04b804", "c45e0bc99ba7", "c64a1f4e3448",
    "81e25d252581", "b42594e5f11a", "7dd89308d538", "d86f002499d9",
]


@pytest.mark.parametrize(
    "radius, golden",
    [(FURTHER, GOLDEN_FURTHER_1234_DIGESTS), (CLOSER, GOLDEN_CLOSER_1234_DIGESTS)],
    ids=["further", "closer"],
)
def test_the_whole_mutation_stream_is_unchanged(radius, golden):
    actual = [
        _spec_digest(child)
        for child in generation(CoverSpec(), len(golden), radius, random.Random(1234))
    ]
    first = next(
        (i for i, (a, b) in enumerate(zip(actual, golden)) if a != b), None
    )
    assert first is None, (
        f"the mutation stream diverges from child {first} onward, so a saved "
        f"--breed-seed no longer reproduces its row. If this is a deliberate "
        f"change (adding a gene or a draw shifts the stream -- see phase 14), "
        f"re-record it on purpose and say so in the comment above."
    )


# --- which genes a radius can actually move --------------------------------


def test_closer_moves_only_the_minor_genes():
    """Section 11.2: Closer converges because nothing major moves."""
    assert movable_genes(CLOSER) == frozenset({"shatter", "spacing", "seed"})


def test_further_moves_everything():
    assert movable_genes(FURTHER) == set(GENE_NAMES)


def test_every_gene_names_a_real_radius_field():
    """A typo in a gate would silently make a gene look permanently immovable."""
    for gene in GENES:
        assert hasattr(CLOSER, gene.gate), gene.name


def test_a_radius_is_inert_when_all_it_can_move_is_locked():
    assert is_inert(CLOSER, {"shatter", "spacing", "seed"})
    assert not is_inert(FURTHER, {"shatter", "spacing", "seed"})
    assert is_inert(FURTHER, GENE_NAMES)
    assert not is_inert(CLOSER, {"shatter"})


def test_an_inert_radius_really_does_produce_only_copies():
    """The point of asking: `is_inert` must agree with what breeding does."""
    base = CoverSpec()
    for radius, locked in [
        (CLOSER, {"shatter", "spacing", "seed"}),
        (FURTHER, GENE_NAMES),
    ]:
        assert is_inert(radius, locked)
        assert generation(base, 8, radius, random.Random(3), locked) == [base] * 8


def test_a_non_inert_radius_eventually_varies():
    """The complement: if it is not inert, breeding must be able to do something."""
    base = CoverSpec()
    kids = [
        child
        for seed in range(40)
        for child in generation(base, 5, FURTHER, random.Random(seed),
                                {"shatter", "spacing", "seed", "tiling", "zoom"})
    ]
    assert any(child != base for child in kids)
