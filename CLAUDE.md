# CLAUDE.md — orientation for a new session

## What this is

`shatter` generates print-ready book covers: a plain pastel background with a
**feature box** containing a "shattered" aperiodic tiling — packed and intact in
the centre, progressively flung outward and rotated toward the rim, thinning into
debris. It renders **no text**; a collaborator sets the type afterwards.

**[SHATTER_DESIGN.md](SHATTER_DESIGN.md) is the spec of record.** It is long but
it is the source of truth, and it is kept current — every phase below was written
up there as it landed. Read section 12 (build plan) and **section 12.1 (decisions
already settled)** before proposing anything; sixteen decisions are recorded there
with their reasoning specifically so they get revisited rather than re-argued.

## Working agreement with this user

**Fix the spec before writing code.** Audit the design doc against what the code
actually does, surface any drift, and agree decisions explicitly before
implementing. This has caught real errors every time — the doc has twice claimed
things the code did not do. The user is happy to be asked and prefers a
recommendation with reasons over a menu of options.

## Getting oriented

```bash
.venv/bin/python -m pytest -q          # 315 tests, ~8s
.venv/bin/python -m shatter.cli --help # or `shatter` (editable install)
```

Note on git: **the repo root is the parent directory**, `/home/guy/scripts/python`,
which also holds about ten unrelated projects (`aosiran/`, `todo/`, `turn-snake/`
and — importantly — `covers/`, the read-only reference of rule 1). Only
`shattered/` is tracked. **Never `git add -A`**; scope every add to this
subtree:

```bash
cd /home/guy/scripts/python && git add shattered/
```

The baseline commit is `53cf02a`, "Initial commit: shatter, through phase 13",
on `main`. There is no remote.

## Hard rules

1. **Never edit anything under `src/covers/tiling/`.** It is vendored verbatim
   from a sibling project and treated as read-only (design doc §2). Add behaviour
   around it, in `src/shatter/`.
2. **`tests/golden/` is a guard, not a convenience.** 27 reference PNGs, compared
   pixel-for-pixel. `python tests/make_golden.py` regenerates them — run it only
   when you have *decided* the output should change. Regenerating to turn a red
   test green destroys the guard while leaving the test in place, which is worse
   than having neither.
3. **Capture goldens BEFORE a refactor, never after.** They only prove anything if
   they predate the change.
4. **New `CoverSpec` fields must be additive with a default.** `from_dict` raises
   on unknown keys, so a config written by an older version must still load.

## Phase status

| # | Phase | State |
|---|---|---|
| 0–8 | Geometry, renderer, auto-shatter, full cover output, layout round-trip, tile labels, breeding engine, chooser window | done |
| 9 | Chooser locks — six lockable genes, `--lock` | done |
| 10 | Colour-model refactor — `color.py`, six-role `Palette`, verified no-op | done |
| 11 | Tile borders — `--border black\|white` | done |
| 12 | Two-colour tiles by prototile shape — `--tile-split by_type` | done |
| 13 | Sanzo Wada colour mode — `--mode wada`, three role layouts, contrast floor | done |
| 14 | Breeding the colour genes — mode-aware `colour` gene, decision 9 | done |

## What to do next

**The phase roadmap is complete — phases 0 through 14 are built.** There is no
"next phase"; what remains is in design doc **§13 (open items)** and **§14 (not
building now)**, and none of it is committed work. The live ones worth knowing:

- **A third contrast tier** (§12.1 decision 16). Box-vs-background being close
  is benign — it just gives the medallion-on-plain-ground look — while a close
  tile-vs-box is fatal, but the strict floor treats them alike. Loosening the
  first would admit roughly eight more `box` combinations. **Deliberately not
  done:** the offered pool is ~2,800 assignments, nowhere near thin. Do it only
  if the pool ever feels narrow.
- **The floor constants** are confirmed at 25/12 but were only ever judged on
  screen, never in print. If a proof comes back muddy, that is the first place
  to look.
- **Open items in §13** — box-aware vs radial shatter, a patch-rotation knob.

Before starting anything here, read **§12.1** first. Sixteen decisions are
recorded with their reasoning, several of which were *reversed* by measurement
during phases 13–14; re-arguing them from scratch will waste your time.

## Gotchas that have already cost time

- **`"white"` is also a paper type** (`--paper white`, `dimensions.py`). A careless
  sweep of the colour strings silently changes spine-width arithmetic.
- **Adding a mutable gene breaks saved `--breed-seed` values.** The mutation stream
  shifts and a recorded seed stops reproducing its row. **This happened, once, at
  phase 14**, with all four colour genes batched so it happened once rather than
  four times; the stream goldens in `tests/test_breed.py` were re-recorded
  deliberately and say so. Seeds from before phase 14 no longer reproduce.
  Mode-gating saved the *wada* draws but not `border` and `tile_split`, which
  apply in both modes — see §12.1 decision 14 if you are tempted to add another.

- **A guard can pass and still be worthless.** The stream golden used to record
  four children and six fields. A phase 14 prototype that shifted the stream for
  22 of 30 children *passed it*, because divergence began at child 4 and `zoom`
  happened to land the same. It now covers sixteen children and every field. When
  a guard matters, check it actually fails on the thing it is guarding against.
- **Overlaps are ~0.02% of covered pixels at default knobs.** Any test or golden
  meant to exercise overlap colouring needs jitter turned up, or it passes for the
  wrong reason. Several fixtures exist for this (`COLLIDING` in `test_render.py`).
- **The Wada dataset's `lab` field disagrees with its own `rgb`.** Upstream derived
  one from CMYK and re-converted the other, so they differ by up to 20 dE. Contrast
  is measured through `color.srgb_to_lab(rgb)`, never the shipped `lab` — which is
  why `WadaColor` does not carry it (§12.1 decision 13). Related trap: an **RGB
  midpoint is not a Lab midpoint**, so a half-way blend gives no guaranteed
  perceptual separation. The design doc claimed it did until a test disproved it.

- **`covers.tiling` has no colour code** and imports only the standard library.
  Prototile tags (`Polygon.tile_type`) survive every geometry transform, which is
  what made phase 12 cheap.
