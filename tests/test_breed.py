import hashlib
import itertools
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
from shatter.color import (
    assign_roles,
    neighbouring_permutations,
    passes_contrast_floor,
)
from shatter.spec import CoverSpec
from shatter.wada import combination_by_id

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

#: What the colour gene gained in phase 14. Kept apart from MAJOR deliberately:
#: the wada fields only move for a wada spec, and the tests built on MAJOR breed
#: a classic one, where they are inert by design (decision 15).
COLOUR_EXTRAS = (
    "tile_color_b", "tile_split", "border",
    "wada_combination", "role_layout", "role_permutation",
)


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

    expected = set(KNOB_RANGES) | set(MAJOR) | set(COLOUR_EXTRAS) | {"seed", "depth"}
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


#: One row bred from the stock spec at breed seed 1234. This is the permanent
#: guard on the draw order documented on `GENES`: reordering the genes, or
#: skipping a locked gene's draws, shifts the stream and breaks this. A saved
#: --breed-seed is a promise that the same row comes back.
#:
#: **Re-recorded at phase 14, deliberately and once** (section 12.1, decision
#: 14). Registering `border` and `tile_split` as bred fields adds draws, and they
#: apply in *both* colour modes, so the classic stream could not be preserved --
#: only the Wada draws could be, by gating them on `spec.mode`. Breed seeds saved
#: before phase 14 no longer reproduce their rows; all four colour genes were
#: batched into this one phase so that this happens once rather than four times.
#: The previous values are in git, at the commit before phase 14 landed.
GOLDEN_FURTHER_1234 = [
    (248313, "p2", 150, "#F2D9E6", 0.858283812272, 0.141733275843),
    (93248, "p3", 150, "#DCEEF0", 0.64929183517, 0.14224722332),
    (495794, "p3", 150, "#F2D9E6", 0.486101613974, 0.026361670466),
    (162078, "p3", 150, "#F2D9E6", 0.9, 0.089023998492),
]


def test_the_mutation_stream_is_unchanged_by_phase_9():
    children = generation(CoverSpec(), 4, FURTHER, random.Random(1234))
    actual = [
        (c.seed, c.family, c.zoom, c.bg, round(c.core_fraction, 12), round(c.jitter, 12))
        for c in children
    ]
    assert actual == GOLDEN_FURTHER_1234


#: Every field any gene can move. The digest covers exactly these.
MUTABLE_FIELDS = sorted({field for gene in GENES for field in gene.fields})


