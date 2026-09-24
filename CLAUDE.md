# CLAUDE.md — orientation for a new session

## What this is

`shatter` generates print-ready book covers: a **feature box** containing a
"shattered" aperiodic tiling — packed and intact in the centre, progressively
flung outward and rotated toward the rim, thinning into debris. It renders **no
text**; a collaborator sets the type afterwards.

It has **two colour models** and **two composition looks**, and knowing that up
front saves a lot of confusion.

The composition looks are one boolean apart: by default the flung tiles spill past
the feature box and float on the plain ground, and with `--clip-tiles` they are cut
dead at its edge. A *negative* `box_margin` overfills the box so the tiles reach its
corners — that plus clipping is the "solid" look. The two are independent on purpose
(§12.1 decision 24).

The colour models:

- **`classic`** (the default) — a plain pastel ground, a white or darkened box,
  tiles in one of three derived colours. Nine combinations in total. This is the
  house look and the aesthetic the project was originally specified around.
- **`wada`** (opt-in, `--mode wada`) — palettes drawn from Sanzo Wada's *A
  Dictionary of Color Combinations*: 159 colours across 348 combinations, mapped
  onto three **role layouts**, screened by a perceptual contrast floor. 3,392
  assignments in all.

Each model reads **only its own fields** on `CoverSpec`, which is why switching
between them is lossless and why breeding never crosses between them.

**[SHATTER_DESIGN.md](SHATTER_DESIGN.md) is the spec of record.** Long, but it is
the source of truth and it is kept current. Read section 12 (build plan) and
**section 12.1 — sixteen decisions, with their reasoning, recorded so they get
revisited rather than re-argued.** Several were *corrected by measurement* while
being implemented; the corrections are written up where the original claim was,
so re-deriving them from scratch will waste your time.

## Status

**Phases 0–18 are all built and nothing is half-done.** 435 tests pass, with a
37-image golden suite, and the last commit is a clean working state.

There is no next phase. §12.2's four later features — rounded corners, the colour
dial, the solid box and the sudoku grid — are all built, and their thirteen design
questions are settled as §12.1 decisions 17–29. What remains is in **§13 (open
items)** and **§14 (not building now)**, plus the short list below — none of it
committed work.

The grid (`--grid-lines`) is worth knowing about because its colour rule has two
branches: normally the lines take the **background** colour so the box reads as cut
into strips, but where the box already *is* the background — `box_color="bg"`, or
the Wada `shapes` layout, about a third of covers — they step away from it instead,
toward black or white by lightness. §12.1 decision 27 records why the obvious
simpler rules both failed.

## Working agreement with this user

**Fix the spec before writing code.** Audit the design doc against what the code
actually does, surface the drift, and agree decisions explicitly before
implementing.

This is not ceremony — **it has caught a real error every single time it has been
done.** Examples, all from the design doc, all found this way:

- §12 said to assign Wada colours "lightest to background". Measured against the
  classic default, that is backwards: the *box* is the lightest element. Fixing it
  is decision 10.
- §12 said "the dataset ships `lab` values; use them". They disagree with the
  dataset's own `rgb` by up to 20 dE and would have passed pairs that render
  nearly identically. Decision 13.
- §12 said to "reject **or reshuffle**" assignments failing the contrast floor.
  Under a uniform floor, reshuffling provably cannot help. Decision 11.

The same applies to claims *this* file and the design doc make — two of the above
were written confidently and were simply wrong. **Measure rather than assert**;
the user values a number over an argument, and several decisions record the
measurement that settled them.

The user is happy to be asked, and prefers **a recommendation with reasons** to a
menu of options. When a choice genuinely is theirs (a visual judgement, an
identity, a trade with no technical answer), ask directly and say which you would
pick.

## Getting oriented

```bash
.venv/bin/python -m pytest -q                        # 435 tests, ~18s
.venv/bin/shatter --help                             # or python -m shatter.cli

# see something, in each colour model
.venv/bin/shatter generate --zoom 60 --only front --out ./output/classic
.venv/bin/shatter generate --mode wada --zoom 60 --only front --out ./output/wada

# the breeding window: pick one, press Further, repeat
.venv/bin/shatter choose --mode wada
```

Four subcommands: `generate` (new layout + render), `render` (an existing layout
JSON), `contact` (breed a generation into a labelled sheet), `choose` (the
tkinter breeding window). `./output/` is gitignored.

To look at the Wada space without the GUI — the least discoverable thing here:

```python
import shatter.color as c
from shatter import wada
c.offered("box")                       # (combination, permutation) pairs that pass the floor
wada.combination_by_id(126).colors     # what is in one
c.assign_roles(wada.combination_by_id(126), "box", 0)   # role -> RGB
```

## Where things live

All new code is in `src/shatter/`. Nothing here is large; `color.py` and
`breed.py` are where the thinking is.

| file | what it owns |
|---|---|
| `color.py` | the six colour roles, both models, Lab maths, the contrast floor |
| `breed.py` | mutation rules, the six lockable genes, the radii |
| `wada.py` | loads the vendored dataset; stdlib only, knows nothing about colour |
| `dial.py` | the colour dial — an ordered, hue-sorted walk of the palette space; makes **no random draws**, which is why it disturbs no breed seed |
| `spec.py` | `CoverSpec` — the whole recipe for a cover, as one serialisable object |
| `render.py` | layout → Pillow image; receives a resolved `Palette` and does no colour reasoning |
| `autoshatter.py` | the parametric layout generator — "the look" lives here |
| `geometry.py`, `model.py` | centroids/bboxes/transforms, and the shared layout format |
| `dimensions.py`, `assemble.py` | trim/bleed/DPI/spine arithmetic, and the single output path |
| `contact.py`, `chooser.py` | thumbnails and sheets, and the tkinter window over `breed.py` |
| `cli.py` | argument parsing; every flag maps to a `CoverSpec` field |
| `data/` | the vendored Wada dataset **and its `SOURCE.md`** (MIT; keep them together) |

`src/covers/tiling/` is vendored and read-only — see hard rule 1.

## Hard rules

1. **Never edit anything under `src/covers/tiling/`.** Vendored verbatim from a
   sibling project and treated as read-only (design doc §2). Add behaviour around
   it, in `src/shatter/`.
2. **`tests/golden/` is a guard, not a convenience.** 37 reference PNGs, compared
   pixel-for-pixel. `python tests/make_golden.py` regenerates them — run it only
   when you have *decided* the output should change. Regenerating to turn a red
   test green destroys the guard while leaving the test in place, which is worse
   than having neither.
3. **Capture goldens BEFORE a change, never after.** They only prove anything if
   they predate it. This applies to the mutation-stream goldens in
   `test_breed.py` as much as to the images.
4. **New `CoverSpec` fields must be additive with a default.** `from_dict` raises
   on unknown keys, so a config written by an older version must still load.

## Git

The repo root is the project root — `pyproject.toml`, `src/` and `tests/` sit at
the top level, and `git add -A` is safe.

**This was not always true.** The project was developed inside a larger repo at
`/home/guy/scripts/python`, where it lived in a `shattered/` subdirectory
alongside about ten unrelated projects, and where `git add -A` would have swept
in all of them. The history here was rewritten with
`git filter-branch --subdirectory-filter` when the project was published, so
every commit before that point originally had a `shattered/` prefix. If you are
comparing against that old repo, that is why the paths differ.

The old copy may still exist on this machine. **This repo is the canonical one**;
changes made in the old location will not appear here.

## If you come back: what is deliberately not done

None of this is unfinished work — each was considered and left alone on purpose.