def _spec_digest(spec: CoverSpec) -> str:
    """A short, stable fingerprint of every field mutation can reach.

    Deliberately **not** the whole of `to_dict()`, which is what it hashed when
    first written. That version had a false positive with teeth: adding *any* new
    `CoverSpec` field changed every digest, even a field no gene touches and that
    every child therefore inherits unchanged. Phase 15's `box_corner` tripped it
    while the mutation stream was provably intact -- the readable table above
    still passed -- and a guard that cries wolf on additive schema changes trains
    exactly the casual re-recording that hard rule 2 exists to prevent.

    Hashing the mutable fields loses nothing: a field no gene owns cannot differ
    between a recorded row and a reproduced one, because it is copied from the
    parent either way.
    """
    values = {field: getattr(spec, field) for field in MUTABLE_FIELDS}
    return hashlib.sha256(
        json.dumps(values, sort_keys=True).encode()
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
#: Re-recorded at phase 14 with the table above, and for the same reason. Re-cut
#: again at phase 15 when `_spec_digest` was narrowed to the mutable fields --
#: that changed what the digest *is*, not what the stream does, and the readable
#: table above was untouched by it, which is the evidence the stream held.
GOLDEN_FURTHER_1234_DIGESTS = [
    "6b32ace97dcc", "fd09cc1c2608", "916a10e85fb4", "a445c24bcb4a",
    "21e30213e164", "20c0a2870809", "12a53ab687e3", "51428956b896",
    "e663839b7264", "044979863f63", "4c6e2e76a884", "7a814bb381ea",
    "1ed80b9f41a8", "6f9c2db9e984", "dcdad9f59bba", "1168144b6b33",
]

#: Closer draws from the same stream -- a gated gene still calls `rng.random()`
#: even when its probability is zero -- so it is a second, independent witness
#: that the draw order has not moved.
GOLDEN_CLOSER_1234_DIGESTS = [
    "f6e9a3a4010a", "8c8c9b511802", "dd53fa99e444", "e1a4adad7bd5",
    "23b2c178ec14", "58af364f26b9", "fc76b4079e5c", "de2a3ba85f1e",
    "fba2bca3c617", "a291b05cf65d", "dec93311b488", "4789710f6d84",
    "d2f2856ac3df", "9ab08df01e22", "636a92b42911", "bb6c162ca411",
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


# --- Phase 14: breeding the colour genes -------------------------------------

WADA = CoverSpec(mode="wada")


def test_a_wada_spec_never_drifts_the_classic_colour_fields():
    """Decision 15. Those three fields are not read in wada mode, so moving them
    would fill a saved config with values that do nothing."""
    for child in generation(WADA, 400, FURTHER, random.Random(5)):
        assert (child.bg, child.tile_color, child.box_color) == (
            WADA.bg, WADA.tile_color, WADA.box_color
        )


def test_a_classic_spec_never_drifts_the_wada_fields():
    """The complement, and the reason the classic stream could be preserved for
    the wada draws at all: a classic spec never enters that branch."""
    base = CoverSpec()
    for child in generation(base, 400, FURTHER, random.Random(5)):
        assert (child.wada_combination, child.role_layout, child.role_permutation) == (
            base.wada_combination, base.role_layout, base.role_permutation
        )


def test_every_bred_wada_child_is_an_assignment_the_mode_would_offer():
    """Decision 11 reaching the breeder: the pool is floor-filtered already, so
    this should hold by construction rather than by checking -- which is exactly
    why it is worth asserting."""
    for child in generation(WADA, 1500, FURTHER, random.Random(3)):
        assigned = assign_roles(
            combination_by_id(child.wada_combination),
            child.role_layout,
            child.role_permutation,
        )
        assert passes_contrast_floor(assigned), child


def test_the_role_assignment_moves_by_a_single_swap():
    """Decision 10: a transposition, not a re-roll, so an excursion from the
    house look is a recognisable variation rather than a scramble."""
    seen = 0
    for child in generation(WADA, 2000, FURTHER, random.Random(8)):
        unchanged_scheme = (
            child.wada_combination == WADA.wada_combination
            and child.role_layout == WADA.role_layout
        )
        if unchanged_scheme and child.role_permutation != WADA.role_permutation:
            neighbours = neighbouring_permutations(
                combination_by_id(child.wada_combination),
                child.role_layout,
                WADA.role_permutation,
            )
            assert child.role_permutation in neighbours
            seen += 1
    assert seen > 0, "no permutation ever moved, so this proved nothing"


def test_the_role_assignment_survives_a_change_of_combination():
    """The stickiness half of decision 10, and the thing that makes an alternate
    track worth choosing: picking a role assignment you like must not be undone
    by the next combination that comes along."""
    parent = CoverSpec(mode="wada", role_permutation=3)
    carried = kept_layout = 0
    for child in generation(parent, 2000, FURTHER, random.Random(12)):
        if (
            child.wada_combination != parent.wada_combination
            and child.role_layout == parent.role_layout
        ):
            kept_layout += 1
            carried += child.role_permutation == parent.role_permutation
    assert kept_layout > 20, "the combination never moved within one layout"
    # Carried whenever it stays legal; the rest are combinations that cannot
    # take permutation 3 at all, which fall back to the lowest legal one.
    assert carried / kept_layout > 0.5


def test_the_assignment_moves_more_rarely_than_the_combination():
    """Decision 10 asks for a *lower* rate, which is what keeps the current
    assignment reading as the default rather than as one option among six."""
    rng = random.Random(4)
    children = generation(WADA, 3000, FURTHER, rng)
    combination_moved = sum(
        1 for c in children if c.wada_combination != WADA.wada_combination
    )
    assignment_moved = sum(
        1
        for c in children
        if c.wada_combination == WADA.wada_combination
        and c.role_permutation != WADA.role_permutation
    )
    assert 0 < assignment_moved < combination_moved


def test_border_and_split_are_bred_in_classic_mode():
    """Phases 11 and 12 shipped these; phase 14 is what lets the chooser reach
    them. Breaking the mutation stream was accepted for exactly this."""
    children = generation(CoverSpec(), 600, FURTHER, random.Random(9))
    assert {child.border for child in children} > {"none"}
    assert {child.tile_split for child in children} > {"single"}


@pytest.mark.parametrize("count", [1, 2, 5])
def test_every_child_differs_from_its_parent_however_much_is_locked(count):
    """Decision 9, the requirement that makes decision 8's dark backgrounds
    recoverable: lock everything but colour, press Further, and every one of the
    five is a real alternative rather than a copy of what you already have."""
    base = CoverSpec(jitter=0.31)
    for locked in itertools.combinations(sorted(GENE_NAMES), count):
        children = generation(base, 5, FURTHER, random.Random(99), set(locked))
        assert all(child != base for child in children), locked


def test_the_difference_fallback_never_fires_when_nothing_is_locked():
    """What makes decision 9 cost nothing: the eight continuous knobs drift on
    every child, so an exact copy is unreachable until shatter and spacing are
    both held. Measured at 0 in 20,000."""
    base = CoverSpec()
    children = generation(base, 20000, FURTHER, random.Random(7))
    assert not any(child == base for child in children)


def test_locking_everything_still_yields_copies():
    """The one case decision 9 must NOT repair -- with nothing free there is
    nothing to force, and a refusal is the honest answer."""
    base = CoverSpec(jitter=0.31)
    assert generation(base, 5, FURTHER, random.Random(3), LOCKABLE) == [base] * 5


def test_the_colour_mode_is_never_bred(): 
    """Decision 5, and still true after the chooser gained a mode switch: the
    user crosses between aesthetics, breeding does not. A gene owning `mode`
    would make one Further button mean two incompatible things and leave the
    `colour` lock ambiguous about what it held."""
    assert not any("mode" in gene.fields for gene in GENES)
    for base in (CoverSpec(), CoverSpec(mode="wada")):
        for child in generation(base, 500, FURTHER, random.Random(2)):
            assert child.mode == base.mode


def test_an_additive_non_bred_field_does_not_disturb_the_stream_guard():
    """Phase 15's lesson, pinned. `box_corner` is a real field that no gene owns;
    a child inherits it unchanged, so it cannot be part of what a breed seed
    promises. If this ever fails, the digest has drifted back to hashing the
    whole spec and will cry wolf on the next additive field."""
    assert "box_corner" not in MUTABLE_FIELDS
    plain = CoverSpec()
    rounded = CoverSpec(box_corner=0.3)
    assert _spec_digest(plain) == _spec_digest(rounded)
    assert all(child.box_corner == 0.3
               for child in generation(rounded, 20, FURTHER, random.Random(1)))


def test_a_clipped_cover_keeps_its_overfill_while_breeding():
    """Decision 25's trap. `KNOB_RANGES` stops box_margin at 0.05, which would
    have dragged a solid cover back to a floating one on its first mutation."""
    from shatter.breed import CLIPPED_BOX_MARGIN_FLOOR

    spec = CoverSpec(clip_tiles=True, box_margin=-0.10)
    rng = random.Random(4)
    negatives = 0
    for _ in range(80):
        spec = mutate(spec, FURTHER, rng)
        assert CLIPPED_BOX_MARGIN_FLOOR <= spec.box_margin <= KNOB_RANGES["box_margin"][1]
        assert spec.clip_tiles is True
        negatives += spec.box_margin < 0
    assert negatives > 20, "the overfill drifted away and never came back"


def test_an_unclipped_cover_never_drifts_into_overfill():
    """The complement: widening the clamp must not change the default look."""
    spec = CoverSpec()
    rng = random.Random(4)
    for _ in range(200):
        spec = mutate(spec, FURTHER, rng)
        low, high = KNOB_RANGES["box_margin"]
        assert low <= spec.box_margin <= high


def test_clipping_is_not_a_bred_gene():
    """Decision 26, and the reason the chooser needs a control for it."""
    assert not any("clip_tiles" in gene.fields for gene in GENES)
    for base in (CoverSpec(), CoverSpec(clip_tiles=True)):
        for child in generation(base, 200, FURTHER, random.Random(2)):
            assert child.clip_tiles == base.clip_tiles


def test_the_grid_is_not_a_bred_gene():
    """Decision 29, and the reason the chooser needs a checkbox for it."""
    assert not any("grid_lines" in gene.fields for gene in GENES)
    for base in (CoverSpec(), CoverSpec(grid_lines=True)):
        for child in generation(base, 200, FURTHER, random.Random(2)):
            assert child.grid_lines == base.grid_lines