- **A third contrast tier** (§12.1 decision 16). Box-vs-background being close is
  benign — it just gives the medallion-on-plain-ground look — while a close
  tile-vs-box is fatal, yet the strict floor treats them alike. A third tier would
  admit roughly eight more `box` combinations. **Left alone because the offered
  pool is 3,392 assignments, nowhere near thin.** Do it only if the pool ever
  feels narrow in use.
- **The floor constants** (25 strict / 12 lenient) are confirmed, but only ever
  judged on screen — never in print. If a proof comes back muddy, look here first.
  The lenient one sits in a dead zone and needs no tuning; the strict one is a
  real trade, measured in decision 16.
- **Colour mode as a bred gene** (§12.1 decision 5). The chooser can switch models
  by hand, but `Further` never crosses between them, deliberately: one button
  would mean two incompatible aesthetics and `lock colour` would become ambiguous.
- **§13 open items** — box-aware vs radial shatter, a patch-rotation knob.
- **§14** — the interactive editor, and everything else consciously excluded.
- **Clicking a cover leaves the status line reading "Rendering..."** — `refresh()`
  sets that placeholder and only overwrites it when given a message, and `select()`
  passes none. Cosmetic, one line, noticed during phase 17 and deliberately not
  fixed in that commit to keep it focused.

## Gotchas that have already cost time

- **`"white"` is also a paper type** (`--paper white`, `dimensions.py`). A careless
  sweep of the colour strings silently changes spine-width arithmetic.

- **Adding a mutable gene breaks saved `--breed-seed` values.** The mutation stream
  shifts and a recorded seed stops reproducing its row. **This happened, once, at
  phase 14**, with all four colour genes batched so it happened once rather than
  four times; the stream goldens in `tests/test_breed.py` were re-recorded
  deliberately and say so. Mode-gating saved the `wada` draws but not `border` and
  `tile_split`, which apply in both models — read §12.1 decision 14 before adding
  another gene.

- **A guard can pass and still be worthless.** The stream golden used to record
  four children and six fields. A phase 14 prototype that shifted the stream for
  22 of 30 children *passed it*, because divergence began at child 4 and `zoom`
  happened to land on the same value. It now covers sixteen children and every
  field. When a guard matters, check that it actually fails on the thing it is
  guarding against.

- **Overlaps are ~0.02% of covered pixels at default knobs.** Any test or golden
  meant to exercise overlap colouring needs jitter turned up, or it passes for the
  wrong reason. Fixtures exist for this (`COLLIDING` in `test_render.py`).

- **The Wada dataset's `lab` field disagrees with its own `rgb`.** Upstream derived
  one from CMYK and re-converted the other, so they differ by up to 20 dE. Contrast
  is measured through `color.srgb_to_lab(rgb)`, never the shipped `lab` — which is
  why `WadaColor` does not carry it (§12.1 decision 13). Related trap: an **RGB
  midpoint is not a Lab midpoint**, so a half-way blend gives no guaranteed
  perceptual separation. The design doc claimed it did until a test disproved it.

- **A wada spec's classic fields are live but unread, and vice versa.** This is
  what makes the chooser's model switch lossless, but it also means a bred `wada`
  config carries whatever `bg` it started with. Do not "tidy" that by making the
  mutation write both — decision 15 is specifically about not doing that.

- **The mutation-stream digest hashes the *mutable* fields, not the whole spec**
  (§12.1 decision 19). Adding any new `CoverSpec` field used to change all 32
  digests even when the stream was untouched — `box_corner` did exactly that at
  phase 15 — which would teach you to re-record the guard without reading it. If a
  future change makes you want to hash `to_dict()` again, read decision 19 first.

- **`CoverSpec` is a plain dataclass, so it is unhashable.** `set()` and `dict`
  keys over specs raise `TypeError`; compare on `to_dict()` instead. It bites in
  tests more than in code.

- **`covers.tiling` has no colour code** and imports only the standard library.
  Prototile tags (`Polygon.tile_type`) survive every geometry transform, which is
  what made phase 12 cheap.
