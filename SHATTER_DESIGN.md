# SHATTERED-TILING COVER GENERATOR — DESIGN DOCUMENT

**Status:** Phases 0–7b are built and working. `shatter generate` produces finished
front, back and wrap PNGs, with the auto-shatter rule, tile gaps, overlap colouring
and print guides; `shatter render` re-renders a saved or hand-edited layout, with
`--label-tiles` for finding the tile you want to change, `shatter contact` breeds a
generation of variants for choosing by eye, and `shatter choose` opens the breeding
window. **Phase 9 (chooser locks) is built**: any of six genes can be held still
while the rest keep breeding, from the window or from `--lock`. **Phase 10 (the
colour-model refactor) is built**: `color.py` resolves every colour, the renderer
draws from a `Palette` of RGB and reasons about no colour strings at all, and an
18-image golden suite proves not a pixel moved. **Phase 11 (tile borders) is
built**: `--border black|white` outlines every tile at a width that tracks tile
size, so a chooser thumbnail shows the border the print will have. **Phase 12
(two-colour tiles) is built**: `--tile-split by_type` colours each prototile shape
separately, in every family. **Phase 13 (the Sanzo Wada colour mode) is built**:
`--mode wada` draws a cover's palette from one of Wada's 348 combinations, over
three role layouts, behind a two-tier perceptual contrast floor. **297 tests
pass**, with a 27-image golden suite.

**Phase 14 (breeding the colour genes) is built**, which is what makes phase 13
usable: `border`, `tile_split` and the Wada fields are all bred under the one
`colour` gene, and every child now differs from its parent however much is
locked. That last part is the condition decision 8 was granted on — you can lock
everything but `colour`, press Further, and climb back out of a dark ground.

**Phases 0–14 are complete.** See section 12 for the phases and **section 12.1 for
the sixteen decisions they were agreed against**, which is the part to read first
if you are picking this up cold.

**Phase 15 (rounded feature-box corners) is built** — `--box-corner`, a fraction of
the box's shorter side, 0.5 a stadium. **Phases 16 and 17 are proposed and not
started**: a colour dial for hunting through the palette space, and a solid box that
clips the tiles at its edge. Section 12.2 has all three, with the seven design
questions still open on 16 and 17 recorded as questions rather than answers.

**Working name:** `shatter` — the package name and the CLI command. (The repo
folder on disk is `shattered/`; only the *package* name matters to the code, so
the two need not match. If you rename the package, change it everywhere in
section 3.)

**Relationship to the previous project:** this is a *separate* project in its own
folder. It reuses the tiling-geometry engine from the sudoku-cover generator by
**vendoring** (copying) that package in unchanged — see section 2. It does **not**
reuse that project's colour, render, or layout code; those encode assumptions
(full-panel coverage, colour-by-prototile, Sanzo Wada palettes) that actively
work against this project's plainer, bounded-motif aesthetic.

**One narrow exception, added in phase 13.** The Wada *dataset* — the old project's
`assets/data/sanzo_wada_colors.json`, 159 named colours across 348 combinations —
is copied in as **package data under `shatter/`**, not under `covers/`. It is inert
data rather than code, and re-deriving it by hand would be absurd. Its loader is
**rewritten rather than copied**: the old `wada_data.py` reaches for
`covers.assets.REPO_ROOT`, a coupling this project has no reason to inherit, so the
new one loads through `importlib.resources` instead. The old project's colour,
render and layout *code* stays excluded exactly as above, and `covers/` stays
read-only.

`assets/data/SOURCE.md` is vendored alongside it, not left behind. The data is MIT
licensed (mattdesl/dictionary-of-colour-combinations, itself derived from
dblodorn/sanzo-wada) and digitises Sanzo Wada's *A Dictionary of Color Combinations*
(1933, public domain) — copying the data without its provenance and licence file is not
an option.


## 1. GOAL

Generate print-ready front/back book covers with a **plain pastel background** and
a **feature box** on the front cover containing a **"shattered" aperiodic tiling**:
the tiles in the centre are packed together in their true, intact pattern, and
toward the perimeter they progressively "break out" — displaced outward and
rotated — thinning into sparse debris at the edge. Tiles are rendered in white or
a darker shade of the background colour. No busy full-bleed pattern, no
multi-colour palette; the shatter is the single focal element.

**Everything in this section describes the `classic` colour mode, which stays the
default.** Phase 13 adds an opt-in `wada` mode built on multi-colour Sanzo Wada
schemes. That is a deliberate second register offered alongside this one, not a
replacement: with `wada` unselected, nothing above changes. The two coexist because
the plain look is still the brief, and a mode flag is the honest way to say so
rather than quietly loosening the paragraph above.

**Tiles are separated by a small gap.** Every tile is filled in the *same* colour,
so tiles packed edge-to-edge in the intact core would merge into one solid blob and
the pattern would be invisible exactly where it is supposed to read most clearly.
Each tile is therefore shrunk slightly about its own centroid before filling,
leaving a uniform background-coloured gap between neighbours — mortar between
bricks. This is not a decorative afterthought; without it there is no visible
tiling in the core. See section 8.

**This tool renders no text.** Title and subtitle are added afterwards by someone
else in a separate program. The front cover reserves a **plain title band** across
the top and places the feature box below it; the band is left as untouched
background. There is no `--title` flag and no text module.

**Variation comes from seeds, not from hand-placement.** A fresh seed costs about a
second and yields a completely new arrangement, so the primary workflow is *roll,
look, keep*. Hand-editing exists for the case where one specific cover is right
apart from a detail — see section 11. This is a deliberate reversal of the original
plan, which centred on an interactive editor; see section 14 for why.


## 2. REUSED CODE (VENDORED) — WHAT TO COPY AND THE RULES FOR IT

The **entire `tiling/` package** from the old project is copied into this one at
the exact `covers/tiling/` path, so the internal imports (`from covers.tiling.base
import ...`) resolve with **zero edits**. The files:

```
src/covers/tiling/__init__.py      (empty package marker)
src/covers/tiling/base.py          Tiling interface + Polygon + depth_for_target_count
src/covers/tiling/penrose.py       P3 (rhombus)
src/covers/tiling/penrose_p2.py    P2 (kite/dart)
src/covers/tiling/pinwheel.py      Pinwheel
src/covers/tiling/registry.py      name -> class, get_tiling()
```

An **empty `src/covers/__init__.py`** is also required (the old repo has one; it
makes `covers` a real package rather than a namespace package, which matters for
setuptools discovery). That's the whole copy list — nothing else from the old
project is needed. The KDP spine/bleed formula (the one other genuinely reusable
bit) is short and is re-specified fresh in section 9 rather than copied, so you
never have to reason about whether the old `dimensions.py` dragged any other
coupling along.

**Two hard rules for the vendored code:**

1. **Do not edit any file under `covers/tiling/`.** It's verified, finished, and
   treated as read-only. All new behaviour is added in code *around* it (section 3's
   `shatter` package), never by modifying it. Editing a vendored copy is exactly how
   two copies of shared code quietly diverge.
2. **To pull in a future upstream fix, re-copy the folder wholesale** — because you
   never edited it, a clean folder copy is a safe re-sync. (This is the one cost of
   vendoring instead of sharing a live package, and it's acceptable here because the
   engine is done and not changing.)

**What the engine gives you** (verified by reading *and running* the source): every
generator returns a flat `list[Polygon]` of tiles in local coordinates centred on
the origin, unrotated and unscaled. The package imports only the standard library —
no Pillow, no colour code, nothing outward-facing — so it drops in cleanly.


## 3. PROJECT STRUCTURE

```
shattered/                      (repo root)
  SHATTER_DESIGN.md             this file
  pyproject.toml
  src/
    covers/                     <-- VENDORED, DO NOT EDIT (section 2)
      __init__.py               (empty)
      tiling/
        __init__.py
        base.py
        penrose.py
        penrose_p2.py
        pinwheel.py
        registry.py
    shatter/                    <-- all new code lives here
      __init__.py
      geometry.py               centroids, bboxes, whole-tile extraction, inset, depth resolution
      model.py                  TileEdit, ShatterLayout (the shared data format)
      autoshatter.py            parametric layout generator (the "look" lives here)
      render.py                 layout -> Pillow image (fit-to-box, apply edits, coverage, fill)
      dimensions.py             trim size, bleed, DPI, KDP spine-width formula
      assemble.py               PrintJob + write_cover: the single output path
      spec.py                   CoverSpec: the whole recipe for a cover, as one object
      color.py                  the six colour roles: settings -> resolved RGB Palette
      wada.py                   loads the vendored Wada dataset (phase 13)
      data/
        sanzo_wada_colors.json  VENDORED DATA (section 2's narrow exception)
        SOURCE.md               its provenance and MIT licence; vendored with it
      breed.py                  mutation rules for the chooser (section 11.2)
      contact.py                thumbnails and labelled contact sheets
      chooser.py                the tkinter breeding window (phase 7b)
      cli.py                    `shatter generate` / `render` / `contact` / `choose`
  tests/
    golden/                     reference PNGs for the phase 10 no-op guard
    golden_specs.py             the specs they are rendered from
    make_golden.py              regenerate them -- deliberately, never to fix a red test
  output/                       generated files (gitignored)
```

`pyproject.toml` uses a src layout and finds **both** top-level packages under
`src/` (`covers` and `shatter`); a minimal setuptools config with
`package-dir = {"" = "src"}` and package discovery under `src` covers this. The
only runtime dependency is **Pillow**.

There is no `text.py` and no `assets/fonts/` — see section 1. There is no `editor/`
package — see section 14.


## 4. THE CENTRAL IDEA — ONE FORMAT, ONE RENDERER

The `ShatterLayout` is the pivot of the design. The auto generator emits one, a
human can edit one, and a single renderer turns any of them into the final image.
The canonical tile geometry (from the vendored engine) is never mutated; each
tile's movement is stored as a separate **`TileEdit`** layered on top.

```
     auto knobs ──> ShatterLayout ──> render.py ──> front.png / back.png / wrap.png
                          ^   │
                          │   └──> layout.json  (--emit-layout)
                          │              │
                          └──────────────┘   (hand-edit, then `shatter render`)
```

What matters is that the format **round-trips**: whatever wrote a layout, the same
renderer produces the output, so a hand-touched layout is not a second-class
citizen. That property is what keeps an interactive editor possible later without
any redesign (section 14) — but it is also what makes an editor *optional*, because
the JSON is directly editable today.


## 5. DATA MODEL (`model.py`)

```python
from dataclasses import dataclass

@dataclass
class TileEdit:
    dx: float = 0.0            # translation in PATCH units (see section 8)
    dy: float = 0.0
    rot: float = 0.0           # radians, rotation about the tile's OWN centroid
    hidden: bool = False       # dropped from the render (debris gaps, or hand delete)

@dataclass
class ShatterLayout:
    family: str                # "p2" | "p3" | "pinwheel"
    depth: int                 # subdivision depth actually used
    drop_partial_tiles: bool   # part of tile IDENTITY -- see below
    seed: int                  # provenance: which seed produced these edits
    edits: list[TileEdit]      # PARALLEL to the whole-tile list for the above
    # ...plus a to_dict/from_dict pair for JSON save/load.
```

**Tile identity = list index.** `edits[i]` corresponds to the *i*-th tile returned
by the whole-tile extraction. That ordering is deterministic (subdivision order is
fixed; P3's rhombus-merge groups into a dict, which preserves insertion order —
verified by running it), so index `i` is a stable handle **as long as `family`,
`depth`, and `drop_partial_tiles` all stay the same**.

`drop_partial_tiles` belongs in the layout for exactly this reason: toggling it
adds or removes P3's ~10 unpaired boundary triangles (see section 6) and shifts
every index after the first one, silently reassigning edits to the wrong tiles.
Changing depth is a genuinely different patch — regenerate the layout rather than
trying to migrate edits across depths.

**What the layout is and isn't.** A layout stores *geometry only* — which tiles
exist and where they have moved. Presentation parameters (background colour, tile
colour, tile gap, box geometry, DPI, trim) are **not** in it; they come from the
CLI or a `--config` file. So a layout plus a parameter set reproduces an image
exactly; a layout alone reproduces the *arrangement*. `seed` is stored for
provenance, not because the render re-derives anything from it — once the edits
exist they are absolute.


## 6. GEOMETRY (`geometry.py`)

- **Whole-tile extraction — use `outline_polygons(depth)`, NOT `generate(depth)`.**
  This is the single most important implementation note in the project. P3's
  `generate()` returns each rhombus as *two* Robinson-triangle halves (same colour,
  no stroke, seamless only because they never move relative to each other). In a
  shatter, where tiles drift apart, those halves would visibly split into triangles.
  `outline_polygons()` merges them back into true rhombi, and P2/Pinwheel don't
  override it (their tiles are already whole), so calling `outline_polygons(depth)`
  **uniformly across all three families** yields whole tiles every time. Measured:
  P3 depth 3 gives 130 triangles from `generate()` but 70 whole tiles from
  `outline_polygons()` — and 60 after the default partial-tile drop below, which is
  the number actually rendered.

- **P3 boundary tiles (watch-out #1).** P3's merge leaves outer-boundary triangles
  unpaired — they come back as 3-vertex polygons because they have no partner.
  Measured: **10** at depths 2 and 3, **20** at depth 4. (An earlier draft of this
  document claimed a constant 10 at every depth ≥ 2; that was wrong. Nothing depends
  on the count being constant — the filter is by vertex count — but don't build on
  the number.) They sit exactly on the perimeter, i.e. in
  the shatter zone. **Default: drop any non-rhombus (vertex-count < 4) tile for P3**
  for a cleaner, uniform-rhombus edge. **Scope this filter to P3 only** — Pinwheel's
  tiles are all legitimately 3-vertex, so applying it blanket-fashion silently
  deletes the entire Pinwheel patch. This is the `drop_partial_tiles=True` flag,
  and it is recorded in the layout (section 5).

- **Centroid = mean of a tile's vertices.** All three patches are centred on the
  origin (verified: bounding-box centres land on the origin to within ~0.04 patch
  units), so a tile's **distance from centre is simply the magnitude of its
  centroid** — no recentring needed. This distance drives the whole shatter effect.

- **Tile inset** — `inset_about_centroid(polygon, gap)` scales a tile about its own
  centroid by `1 - gap`, which leaves the centroid unchanged and so composes cleanly
  with rotation and translation. This is a uniform scale, not a true polygon erosion,
  so the visible gap is slightly narrower at a rhombus's sharp corners than along its
  long edges; that is acceptable and arguably looks better.

- **Patch bounding box** over the (kept) whole tiles, for the fit-to-box transform.

- **Depth resolution — do NOT pass a target straight to `depth_for_target_count`.**
  The engine's `tile_count()` counts what `generate()` produces, which for P3 is
  *triangles*, roughly twice the number of whole tiles the shatter actually draws;
  `--zoom 200 --tiling p3` would silently give ~100 visible tiles. Resolve depth
  against the real whole-tile count instead:
  1. Use `depth_for_target_count(tiling, target)` as a cheap **lower bound** — the
     whole-tile count is never greater than `tile_count`, since merging and
     dropping only ever reduce it.
  2. From that depth upward, call `whole_tiles(...)` and return the first depth
     whose actual count reaches the target, capping at the engine's
     `MAX_ZOOM_DEPTH`.
  This stays cheap because realistic targets (~100–1000 tiles) resolve at depth ≤ 4.

- **P2 is inflation (watch-out #2).** Each depth step recursively builds a larger
  surrounding structure while leaf tiles shrink by 1/phi, unlike P3/Pinwheel's
  fixed-size subdivision. In practice its patch bounding box *converges* rather than
  growing without bound (measured 2.00 → 2.24 → 2.31 over depths 1–3), so this is
  harmless given the fit-to-box transform. The real point stands: **don't assume
  tile size is comparable across families at the same depth** — resolve depth from a
  tile-count target, not by hardcoding a depth.


## 7. THE AUTO-SHATTER RULE (`autoshatter.py`) — WHERE THE LOOK LIVES

Given a family, a depth (resolved as in section 6), a seed, and the knobs below,
produce a `ShatterLayout`. For each kept tile:

1. **Normalised radius** `r = |centroid| / R_max`, where `R_max` is the largest
   centroid magnitude among kept tiles, so `r ∈ [0, 1]`.
2. **Intact core:** if `r <= core_fraction`, leave the tile untouched (empty
   `TileEdit`). This is the packed, recognisable centre.
3. **Break-out factor** for `r > core_fraction`:
   `s = ((r - core_fraction) / (1 - core_fraction)) ** falloff`
   — `s` ramps 0→1 from the core edge to the rim; `falloff > 1` keeps tiles calmer
   near the core and flings the outermost ones harder.
4. **Displacement:** push outward along the centroid direction by
   `s * max_push * R_max`, plus **seeded** random radial + tangential jitter scaled
   by `s`. **`max_push` and `jitter` are fractions of the patch radius, not raw
   patch units** — the three families have radii of roughly 0.9 (P3), 1.2 (P2) and
   2.8 (Pinwheel) at comparable depths, so an absolute push would mean something
   completely different in each.
5. **Rotation:** a **seeded** random angle in `[-max_rotation, +max_rotation] * s`.
6. **Debris gaps:** with probability `dropout * s`, set `hidden = True`, so the very
   outside thins out instead of forming a solid ring.

**Knobs** (all reproducible from `seed`). Defaults, chosen against a real render
sweep rather than guessed: `core_fraction` **0.6**, `falloff` **2.0**, `max_push`
**0.5**, `jitter` **0.12**, `max_rotation` **40°**, `dropout` **0.3**.

**Random draws are made for every tile, including intact ones.** Drawing only for
tiles that break out would tie the random stream to how many tiles fall inside the
core, so nudging `core_fraction` would re-roll the entire patch and scramble a
layout mid-tune. Drawing per tile means changing `core_fraction` only re-classifies
tiles; the debris you already liked keeps its character.

**The break-out is purely radial**, which makes the intact core a *disc* floating
inside a rectangular box — the intended medallion look for P2 and P3, whose patches
are roughly circular. **Pinwheel's patch is square**, so under the same rule its
core stays a square block and debris leaves through flat edges; a 40-cover gallery
confirmed it reads as a broken tile floor rather than a medallion. Treat that as a
distinct look, or give Pinwheel the box-aware variant in section 13.

Measured for reference: at `core_fraction 0.6` the intact core holds 34% of P3's
tiles, 60% of P2's and 49% of Pinwheel's — the same knob gives a visibly different
core size per family, so per-family default overrides may eventually be worth it.


## 8. RENDERING (`render.py`)

- **Library: Pillow**, raster at **300 DPI**, same rationale as the old project
  (covers flatten to raster anyway, and one lightweight dependency handles polygon
  fills and PNG export).

- **Transform order — edits happen in PATCH space, before the fit transform.**
  `TileEdit.dx/dy` are in patch units, so applying them *after* scaling to pixels
  would make them invisibly small. The pipeline per tile is:

  ```
  tiles = whole_tiles(family, depth, drop_partial_tiles)   # patch units, origin-centred
  fit   = fit_to_box(bbox(tiles), box_rect, box_margin)    # from the UNEDITED bbox

  for tile, edit in zip(tiles, layout.edits):
      if edit.hidden: continue
      p = inset_about_centroid(tile, tile_gap)
      p = rotate_about_centroid(p, edit.rot)
      p = translate(p, edit.dx, edit.dy)
      draw_polygon(fit(p))
  ```

  Computing `fit` from the **unedited** bounding box is deliberate: otherwise the
  patch would shrink to accommodate its own flying debris and the intact core would
  drift smaller as you turn `max_push` up. `fit` is a uniform scale plus a
  translation — no rotation. It also flips the y axis, since patches use maths
  convention (y up) and images do not.

- **Fit-to-box — the inverse of the old project's.** The old renderer scaled the
  patch *up* so it covered the whole panel at any rotation. Here you scale the
  patch's bounding box to fit *inside* the feature box **with margin**
  (`box_margin`, e.g. 12–18% of the box), and centre it — so the intact pattern
  deliberately does **not** reach the box edges, leaving room for debris and
  breathing space.

- **Corner radius** (`box_corner`, phase 15). 0 is the square box above; higher
  values round the corners, and **0.5 is a stadium** — the short ends become
  semicircles. It is a fraction of the box's **shorter side**, not a pixel count,
  so a chooser thumbnail and a 300dpi print describe the same shape; a radius in
  pixels could not do that. Values above 0.5 are capped rather than rejected at
  the renderer, because Pillow saturates there anyway and the cap is better owned
  here than left as an accident. At exactly 0 the old square drawing path is used
  unchanged, which is what keeps every golden captured before phase 15 valid.

- **The feature box** is a drawn rectangle on the front cover: fill it with white or
  a darkened shade of the background, then draw the shatter over it. Let broken-out
  tiles extend *past* the box border — debris escaping the frame is the effect. Its
  geometry is defined as fractions of the **trim** rectangle (not the bleed
  rectangle), offset by the bleed:

  - top edge at `title_band` (default **0.30**) of trim height — everything above is
    reserved plain background for the collaborator's text;
  - left and right edges inset by `side_margin` (default **0.10**) of trim width;
  - bottom edge inset by `bottom_margin` (default **0.10**) of trim height.

  At 6×9 in those defaults give a box of about 4.8 × 5.4 in. Keep the box and the
  title band clear of KDP's 0.25 in safe margin inside the trim.

- **Colour resolution lives in `color.py`, not here** (phase 10). `render.py`
  receives a `Palette` — six roles (background, box, tile A, tile B, border,
  overlap) already resolved to RGB — and draws with it. The settings described
  below are the *input* to that resolution and still travel on `RenderParams`;
  what changed is that no drawing code compares a colour string any more. Note
  `overlap` arrives as `None` rather than the string `"none"`, which is the
  renderer's switch between flat fills and coverage counting.

- **Tile colour** is deliberately trivial: `tile_color = "white" | "dark" | "bg"`,
  where "dark" = the background colour darkened (multiply RGB by ~0.7). No palette
  selection, no Sanzo Wada. `box_color` takes the same three values and must
  **contrast with `tile_color`** — the box fill is what shows through the tile gaps,
  so it is the "mortar" colour and the thing that makes the core legible. Defaults:
  white box, dark tiles.

  Setting `box_color = "bg"` makes the box **invisible** — it still governs where the
  patch sits and how big it is, but nothing is painted, so the cover reads as a
  medallion floating on plain pastel with the background showing through the tile
  gaps. This is a first-class option, not a degenerate case: it is the plainest look
  the tool offers and it suits the brief particularly well.

  **White tiles need a dark box or a deep pastel.** White on a very pale background
  (e.g. `#FCE8E6`) nearly vanishes; the gallery showed white tiles working well only
  against `box_color = "dark"` or a distinctly deeper `--bg`.

- **Overlapping tiles show a third colour.** Where two or more broken-out tiles
  cover the same pixel, the intersection is painted in `overlap_color` — the tiles
  read as translucent shards rather than opaque cut-outs. `"auto"` picks a colour
  one step darker than the tile, but **the step is not the same operation for both
  tile colours**: dark tiles darken again (`bg x 0.7²`), while white multiplied by
  white is still white, so white tiles instead blend halfway toward the background
  pastel. `"none"` disables the effect and restores flat opaque tiles; an explicit
  `#RRGGBB` overrides.

  Implemented by counting, not blending: each tile is rasterised into a coverage
  map (accumulated inside its own bounding box, so cost tracks tile area rather
  than tiles x canvas), then pixels with count >= 1 are painted in the tile colour
  and count >= 2 in the overlap colour. Only two levels — a triple overlap looks
  the same as a double.

  **Overlaps are rare with the default knobs** (~0.1% of covered pixels), because a
  purely radial push moves tiles *apart*. `jitter` and `max_rotation` are what make
  tiles collide; `jitter` around 0.4 makes the effect clearly visible.

  **With two tile colours, one overlap colour still covers every case** — A-on-A,
  B-on-B and A-on-B alike (section 12.1, decision 3). Each group gets its own
  coverage map and the maps are summed, so any pixel two groups both cover reaches
  count 2 and is overpainted with the overlap colour **regardless of the order the
  groups were painted in** — which is what keeps the split from reintroducing
  draw-order dependence. The "auto" overlap colour follows `tile_color`, so a
  split cover's overlaps match the unsplit one it was bred from.

  The one place order does show is `overlap_color = "none"`, where there is no
  third colour to reach for and opaque tiles must simply stack; `tile_a`'s group is
  painted first, so `tile_b` wins a shared pixel. That is what "opaque" means, and
  it is deterministic. Both behaviours are pinned by tests.

  **Known limitation:** at `tile_gap = 0` neighbouring tiles double-cover their
  shared edges, so the overlap colour paints seams along every join (up to 7 deep
  where vertices meet). Harmless in practice, since gap 0 renders the core as one
  solid blob and is not a setting worth using.

- **Two tile colours by prototile shape (phase 12).** `tile_split = "single" |
  "by_type"`, default `single`. Under `by_type` the tiles are bucketed on the
  engine's `Polygon.tile_type` tag and filled from two roles: the **first** tag in
  the family's declared `tile_types` takes `tile_a`, the other takes `tile_b`
  (classic mode reads `tile_color` and `tile_color_b`). That order is part of the
  contract — if it drifted, a saved cover would change colour on re-render.

  Every family declares exactly **two** prototile tags (p3 thin/thick, p2
  kite/dart, pinwheel cw/ccw) and every tile a patch contains carries one of them,
  **including P3's unpaired boundary triangles, which are tagged "thick"**. So
  `by_type` needs no per-family special case and never leaves a bucket empty.

  `tile_color_b` is read **only** under `by_type`, so setting it cannot disturb a
  cover that never asked to split — and splitting into the same colour twice is
  byte-identical to not splitting at all.

- **Tile borders (phase 11).** `border = "none" | "black" | "white"`, default
  `none`. Drawn as a second pass over the same shapes the fill pass used, so it
  composes with overlap colouring rather than replacing it. Black and white are
  absolute rather than derived from the background the way `dark` is: a border
  exists to separate a tile from its neighbour, so tying it to the pastel would
  defeat it.

  **`border_width` is a fraction of the median tile radius, not a pixel count**
  (default **0.12**). This is the whole difficulty of the feature. The same layout
  is drawn 170px wide in the chooser and 1800px wide for print; a fixed pixel width
  would vanish in the one and hairline the other, and the chooser would stop being
  an honest preview of what it prints (section 11.2). Measured across a 10x size
  range the drawn ratio holds at 0.107 / 0.139 / 0.121 / 0.121 against a 0.12
  target — the residual is integer rounding. Width is floored at 1px, because a
  border asked for and then silently not drawn is the worst outcome.

  **The border eats the tile, not the gap.** Pillow strokes a polygon outline
  *inside* the shape, so `tile_gap` keeps meaning exactly what it says below
  however heavy the border gets — measured at 0% of border pixels taken from the
  gap, against 43.5% for the same path stroked centred with `ImageDraw.line`. The
  one exception is `width == 1`, where a single-pixel path has no inside to sit on
  and straddles the boundary; that only arises on small thumbnails, where the gap
  is a pixel or two anyway. The natural failure mode at large widths is a thin
  rhombus filling solid with border colour, which is gentle and visible rather
  than silent.

- **Tile gap (required, see section 1).** `tile_gap` (default **0.08**) shrinks each
  tile about its centroid to `1 - tile_gap` of its size before filling, so
  neighbouring same-coloured tiles read as separate tiles rather than one mass. Too
  small reads as a blob; too large reads as confetti.

- **Antialiasing:** Pillow polygon fills are aliased, and rotated tile edges will
  show it. **Supersample** — render the panel at 2× (or 3×) and downscale with
  `LANCZOS` — for clean edges. Note that LANCZOS shifts flat colour by a level or
  two within a couple of pixels of a hard edge; that is the filter, not a bug, and
  tests should not assert exact pixel colours near edges.

- **Draw order (front):** pastel background → feature box → shatter tiles. Nothing
  else. The title band is simply the region no box is drawn in.

- **Tile density has a practical ceiling.** Past roughly 400 visible tiles the
  shatter stops reading as tiles and becomes texture; at `--zoom 900` it looks like
  spray. Useful as an effect, but not the default register.

- **Back cover:** plain pastel background only for v1 (the sister's brief is
  "plainer"). A small echoed motif on the back is a section-13 maybe, not now.


## 9. PHYSICAL SPEC & OUTPUT (`dimensions.py`, `assemble.py`)

Same print targets as the old project (re-specified here so nothing is copied):

- Default trim **6 in × 9 in**; configurable later.
- **Bleed 0.125 in** on all outer edges.
- **300 DPI** raster.
- **Spine width** computed from page count × a per-page-thickness constant, one
  constant per paper type (white / cream), per the standard KDP paperback formula.
  Keep the constants in `dimensions.py` alone so they're easy to correct if Amazon
  changes them. The spine is **plain background with no text** in v1, consistent
  with section 1 — spine text is the collaborator's job too.
- **Outputs are PNG, always.** `front.png`, `back.png`, and `cover_wrap.png`. No
  PDF, no layered formats. Everything this tool emits is handed to someone else for
  typesetting, so a plain raster anything can open beats a print container. The wrap
  is laid out **back | spine | front**, left to right, at trim + bleed + spine width
  — that order is what KDP expects (the front must land on the right-hand side).
  front/back don't need page count; only the wrap does (it's the only part with a
  spine).
- **Every PNG carries its resolution** in the file's `pHYs` metadata (Pillow's
  `dpi=` save argument), so the editing program places it at true physical size
  instead of guessing at 72 DPI. PNG stores this as integer pixels-per-metre, so
  300 DPI reads back as 299.9994 — expected, not a rounding bug.
- **The final KDP upload will still need a PDF**, because Amazon wants a print-ready
  PDF for paperback covers rather than an image. That export belongs to whoever adds
  the type — they finish the cover, so they produce the final file. Worth confirming
  against KDP's current requirements before the first real upload.


## 10. INTERFACE (`cli.py`)

Three subcommands. `generate` makes a new layout from knobs and renders it;
`render` renders a layout that already exists; `contact` renders many small
variants so you can choose one by eye.

```
shatter generate \
  --pages 120 --paper white --trim 6x9 \
  --tiling p3 --zoom 200 --seed 42 \
  --bg "#F2D9E6" --tile-color dark --box-color white \
  --overlap-color auto --tile-gap 0.08 \
  --border black --border-width 0.12 \
  --tile-split by_type --tile-color-b white \
  --core-fraction 0.6 --falloff 2.0 --max-push 0.5 --jitter 0.12 \
  --max-rotation 40 --dropout 0.3 \
  --box-margin 0.15 --title-band 0.30 \
  --only all --guides \
  --emit-layout layout.json \      # optional: also save the ShatterLayout
  --out ./output

shatter render layout.json \       # re-render a saved (possibly hand-edited) layout
  --bg "#F2D9E6" --tile-color dark --pages 120 --only all \
  --label-tiles \                  # optional: draw each tile's index, for hand-editing
  --out ./output

shatter contact \                  # breed a generation and sheet it for choosing
  --tiling p3 --count 10 --vary closer \
  --config parent.json \           # optional: breed from a saved spec
  --lock colour,tiling \           # optional: hold these genes still (section 12, phase 9)
  --breed-seed 5 --out ./output/contact

shatter choose \                   # the breeding window
  --lock colour \                  # optional: which lock checkboxes start ticked
  --breed-seed 5 --out ./output/chosen
```

- No `--title` / `--subtitle`: this tool renders no text (section 1).
- `--zoom` takes a target visible tile count and resolves to a depth via section 6's
  whole-tile count, **not** by calling `depth_for_target_count` directly;
  `--depth` stays available as a raw override.
- `--keep-partial-tiles` flips `drop_partial_tiles` off for P3 (default on).
- `--config file.json` loads a `CoverSpec` as the base; any flag passed explicitly
  overrides it. `--emit-config` on `generate` saves one. Spec-valued flags use
  `argparse.SUPPRESS` so an unset flag is absent from the namespace, which is what
  makes "config as base, flags on top" work without guessing at defaults.
- `--lock` takes a comma-separated list of gene names — `shatter`, `spacing`,
  `seed`, `tiling`, `colour`, `zoom` (section 12, phase 9). It is accepted by
  `contact` and `choose` only, since `generate` and `render` do not breed. `color`
  is accepted as an alias for `colour`, because every other colour flag in this CLI
  is spelled the American way. `contact` **rejects** `--lock` together with
  `--vary seed`: that mode only ever moves the seed, so a lock there is either inert
  or a request for N copies of one cover.
- `contact` takes `--count`, `--vary seed|closer|further`, and `--breed-seed` (a
  seed for the *mutation* RNG, distinct from the cover's own `--seed`). It prints
  the breed seed it used, writes `contact.png`, and saves `NN.json` per panel so any
  panel can be rebuilt with `generate --config`.
- `--only front|back|wrap|all` (default `all`) to build just one part. `wrap` and
  `all` require `--pages`, since the spine width depends on it; `front` and `back`
  do not.
- `--guides` additionally writes `cover_wrap_guides.png`, a reference copy marking
  trim, bleed, safe margin, the spine, and the title band, with a colour legend.
  Never a print output — it exists because the finished wrap is a flat pastel field
  in which the spine is invisible, so whoever sets the type otherwise cannot tell
  the three panels apart.

All presentation flags apply to `render` exactly as they do to `generate`, because
presentation is not stored in the layout (section 5). The only flags `render`
rejects are the auto-shatter knobs — those made the layout, and re-applying them
would mean generating a new one.


## 11. CHOOSING AND TUNING A COVER

Two workflows, and most of the time you want the first one. **11.2 chooses** a
design by breeding candidates and picking what you like; **11.1 tunes** a chosen
design by editing individual tiles.

### 11.1 Hand-tuning a layout

Hand-tuning works on the layout JSON directly, and the tooling exists to make that
practical rather than painful:

1. `shatter generate --emit-layout layout.json ...` writes the arrangement.
2. `shatter render layout.json --label-tiles ...` writes a reference PNG with each
   tile's **index drawn on it**. The index is the tile's position in `edits`, which
   is exactly what you edit.
3. Open `layout.json`, find that index, and change it. The useful edits are:
   - `"hidden": true` — remove a tile that spoils the composition. This is by far
     the most common fix.
   - `"dx"` / `"dy"` — nudge a tile, in patch units. The patch radius is around
     1.0, so 0.05 is a small shove and 0.3 is a big one.
   - `"rot"` — rotate a tile, in **radians** about its own centroid.
4. `shatter render layout.json ...` to see the result.

This covers deleting and nudging, which is most of what hand-work actually
consists of. It cannot do rubber-band dragging or live preview; if those turn out
to matter, section 14 is still open.

### 11.2 Breeding a cover — the chooser

Eight continuous knobs decide the look, and nobody can pick good values by reading
numbers. But anyone can point at the nicest of five pictures. So the chooser
replaces parameter-fiddling with **selection**: look at candidates, pick the best,
get variations of it, repeat until you like one.

```
  row 1   [ ][ ][*][ ][ ]     the generation you chose from
  row 2   [ ][ ][ ][ ][ ]     its children

  click a cover to select it
  lock: [ ]shatter [ ]spacing [ ]seed [ ]tiling [x]colour [ ]zoom
  colour model: ( ) classic  (*) wada
  [ Closer ]  small mutations around the selection
  [ Further ] large mutations around the selection
  [ Print! ]  render the selection full size
```

**The colour model** converts the selected cover between the two aesthetics
(phase 13). It reports the *selection's* model rather than a window-wide setting,
so clicking between covers shows which each one is, and converting one leaves its
neighbours alone — which means a row can hold the same shatter in both models
side by side. Switching is free in either direction: each model reads only its own
fields (decision 15), so a classic cover's settings survive a trip through `wada`
untouched. It is **not** a gene — see decision 5.

**Locking** (phase 9) holds a gene still while everything else keeps rolling — tick
`colour` to hunt for an arrangement without the palette wandering, tick `tiling` and
`zoom` to explore the shatter knobs within one register. See phase 9 for the six
genes and for why a locked gene still makes its random draws.

Picking Closer or Further promotes the current children to row 1 and breeds a new
row 2 from the selection, so the window always shows *where you came from* and
*where you could go next*.

**The genome is a `CoverSpec`** (`spec.py`) — family, zoom, seed, the six
auto-shatter knobs and the presentation settings, as one serialisable object. It is
the same thing `--config` saves and loads, so anything bred is reproducible on the
command line.

**What mutates, and what deliberately does not:**

- **Mutated:** the six shatter knobs, plus `tile_gap` and `box_margin`. Each is
  nudged by a gaussian scaled to that knob's own sensible range and clamped to it,
  so a knob near its limit stays legal.
- **The seed mutates by probability, not always.** This is the subtle part: the
  seed drives every per-tile random draw, so re-rolling it changes the arrangement
  *completely* no matter how small the other mutations are. If every child got a
  new seed, "Closer" could not be close. So Closer re-rolls the seed rarely and
  Further re-rolls it often — that probability is most of what the two buttons
  actually mean.
- **The major genes move only under Further**, and only sometimes: `family`,
  `zoom`, and the palette (background plus the tile/box colour pair, mutated
  together). Each has its own per-child probability, tuned so a row of five
  averages **1.8** children that jumped and only about 9% of rows are all-minor.
  That is the balance the buttons need: Closer converges because nothing major
  moves, Further keeps offering a way out of a local rut without the row ceasing
  to resemble its parent.
- **A major mutation never re-picks the current value.** With only five slots, a
  "mutation" that lands back on the same family wastes one.
- **Palette choices are curated, and the pair moves together.** Backgrounds come
  from a fixed list of pastels rather than random hex, which would wander out of
  the register and produce near-white grounds that swallow white tiles. The
  tile/box pair is drawn from combinations where **the two differ** — the box fill
  is what shows through the tile gaps, so equal values mean invisible tiles.
- **Not mutated at any radius:** the title band and side/bottom margins, because
  that composition is the space the collaborator sets type into and it must stay
  put. Nor `overlap_color`, which is "auto" and already follows whatever tile
  colour is chosen.
- **Zoom mutation clears any explicit `depth`**, which would otherwise override
  zoom and make the mutation invisible.

**Reproducibility.** Print! writes the cover PNGs, the `ShatterLayout`, *and* the
`CoverSpec` config, so a bred design can be regenerated, hand-tuned via 11.1, or
re-bred later. A cover you can't get back is not much use.

**Built in two halves** (section 12), because the interesting logic and the risky
part are separable: the breeding rules and the contact-sheet rendering are pure
functions that can be tested properly, and the tkinter window is a thin shell over
them. If the window disappoints, `shatter contact` still delivers the same search
one generation at a time.


## 12. BUILD PLAN

Phases 0–4 are **done**. Each remaining phase ends with a concrete check.

**Phase 0 — Scaffold.** *(done)*
`src/covers/__init__.py`, `pyproject.toml`, `.gitignore`, `src/shatter/` package,
editable install.

**Phase 1 — Geometry + data model.** *(done)*
`geometry.py` and `model.py`, with the P3 partial-tile filter, the whole-tile depth
resolver, and JSON round-tripping.

**Phase 2 — Renderer, front panel.** *(done)*
`render.py`: fit-to-box, patch-space edits, tile gap, supersampling.

**Phase 3 — Auto-shatter generator.** *(done)*
`autoshatter.py` and `shatter generate`. Defaults tuned against render sweeps.

**Phase 4 — Full cover output.** *(done)*
`dimensions.py`, `assemble.py`, back panel, wrap PNG, `--guides`, `--pages`,
`--paper`, `--only`. Overlap colouring was added here too, out of sequence.

**Phase 5 — Round-tripping a layout.** *(done)*
`shatter render layout.json`, reusing every presentation flag and output mode
`generate` supports. Both commands share one `write_outputs` pipeline. Verified:
re-rendering an untouched layout is byte-identical across front, back and wrap;
hiding one tile by hand changes exactly one tile-sized region.

**Phase 6 — Making hand-editing practical.** *(done)*
`--label-tiles` on `render` writes `front_labels.png` with each visible tile's
index drawn at its centroid. A separate file, so `front.png` stays a clean print
asset. `placed_tiles` now returns `(index, polygon)` pairs, because once hidden
tiles are dropped, position in the list is no longer the tile's identity.
Verified: the index shown on a label is the one that vanishes when hidden.

**Phase 7a — The breeding engine (no GUI).** *(done)*
`spec.py` (`CoverSpec`, JSON save/load, conversion to the existing param objects),
`breed.py` (knob ranges, `mutate`, `generation`, the Closer/Further radii),
`contact.py` (thumbnails and labelled sheets), `--config` on `generate`, and
`shatter contact` to render one generation as a sheet plus a config per panel.
All pure logic, fully testable, and useful on its own.
*Check:* mutating with radius 0 is a no-op; every mutated knob stays inside its
range however many generations you run; Closer changes the seed rarely and Further
often; `shatter contact` writes a labelled sheet whose panel N is reproduced
exactly by `generate --config <panel N>.json`.

**Phase 7b — The chooser window.** *(done, basic version)*
`chooser.py` (tkinter): two rows of five thumbnails, click to select, Closer /
Further / Print!. Thumbnails are real renders shown small, so what you pick is what
prints. Print! writes the cover PNGs, the layout and the config.
*Check:* breed several generations, print one, and `generate --config` on the saved
config reproduces that exact cover.

**Phase 8 — Polish (optional, later).**
Box-aware (non-radial) shatter, especially for Pinwheel; true constant-distance tile
erosion instead of centroid scaling; back-cover echo motif; rounded box corners;
additional trim sizes. (Curated Wada backgrounds used to be listed here; phase 13
supersedes that with something considerably more deliberate.)

---

Phases 9–14 below are **planned, not built.** They deliver two things: *locking*
genes in the chooser, and a much wider *colour* space. Read section 12.1 first — it
records the decisions these phases assume, so that they can be revisited rather than
re-argued.

**Two facts make this cheaper than it looks, both verified by running the code:**

1. **`Polygon.tile_type` already exists and already survives the pipeline.** The
   vendored engine tags every tile with its prototile type, and `inset_about_centroid`,
   `rotate_about_centroid` and `translate` in `geometry.py` all preserve the tag.
   Every family has exactly **two** types (p3 thin/thick, p2 kite/dart, pinwheel
   cw/ccw). Colouring by tile shape therefore needs **no geometry work whatsoever** —
   the information is sitting there unused.
2. **None of this touches `ShatterLayout`.** Colour and borders are presentation,
   which section 5 deliberately keeps out of the layout. So there is no layout
   migration, no tile-identity risk, and every `layout.json` already on disk keeps
   rendering. The blast radius is `spec.py`, `render.py`, `breed.py` and `cli.py`.

**Phase 9 — Locking genes in the chooser.** *(done)*
Thread a `locked: frozenset[str]` through `breed.mutate` and `breed.generation`, add
a row of checkboxes to `chooser.py`, and add `--lock a,b,c` to `shatter contact`.
Locked genes are simply skipped by the mutation, so the child inherits the parent's
value exactly.

It was built **first**, before any colour work, even though it is the second idea
chronologically. It is independent of everything else, and phases 11–13 are all tuned
by eye through the chooser — locking pays for itself the moment you start breeding
against a fixed palette or a fixed tiling.

**Locked genes still make their random draws, and the result is discarded.** This is
the one non-obvious decision in the phase, and it was added during the build. Skipping
the draws would shift the random stream, so locking the tiling would silently re-roll
every shatter knob too — locking one thing would scramble everything else, which is
the opposite of what the button is for. It is the same reasoning as section 7's
"random draws are made for every tile, including intact ones": a lock should
**re-classify what moves, not scramble what didn't**. Verified on real output — a
`--vary further` row bred with `--lock colour,tiling` has bit-identical
`core_fraction` and seeds to the same row bred unlocked.

*The gene registry.* Do not write this as a chain of `if "family" not in locked`.
Define the genes as **data** — a dict of gene name -> the spec fields it owns and how
it mutates — and have `mutate` walk it. It is barely more work than hardcoding, and
it is what makes phase 14 nearly free. The six genes (section 12.1, decision 1):

| gene      | owns                                                                  |
|-----------|-----------------------------------------------------------------------|
| `tiling`  | `family`                                                              |
| `zoom`    | `zoom` (and clears `depth`, which would otherwise mask the mutation)   |
| `colour`  | the whole palette, moved as one unit — see phase 14 for what that grows to |
| `seed`    | `seed`                                                                 |
| `shatter` | `core_fraction`, `falloff`, `max_push`, `jitter`, `max_rotation`, `dropout` |
| `spacing` | `tile_gap`, `box_margin`                                              |

*Locks live in the chooser, not in `CoverSpec`.* A spec describes a cover; a lock
describes how you are searching. Putting locks in the spec would write them into every
`--emit-config` and make a saved cover claim something about a breeding session that
has nothing to do with reproducing it.

*The degenerate case is real and must be handled.* Lock everything a button can move and
every child is byte-identical to the parent. Detect it and say so rather than breeding a
row of copies — and **refuse the breed**, which also leaves the children already on screen
in place instead of wiping them.

*Corrected after phase 12:* the first cut of this only fired when **all six** genes were
locked, which was wrong. `Closer` moves only the minor genes by design (section 11.2), so
it goes inert with just `shatter`, `spacing` and `seed` held — three locks, not six. Each
gene now records which `Radius` field gates it, `movable_genes(radius)` reports what a
radius can actually move, and the window names those genes when it refuses.
*Check (passed):* for every gene, 60 children bred locked differ from the same 60 bred
free **only** in that gene's own fields — which pins the freeze and the stream alignment
in one assertion. Locked knobs survive 40 compounding generations. Locking nothing
reproduces the pre-phase-9 stream exactly, verified across 300 breed seeds x both radii.
Locking all six yields exact copies of the parent, reported in the status bar rather
than forbidden.

**Phase 10 — The colour-model refactor.** *(done; no visible change, by design)*
This phase adds **no feature**. That is the point of it: phases 11, 12 and 13 all push
against the same wall, and doing them one at a time means rewriting `resolve_color`,
`render_front`, `breed.PALETTES` and the CLI colour flags three separate times.

Today colour is three string fields (`bg` as hex, `tile_color` and `box_color` each one
of `white`/`dark`/`bg`) resolved by a seven-line function, and `render_front` paints from
a single coverage map in a single tile colour. Replace that with a `ColorScheme` in a new
`color.py` that resolves to concrete RGB for **six roles**:

```
background | box fill | tile fill A | tile fill B | border | overlap
```

`render.py` stops reasoning about the strings `"white"`, `"dark"` and `"bg"` entirely and
takes resolved RGB. The strings survive only as *input* to the classic mode's resolver.

*Settings stay flat; only the result is an object* (section 12.1, decision 6). `CoverSpec`
keeps `bg`, `tile_color` and `box_color` as plain fields and gained `mode` the same way;
`color.py` owns the `Palette` of six resolved RGB values and the function that fills it.
Nesting the settings into a scheme object was considered and rejected: it would nest the
config JSON, and phase 9's gene registry addresses flat field names through
`dataclasses.replace`, so every colour mutation would have grown nested-path handling.

*Compatibility was the whole risk.* `CoverSpec.from_dict` raises on unknown keys, so every
new field is **additive with a default** — a config written before `mode` existed loads
untouched, verified directly. Nothing was renamed or removed.

*Two roles are carried but not yet drawn.* `tile_b` equals `tile_a` in every mode that
does not split tiles by shape (phase 12), and `border` is `None` (phase 11). They are in
the dataclass so those phases add a filling rule rather than a new parameter path.

*Check (passed):* **14 golden PNGs**, captured from the pre-refactor renderer and compared
pixel-for-pixel. They cover all six legal tile/box pairs, all three overlap modes, all
three families and a wide gap. The guard was itself tested by nudging `DARKEN_FACTOR` from
0.7 to 0.699: **7 of 15 goldens failed**, the smallest catch being *3 pixels differing by
one channel level*. Comparison is on decoded pixels rather than file bytes, so a Pillow or
zlib encoder change cannot cry wolf and get the guard regenerated away.

*One trap found while doing it, recorded for the next person:* `"white"` is also a **paper
type** (`--paper white`, `dimensions.py`). A careless sweep of the colour strings changes
spine-width arithmetic. And `classic_overlap` has a `tile_color="bg"` case that section 8
never documented; it is preserved deliberately and now pinned by a test.

**Phase 11 — Tile borders.** *(done)*
`border` becomes a scheme field taking `none` (today's look, the default), `black` or
`white`. Drawn as a second pass over the same shapes the fill pass already computes, so
it composes with the coverage-map path rather than replacing it.

*Border width is scale-invariant, and that was the trap.* A width in pixels is invisible
in a 170px chooser thumbnail and a hairline on an 1800px print panel — which would make
the chooser **lie about the output**, defeating the point of picking by eye (section 11.2:
"thumbnails are real renders shown small, so what you pick is what prints"). It is a
fraction of the **median tile radius in pixels**, computed per render: median across tiles
because the outermost debris is no guide to the core, and mean-of-vertices within a tile
because a rhombus's two half-diagonals differ wildly and the long one says nothing about
how thick the tile is.

*The mortar worry turned out not to exist, and the measurement is the reason.* Pillow's
`ImageDraw.polygon(outline=..., width=...)` strokes **inside** the shape — verified by
rasterising a square and reading back where the black pixels fell — so the border consumes
the tile's own fill, not the gap. Measured at a 5px width it takes **0%** of its pixels
from the gap, where the obvious alternative of stroking the path centred with
`ImageDraw.line` takes **43.5%**. So `tile_gap` keeps its meaning at any border weight,
and **no clamp against `tile_gap` is needed** — which retires that open item in section 13
rather than deciding it. (At `width == 1` a single-pixel path has no inside to sit on and
does straddle the edge, costing the gap about 15% of the border. That only happens on
small thumbnails, where the gap is a pixel or two anyway.)

*Not bred yet, deliberately.* `border` and `border_width` are reachable from `--border`
and from a config, but the chooser does not mutate them until phase 14. Every new mutable
gene shifts the mutation stream and stops a saved `--breed-seed` reproducing its row, so
all the new colour genes go in together as one break rather than four.

*Check (passed):* border ratio holds at 0.107 / 0.139 / 0.121 / 0.121 across a 10x size
range against a 0.12 target; width never rounds to zero; a bordered render contains the
border colour and a borderless one does not; and the count of gap-coloured pixels is
**exactly equal** with and without a border, which is the mortar claim stated as an
assertion. Four new goldens, including one where borders are drawn over the overlap
composite — the only place the two passes meet.

**Phase 12 — Two-colour tiles by prototile shape.** *(done)*
`tile_split` takes `single` (today) or `by_type`. Under `by_type`, tiles are partitioned
on `Polygon.tile_type` and filled from roles *tile fill A* and *tile fill B*. Because
every family has exactly two types, A and B always both mean something; no family needs a
special case.

*The tag was already there, which is why this was cheap.* `Polygon.tile_type` survives
`inset_about_centroid`, `rotate_about_centroid` and `translate` untouched, so the only
plumbing needed was for `placed_shapes` to stop discarding it. It now returns a
`PlacedTile` (index, tile_type, points) rather than a bare pair — the index still being
the hand-editing handle from section 11.

*Overlaps.* Per section 12.1 decision 3, **any** pixel covered twice or more gets the one
overlap colour, regardless of which shapes collided. One coverage map per group, summed,
keeping the two-level rule. Distinguishing A-on-A from A-on-B was considered and rejected:
overlaps are ~0.1% of covered pixels at default knobs, so three extra colours would buy
almost nothing and would complicate phase 13's role assignment.

*On draw order — the earlier draft of this phase overstated the problem.* With overlap
colouring **on**, summing the coverage maps makes the result order-independent by
construction: a pixel both groups cover reaches count 2 and is overpainted either way.
Verified by rendering the groups in both orders and comparing bytes, on knobs tuned to
make the two groups genuinely collide (the test asserts the collision exists, so it cannot
quietly become vacuous). With overlap colouring **off**, there is no third colour to reach
for and opaque tiles must stack; that order is visible, and the requirement is only that
it be deterministic, which it is.

*Check (passed):* group sizes match `Counter(tile_type)` for the patch, in all three
families; the first declared tag takes `tile_a`; splitting into the same colour twice is
**byte-identical** to not splitting; `tile_color_b` alone changes nothing; four new
goldens including one where a split, a border and an overlap region all meet.

**Phase 13 — The Sanzo Wada colour mode.** *(done)*
The largest phase. `mode` takes `classic` (default, unchanged) or `wada`. Vendor the
dataset per section 2's narrow exception and write `wada.py` to load it through
`importlib.resources`.

The dataset is a remarkably good fit for what was asked, and the arithmetic is worth
recording: **348 combinations, split 120 of two colours, 120 of three, 108 of four.**
*(Re-verified against the data before phase 13 began: 348 combination ids, contiguous
1–348, sizes 120/120/108, across 159 uniquely-named colours. The figures below were
measured the same way, not estimated.)* So the three requested groupings map straight
onto the six roles from phase 10:

| combination size | `role_layout` | roles filled                          |
|------------------|---------------|---------------------------------------|
| 3                | `box`         | background, feature box, tiles *(tile_split=single)* |
| 3                | `shapes`      | background, tile shape A, tile shape B *(box invisible, `box_color=bg`)* |
| 4                | `full`        | background, feature box, tile shape A, tile shape B |

Both three-colour layouts are offered and the breeder chooses between them
(section 12.1, decision 7), so `role_layout` is a field of the spec and part of the
`colour` gene — not a mode set once at launch.

*Role assignment is the actual design problem here.* A Wada combination is an unordered
bag of colours with no roles attached. Assign them **by lightness, in the order that
reproduces the house look** — lightest to the box, then the background, darkest to the
tiles; and for `shapes`, where the box is deliberately invisible, lightest to the
background and the remaining two to the tiles. That ordering is `role_permutation = 0`
(**decision 10**, which corrects an earlier draft of this section that sent the lightest
colour to the background — measurement showed that is backwards for the house look).
A `role_permutation` integer carried alongside keeps every other assignment reachable
(decision 8); it indexes **all k! orderings**, not only the ones that pass the contrast
floor (**decision 12**), which is what keeps a saved config reproducible. That is what
turns 348 combinations into a space big enough to be worth breeding through, and it makes
the permutation a gene in its own right (phase 14).

*A contrast floor is mandatory, not polish.* With arbitrary colours you will land on
background ≈ box, or tile ≈ box, and draw an invisible tiling. Section 8 already flags
this hazard for the existing three-value scheme, where only nine combinations exist;
with 348 it stops being a corner case. The floor is **two-tier** (**decision 11**):
strict between any (background, box, tile) pair, lenient between `tile_a` and `tile_b`.
A uniform floor would make the word "reshuffle" meaningless — the multiset of pairwise
distances does not change when you permute the roles, and 0 combinations were rescued by
reshuffling at any uniform threshold tried. Measure distance in Lab **recomputed from
the shipped `rgb`**, not read from the shipped `lab` field (**decision 13**).

*`overlap_color = "auto"` must be re-specified.* It currently branches on
`tile_color == "white"` (section 8), which is meaningless once the tile is an arbitrary
RGB. Replacement: blend `tile_a` **halfway to the box colour**. It follows `tile_a`
because one overlap colour covers every kind of overlap (decision 3) and following the
first tile is what classic mode already does.

The obvious corollary — that half-way blending puts the overlap half the strict floor
from its tile — is **false**, and worth recording as such: an RGB midpoint is not a Lab
midpoint, so the separation does not follow from the floor. What is true is measured:
across every assignment the three layouts offer, the overlap sits **10.7 to 31 dE from
its tile, median ~30**, against a just-noticeable difference of about 2.3. So it is
reliably visible, but by measurement rather than by construction, and a test pins it.
Classic mode keeps its existing branch untouched.

*The CLI surface does not exist yet.* `mode` has been a `CoverSpec` field since phase 10,
but no flag reaches it — phase 13 is where it becomes usable. Add `--mode`,
`--wada-combination`, `--role-layout` and `--role-permutation`, plus `choose --mode wada`
(decision 5: the mode is chosen when the chooser launches, never bred).

*Check (passed):* every combination the mode **offers** passes the contrast floor --
checked exhaustively, not sampled; a cover generated in `wada` mode reproduces exactly
from its saved config, and still does after the floor constants are moved (decision 12);
`role_permutation = 0` puts the lightest colour on the box, not the background, for all
120 three-colour and 108 four-colour combinations; the 22 pre-existing goldens are
byte-identical, so classic mode did not move; five new goldens, one per role layout plus
a permuted one and the busiest path (split, border and overlap at once).

*Measured while building it,* and worth keeping: the floor admits 106/120 `box`,
120/120 `shapes` and 103/108 `full` combinations, and a dark background does reach the
offered set, so decision 8 survives contact with decision 11.

**Phase 14 — Breeding the new genes.** *(done)*
Register `border`, `tile_split`, the Wada combination and `role_permutation` in phase 9's
gene registry, all under the existing `colour` gene so that one lock still means one
intuitive thing. `role_permutation` is the one needing care: per decision 10 it draws
**independently of the combination and at a lower rate**, and moves by a single
transposition. **Set that rate here by measurement** — report how many of five children
keep the parent's permutation, and pick a rate that leaves the house look dominant within
a row while still turning up an alternate within a few generations. Do not choose the
constant by taste; decision 9 was settled the same way.

*What the pre-implementation audit changed here.* Three things, all recorded as
decisions 14-16. The `colour` gene becomes **mode-aware** rather than gaining fields
(decision 15), and must move the Wada *(combination, layout, permutation)* triple
together because a layout and a combination have to agree on size. The classic mutation
stream **breaks once, deliberately** (decision 14) — mode-gating saves it from the Wada
draws, but not from `border` and `tile_split`, which apply in both modes. And the
contrast floor constants were confirmed rather than changed (decision 16), so
`offered()` is a stable pool to breed against.

Treat this as **part of phase 13's definition of done, not as optional polish.** Phase 13
opens a space of hundreds of combinations times permutations times border styles; without
breeding, the only way to explore it is to type combination numbers in by hand, which is
precisely the parameter-fiddling the chooser exists to abolish (section 11.2).

**Locking must redistribute the mutation budget — this is a requirement, not polish.**
Section 12.1 decision 8 allows dark Wada backgrounds on the understanding that the
ordinary tools can get you back to a light one. The obvious route is to lock everything
except `colour` and press Further until a light ground turns up. **Measured on the shipped
phase 9 behaviour, that route barely works:** with the other five genes held, Further
changes only **0.89 of 5** children per row and **38% of rows are five identical covers**,
because `palette_probability` is 0.18 per child and was tuned (section 11.2) on the
assumption that every gene is free.

**The fix is section 12.1's decision 9:** guarantee every child differs from its parent,
by forcing one still-free gene to mutate when the ordinary draws produce an exact copy.
A lock should change *what* varies, not *how much* varies — the same principle as phase
9's "a locked gene still makes its random draws".

Worth knowing where the cliff actually is, because it is not where it looks. The eight
continuous knobs drift on **every** child while the major genes move only sometimes, so
locking is nearly free until the always-on genes go: measured differing-children-per-row
of 5.00 with nothing locked, 5.00 with `colour` locked, 4.35 with `shatter`+`spacing`,
then **1.77** once `seed` joins them and **0.88** with everything but `colour` held.

Also update `contact.describe()`, which currently reports only family, seed and three
shatter knobs. Once the palette is what varies between two panels, a caption that cannot
tell them apart is worse than no caption. *(Done: it now carries a second line naming the
combination, layout and permutation in wada mode, or the pastel and tile/box pair in
classic, plus the border when there is one.)*

*One correction the implementation forced,* recorded because it is the kind of thing that
reads fine in a design and fails in use. Decision 15 says the *(combination, layout,
permutation)* triple moves together, and a first cut drew all three from the offered pool
at once — which quietly destroyed decision 10. At `palette_probability` 0.18 that
re-randomised the role assignment roughly every fifth child, so an alternate track could
never be held long enough to choose, which is the one thing decision 10 exists to
provide. The permutation is therefore **carried across a change of combination** whenever
it stays legal; only a change of *layout* resets it, because three roles becoming four
makes the index mean something else. See `breed._carry_permutation`.

*Check (passed):* breeding in `wada` mode with `colour` locked never changes any colour
role; with everything *but* `colour` locked, every one of five children differs — measured
**5.00 of 5 for all 62 partial lock combinations**, against the 0.88 this section
predicted for the unfixed behaviour, and 0 exact copies in 20,000 unlocked children, so
the fallback costs nothing when nothing is locked. Every bred `wada` child is an
assignment the mode would have offered, checked over 1,500 children. The role assignment
moves by a single transposition, more rarely than the combination, and survives a change
of combination in over half the cases where the layout holds. `--mode wada --lock
shatter,spacing,seed,tiling,zoom` produces ten visibly different palettes in one sheet.


### 12.1 DECISIONS BEHIND PHASES 9–15

Agreed before implementation, recorded so they can be revisited rather than re-argued.

1. **Lock granularity: six coarse genes, not per-knob.** The six in phase 9's table, not
   twelve individual fields. They match how the problem was actually described ("lock the
   colour scheme or zoom level or tiling style") and they match the units the mutation
   already moves in. A twelve-checkbox window would mostly be noise. The gene registry
   keeps a finer view addable later without reworking the breed API.

2. **Wada is a separate mode, not a widening of the default.** This is the decision that
   matters most, because it resolves a genuine contradiction rather than papering over it:
   section 2 records that Wada palettes were excluded *on purpose* as working against the
   plainer aesthetic, and section 1 says "no multi-colour palette". Making Wada an opt-in
   mode keeps both statements true of the default look while still opening the new space.
   The cost is two colour aesthetics to maintain; that was accepted.

3. **One overlap colour for any overlap.** See phase 12.

4. **The colour refactor is its own phase, landed before any colour feature.** Accepting a
   phase that ships nothing visible, in exchange for one renderer rewrite instead of three
   and a clean rollback point if a colour feature disappoints. The golden-image no-op test
   is what makes the trade worth it.

5. **Colour *mode* is not a mutable gene.** *(decided alongside the four above)*
   Breeding explores within one aesthetic. Letting Further jump between them would make
   one button mean two incompatible things and would make the `colour` lock ambiguous —
   locked against what?

   **Amended after phase 14:** this decision originally added "you choose `classic` or
   `wada` when you launch the chooser", and the chooser now carries a colour-model
   switch, so that half no longer holds. Nothing else about the decision changes, and
   the distinction is the point: *the user* crosses between aesthetics, deliberately and
   one cover at a time; *breeding* still never does. Both reasons above were about
   `Further`, and both survive intact. Asking someone to relaunch the window to see the
   other half of the tool was never part of the argument — it was just an assumption
   about where the choice would be made.

6. **Colour settings stay flat on `CoverSpec`; only the resolved result is an object.**
   *(decided at the start of phase 10)* A nested `ColorScheme` reads tidier and is what an
   earlier draft of phase 10 above implied, but it would nest `--config` JSON and force
   phase 9's gene registry to mutate through nested paths. The resolved `Palette` is the
   object; the settings remain plain fields, and phases 11–13 add more of them.

7. **Both three-colour role layouts are offered, not one.** A three-colour Wada
   combination can fill *(background, feature box, tiles)* or *(background, tile
   shape A, tile shape B)* with the box left invisible. Both are worth having and
   the breeder picks between them, so the layout is part of the `colour` gene
   rather than a mode the user sets once. With 120 three-colour combinations that
   is 240 covers' worth of ground, for one extra field.

8. **`role_permutation` is NOT bounded, and dark backgrounds are allowed.** An
   earlier draft proposed restricting permutations so the darkest colour could
   never land on the background. Rejected: the striking results are worth the
   occasional unusable one, and Wada mode is opt-in anyway (decision 2), so the
   plain pastel register is never at risk. **The condition attached to this
   decision is that the ordinary tools must let you climb back out** — see the
   phase 14 requirement below, which exists because of this decision.

9. **Locks are compensated by guaranteeing every child differs from its parent,**
   not by scaling the mutation rates. *(decided after phase 12, from measurement.)*
   Draw as normal; if a child comes back an exact copy of its parent, force one
   still-free gene to mutate. Chosen over proportional rate-scaling because it
   needs no tuning constant, does exactly as much as the situation requires, and
   **leaves unlocked breeding bit-identical** — measured 0 exact copies in 20,000
   unlocked children, so the fallback never fires unless something is locked.

   It is also the existing principle extended: section 11.2 already rejects a
   mutation that re-picks the current value because "with only five slots" it
   wastes one. A child identical to its parent wastes a slot for the same reason,
   and row 1 already shows the parent, so row 2 has no need of a copy.

   Prototyped across every lock combination: **5.00 of 5 children differ** in all
   of them, against 1.77 and 0.88 for the two worst cases today. `Closer` is
   exempt — when only major genes are free it stays refused, because "nothing
   major moves" leaves it nothing to do.

10. **The default role assignment reproduces the house look, and drifts by single
    swaps.** *(decided at the start of phase 13, from measurement.)* An earlier draft
    of phase 13 said "lightness, lightest to background". Measured against the classic
    default cover that is backwards: the box is white at **L\*=100**, the background
    pastel at **89.0**, the tiles at **64.5** — the box is the lightest element, not
    the ground. So `role_permutation = 0` is lightest→box, next→background,
    darkest→tiles (and for `shapes`, lightest→background, the rest to the tiles).
    The familiar look is therefore where a Wada cover *starts*.

    **The second half of this decision is what lets you leave it.** `role_permutation`
    gets its **own** mutation draw inside the `colour` gene, at a rate below the
    combination's, and it moves by a **single transposition** — swap two roles — rather
    than a uniform re-roll across all k! orderings. Without that, the alternate-track
    case is inexpressible: `_mutate_colour` today replaces `(bg, tile_color, box_color)`
    as one atomic triple, and locks are whole-gene, so "keep this role layout but keep
    roaming the combinations" would collapse into either one frozen scheme or none.

    A low rate makes the house look the statistical *centre* rather than merely the
    starting point; a transposition makes each excursion a recognisable variation
    (ground and box trading places) instead of a scramble, which is what `Closer` and
    `Further` already mean to the hand on the button; and because transpositions
    generate the full symmetric group, sustained `Further` still reaches any ordering,
    so decision 8 loses no ground. It also satisfies section 11.2's rule that a
    mutation never re-picks the current value — a transposition always changes
    something.

    A seventh gene, or a sub-lock under `colour`, was rejected: it would contradict
    decision 1's six coarse genes to buy what one rate constant already buys. Decision
    1's "a finer view is addable later" stays available if measurement disagrees.
    **The rate itself is set in phase 14 by measurement, not chosen here** — the same
    method as decision 9.

11. **The contrast floor is two-tier, not uniform.** Strict between any (background,
    box, tile) pair; lenient between `tile_a` and `tile_b`. Two adjacent tiles of the
    same patch sitting close together read as *texture*; a close tile/box or
    tile/background pair reads as a rendering failure. Starting values **25 strict, 12
    lenient** in Lab, to be confirmed by eye on real covers.

    This is the decision that gives the word "reshuffle" its meaning. Under a uniform
    floor, permuting roles cannot rescue anything — the multiset of pairwise distances
    is permutation-invariant — and the measurement agrees exactly: **0 combinations
    rescued by reshuffling** at every uniform threshold tried. Under the two-tier floor
    it rescues real ground:

    | floor | `box` | `shapes` | `full` |
    |---|---|---|---|
    | uniform 25 | 106/120 | 106/120 | 84/108 |
    | strict 25, tile-pair 12 | 106/120 | **120**/120 | **103**/108 |

    (Measured through the shipped `color.delta_e`, so under decision 13's
    recomputed Lab. The audit's first pass read one to two combinations higher in
    places because it used the shipped `lab` field — which is the very
    discrepancy decision 13 exists to remove.)

    `box` is unchanged because that layout has no `tile_b` role, so it is
    permutation-invariant by construction — expected, not a defect.

    **Tile-vs-background belongs in the strict set**, which is not obvious until you
    look: flung tiles overhang the feature box onto the plain background, because
    `render.py` fits from the *unedited* patch and nothing clips to the box. Measured
    4 of 149 tiles at default knobs, and more as `max_push` rises.

    **Box-vs-background stays strict too**, even though classic mode treats an
    invisible box as first-class (`box_color="bg"`, section 8). A three- or four-colour
    combination that collapses to look like two wastes the whole point of the mode, and
    the invisible-box look remains reachable through the `shapes` layout — a clean
    division of labour rather than a lost option.

12. **`role_permutation` indexes all k! orderings; the floor filters what is
    *offered*, never what a config can express.** The integer is taken mod k!, and the
    contrast floor is applied at **selection** time — the breeder and any random pick —
    not at load and not at render.

    The alternative, indexing only floor-passing permutations, is what makes this worth
    recording: it would mean that tuning a floor constant silently changed what every
    previously saved config renders, breaking phase 13's own check that a `wada` cover
    reproduces exactly from its saved config. It also matches the wording that check
    already used: every combination the mode *offers*.

    The accepted cost is that a hand-written config can ask for a low-contrast
    assignment and will get it. Hand-editing is the expert path (section 11.1), and a
    config that silently rendered something other than what it says would be worse than
    an ugly cover.

13. **Perceptual distance is measured in Lab recomputed from the shipped `rgb`, not
    read from the shipped `lab` field.** Upstream derived `lab` from the CMYK values
    and re-converted `rgb` separately, so the two disagree — median **1.84** dE, max
    **20.16**. At a floor of 25 that flips 6 of 1128 pairs, and nearly all of them in
    the dangerous direction: combination 318's *Dusky Green* / *Blackish Olive* reads
    **29.7 (passes)** on the shipped `lab` and **16.9 (fails)** on the colours actually
    rendered.

    This keeps the real point of the original instruction — use a perceptual space,
    not Euclidean RGB — while measuring the pixels that land on the page. The
    conversion is about a dozen lines and adds no dependency. The shipped `lab` stays
    in the vendored data untouched, per section 2's rule that the data is copied
    verbatim; it is simply not what the floor reads.

14. **The classic mutation stream is broken once, deliberately, at phase 14.**
    *(decided from measurement, after phase 13.)* Prototyped three ways before
    choosing:

    | variant | classic stream |
    |---|---|
    | Wada draws gated on `spec.mode` | **bit-identical over 200 children** |
    | `border` bred with its own draw | broken |
    | `border` folded inside the existing branch | broken |

    Mode-gating genuinely works, and it works because decision 5 fixes a spec's
    mode for its whole breeding run, so a `classic` spec consumes exactly the
    draw sequence it consumes today. But `border` and `tile_split` apply in
    **both** modes, and any draw for them shifts the stream for every subsequent
    child. Breeding two shipped features (phases 11 and 12) is worth more than
    the saved `--breed-seed` values, so the break is accepted — once, with all
    four genes landing together, which is why they were batched here.

    **The stream golden was widened before this phase, not after** — the narrow
    version could not see the break it existed to catch. See the comment on
    `GOLDEN_FURTHER_1234_DIGESTS`. Re-recording it is part of *this* phase's work
    and must be done knowingly, with the comment updated to say so.

15. **The `colour` gene is mode-aware.** In `wada` mode it mutates the Wada
    fields and leaves `bg`, `tile_color` and `box_color` untouched; in `classic`
    mode it behaves exactly as it does today. Without this, breeding a `wada`
    cover drifts three fields that `wada` mode never reads, so saved configs
    accumulate values that do nothing — and the panels all come back the same
    colour anyway, which is what the mode looks like today.

    Two constraints the audit turned up, recorded because neither is obvious:

    - **`role_layout` cannot mutate on its own.** `box` and `shapes` need a
      three-colour combination and `full` needs a four-colour one, so the gene
      must move *(combination, layout, permutation)* as a consistent triple.
      Drawing it from `offered(layout)` does that and satisfies decision 11 for
      free, since that set is already floor-filtered. **Amended during
      implementation:** drawing all three *at once* also re-randomises the
      permutation with every new combination, which destroys decision 10's
      stickiness — the assignment was being scrambled roughly every fifth child.
      The permutation is carried across instead whenever it stays legal, and only
      a change of layout resets it. Phase 14 records the measurement.
    - **A transposition can fail the floor.** Decision 10 moves the permutation
      by swapping two roles, and the result may sit below the contrast floor.
      Retry a different transposition, and keep the current permutation if none
      passes — never emit an assignment the mode would not have offered.

16. **The contrast floor constants stand at 25 strict / 12 lenient.**
    *(confirmed by eye and by measurement, at the end of phase 13.)*

    The **lenient floor needs no tuning**: it sits in a dead zone. Any value in
    (8.2, 14.6] gives byte-identical results for `full`, and anything at or below
    14.8 does for `shapes`. It makes exactly one decision — rejecting
    combination 337's pairings at dE 8.2 — and that rejection is right; the two
    tile colours are indistinguishable on the page.

    The **strict floor is a real trade** and 25 is the place to stand: 20 would
    admit 8 more `box` combinations, 30 would cost 10. All 11 combinations that
    25 rejects and 20 would admit were rendered and looked at. Only one (#131,
    dE 18.4, orange tiles on an orange box) is actually broken; the rest are
    merely soft, and always because **box-vs-background** is close.

    That asymmetry is worth recording as a **known future refinement, not a
    to-do**: box-vs-background being soft just produces the medallion-on-plain-
    ground look that section 8 already treats as first-class, whereas a soft
    tile-vs-box is fatal. A third tier would admit those. It is not worth
    reopening decision 11 now — the offered set is 3,392 assignments (636 `box`,
    664 `shapes`, 2,092 `full`), nowhere near thin — but if the pool ever feels narrow, this is the cheapest
    place to widen it.

17. **The corner radius is a fraction of the box's shorter side, capped at 0.5.**
    *(phase 15.)* Pixels cannot work: a 20px radius on a 200px-wide thumbnail and
    on a 3000px print are different shapes, so a chooser thumbnail would stop
    predicting what gets printed — the same reason `tile_gap`, `box_margin` and the
    three margins are all fractions. The shorter side is the reference because it
    makes 0.5 exactly a stadium, which is a meaningful ceiling rather than an
    arbitrary one. Pillow saturates above half rather than failing (0.5, 0.6 and
    1.0 all draw the same shape), so the cap is applied in `box_corner_px` where it
    can be documented, and the CLI rejects out-of-range values so that a 0.8 that
    would silently do nothing is a clear error instead.

18. **`box_corner` is not a bred gene.** *(phase 15.)* Registering it would add a
    draw and break every saved `--breed-seed` for a third time — decision 14 is
    explicit that this should not happen casually. There is clean precedent for a
    setting that is deliberately not a gene: `border_width`, `title_band`,
    `side_margin` and `bottom_margin` are all exactly this. It can be promoted
    later if it turns out to be something worth stumbling onto rather than
    choosing, at the cost of one more stream break, and nothing about the field
    would have to change.

19. **The mutation-stream digest covers the mutable fields, not the whole spec.**
    *(phase 15, from a false positive.)* As first written it hashed all of
    `to_dict()`, so adding `box_corner` — a field no gene owns, that every child
    inherits unchanged — changed all 32 digests while the stream was provably
    intact, which the readable four-child table confirmed by still passing.

    That is worse than it sounds. A guard that fails on every additive schema
    change teaches you to re-record it without reading it, which is precisely the
    habit hard rule 2 exists to prevent, and the next time it fired for a real
    reason it would be waved through. Narrowing it to the fields mutation can
    reach loses nothing — a field no gene owns cannot differ between a recorded
    row and a reproduced one — and it was verified afterwards that the narrowed
    guard still catches a genuine extra draw, failing from child 1 on both radii.
    **Do not widen it back.**

**Suggested order:** 9 → 10 → (11 and 12, in either order) → 13 → 14. Phases 11 and 12 are
independent of each other once 10 lands, so either can go first or they can be split.
*(All of these are built. Phases 15–17, proposed and not started, are in section 12.2,
and the decisions they still need are open questions there rather than entries here.)*


### 12.2 PROPOSED PHASES 15–17

Three features asked for after phase 14 landed. **All three are proposed, none is
started, and each carries at least one design question that must be settled before
any code** — the working agreement in CLAUDE.md, which has caught a real error every
time it has been applied. The difficulty ratings and the numbers below come from
prototyping each one, not from estimating.

The suggested order is **15 → 16 → 17**: 15 is a quick win that lays groundwork 17
reuses, 16 has the best value-for-risk (it touches no random draws at all), and 17
is the largest.

**Phase 15 — Rounded feature-box corners.** *(done)*
The feature box is drawn with sharp corners by a single `ImageDraw.rectangle` call in
`render_front`. Pillow ships `rounded_rectangle` with the same signature plus a
`radius`, so the drawing change is one line. Add a `box_corner` field to `CoverSpec`,
default 0 (square), and a `--box-corner` flag.

Prototyped across radii from square to a full lozenge: the look holds up at every
value, and a large radius on a narrow box degenerates gracefully into a stadium
rather than into anything broken.

*Both questions settled before code, as decisions 17 and 18:* the radius is a
fraction of the box's **shorter side**, capped at 0.5; and it is **not** a bred gene,
following `border_width` and the three margins, so no saved `--breed-seed` was
broken by this phase.

*What building it turned up.* One thing, and it was in the test suite rather than
the feature: the mutation-stream digest added at phase 14 hashed the whole of
`to_dict()`, so `box_corner` — a field no gene touches — changed all 32 digests
while the stream was provably intact. It is now narrowed to the mutable fields.
That is **decision 19**, and it is worth reading before touching that guard again.

*Check (passed):* all 27 pre-existing goldens byte-identical, so nothing that does
not ask for a rounded corner moved a pixel; radius 0 asserted byte-identical to the
old `rectangle` call rather than merely assumed; all four corners cut at every
radius above 0 and the centre never eaten; the radius confirmed proportional to
output size (30px at 150 wide, 120px at 600) and to supersampling; values of 0.5,
0.6, 1.0 and 4.0 all clamp to the stadium; a negative radius renders square; a
config written before phase 15 still loads and renders square; three new goldens,
including the stadium extreme and a rounded box sharing a cover with a Wada palette
and tile borders.

**Phase 16 — The colour dial.** *(proposed; difficulty: MEDIUM)*
`Further` finds new palettes by surprise, which is the point of it, but there is no
way to *hunt*. The ask is a control that walks the colour space for the current
tiling in order — show five, click forward for the next five — so a half-remembered
scheme can be found again.

The enumeration is nearly free: `offered(layout)` is already a deterministic ordered
tuple, so "the next five" is a slice, and `PALETTES` is the classic-mode equivalent.
**It consumes no random draws at all**, so unlike almost everything in phases 9–14 it
cannot shift the mutation stream or break a saved breed seed. That is most of why it
is recommended before phase 17.

*The ordering is the whole design problem, and the natural one is unusable.*
`offered()` is ordered combination-major with every permutation adjacent, so a naive
"next five" shows **the same three colours rearranged five times** rather than five
different colour groups — the first page of `box` is six permutations of combination
121. Prototyped side by side, the difference is not subtle.

*Open — settle before code:*

3. **What does one step of the dial change?** Recommended: one *combination*, at a
   single representative permutation, so every entry on a page is a genuinely
   different colour group. That also shrinks `box` from 127 pages to 22.
4. **In what order?** Recommended: **by hue**, so the dial sweeps reds → oranges →
   yellows → greens → blues → purples and can be searched the way a colour wheel can.
   Combination id is stable but arbitrary, which is exactly the wrong property for
   hunting. Open: hue *of which role* — the background is the largest area and the
   obvious answer.
5. **Where does the permutation go?** If the dial steps combinations only, the role
   assignment needs either a second control or to stay with breeding (decision 10),
   which already moves it by single swaps at a measured rate.
6. **Where does the page state live, and when does it reset?** The chooser has two
   rows with a meaning (`chosen from` / `variations`); a colour page fills the second
   without breeding. Whether selecting a different cover resets the page is a real
   choice and should be made deliberately.

*Check:* stepping the dial changes only colour — every other field of the spec is
untouched; a full sweep visits every assignment the mode offers exactly once and
returns to where it started; no call into `breed.py` and no rng consumed, asserted
rather than assumed.

**Phase 17 — Solid box, hard cutoff.** *(proposed; difficulty: MEDIUM)*
Today the shatter is fitted *inside* the box and the flung tiles spill over the edge
to float on the plain ground — verified in phase 13 as 4 of 149 tiles at default
knobs, and the look section 1 was written around. The ask is an alternative: fill the
box with tiles and cut them dead at its edge, showing nothing outside.

This is **two coupled changes**, which is what makes it the largest of the three:

- **Clipping** every tile to the box — and not only the fills. Borders and the
  overlap composite have to go through the same mask, which means drawing the tiles
  onto their own layer and compositing it through a box-shaped mask rather than
  painting straight onto the canvas.
- **Cover-fit** — scaling the patch to *overfill* the box rather than fit inside it.
  Without this, clipping alone gives a box with empty corners where the debris used
  to be, because the fit is computed from the unedited patch and the shatter then
  moves tiles out of it.

Prototyped, and there is a real tension worth recording: **the more you overfill, the
less shatter you can see.** At an overfill of about 1.45 the visible area is all
intact core and the break-up has vanished entirely; the range where it still reads as
*shattered but solid* is roughly **1.0 to 1.2**.

It should reuse phase 15's rounded corner in the mask, so the two compose — a rounded
solid box was prototyped and works — which is the other reason to do 15 first.

*Open — settle before code:*

7. **One setting or two?** Clipping and cover-fit are separable — clipping alone is a
   legible (if sparser) look — but they are only *useful* together. A single named
   option is simpler to explain; two are more honest about what is happening.
8. **What happens to `box_margin`?** In cover mode it is meaningless or inverted,
   since the patch is deliberately larger than the box. It has a documented meaning in
   section 8 that this would contradict, so the answer must be explicit: most likely
   an `overfill` knob replaces it in this mode and section 8 says so.
9. **Is this a mode or a widening of the default?** Recommended: a **named opt-in
   mode**, exactly as decision 2 made Wada one. Section 1 describes the floating
   debris as the aesthetic, and an opt-in mode keeps that true of the default while
   opening the other look. The cost is a second composition aesthetic to maintain,
   which is the same cost decision 2 accepted.

*Check:* the default is byte-identical on all 27 goldens; with clipping on, no tile
pixel falls outside the box — asserted against the mask, not by eye — including
borders and overlap regions; a cover rendered at thumbnail and print size clips at
the same relative place.


## 13. OPEN ITEMS / DECISIONS DEFERRED

- **Box-aware vs radial shatter.** Radial everywhere today. The gallery showed this
  suits P2 and P3 but makes Pinwheel read as a square block; decide whether Pinwheel
  gets a per-family rule or is simply a different look.
- **Debris entering the title band.** Tiles breaking out of the top of the box may
  drift into the reserved text area. Allowed today; decide whether to clip, push the
  box down, or leave it as a happy accident.
- **Per-family knob defaults.** `core_fraction 0.6` keeps 34% of P3's tiles but 60%
  of P2's, so one default does not give one look.
- **P3 partial-boundary-tile handling:** default drop, revisit against a real render.
- **Tile gap treatment:** uniform centroid scaling today; constant-distance edge
  offset if sharp corners read badly.
- Whether the back cover stays fully plain or gets a small motif.
- Curated pastel backgrounds vs. free-form `--bg` hex — free-form for now. Phase 13
  settles the *multi-colour* half of this question but deliberately leaves classic
  mode's `--bg` free-form.
- ~~**Border width vs. tile gap (phase 11).**~~ **Resolved in phase 11, by
  measurement rather than by choosing:** Pillow strokes a polygon outline inside
  the shape, so the border takes 0% of its pixels from the gap and no clamp is
  needed. See phase 11.
- ~~**Which Wada combination sizes to offer (phase 13).**~~ **Settled: offer both
  three-colour role layouts**, chosen by the breeder. Section 12.1, decision 7.
- ~~**Whether `role_permutation` should be bounded (phase 13).**~~ **Settled: not
  bounded; dark backgrounds are allowed.** Section 12.1, decision 8, together with
  the phase 14 budget-redistribution requirement that makes it recoverable.
- ~~**How the contrast floor is defined (phase 13).**~~ **Settled: two-tier — strict
  between the grounds and the tiles, lenient between the two tile colours, measured in
  Lab recomputed from `rgb`.** Section 12.1, decisions 11 and 13.
- Whether a patch-rotation knob (rotating the whole tiling inside the box) is worth
  exposing; the old project always rotated, this one never does.

The three proposed phases each carry open questions of their own. They are written
where the work is, in **section 12.2**, rather than copied here — but they are listed
so this section stays the place you can find out what is undecided:

- ~~**Rounded corners (phase 15)**~~ — **both settled**, as decisions 17 and 18: a
  fraction of the box's shorter side capped at 0.5, and not a bred gene. Phase 15 is
  built.
- **The colour dial (phase 16)** — what one step changes, in what order, where the
  role permutation goes, and where the page state lives. Four questions, and the
  ordering one is load-bearing: the natural order is unusable for the purpose.
- **Solid box (phase 17)** — one setting or two, what becomes of `box_margin`, and
  whether it is an opt-in mode or a widening of the default. Three questions.


## 14. NICE TO HAVE — NOT BUILDING NOW

### 14.1 The interactive editor

The original plan centred on a tkinter drag-and-drop editor, sequenced last. After
Phases 0–4 shipped and a 40-cover gallery existed, it was **deliberately dropped**
in favour of section 11's lightweight path. The reasoning, recorded so the decision
can be revisited rather than re-argued:

- **The benefit shrank.** Re-rolling a seed costs about a second and produces a
  wholly new arrangement. Hand-placement only pays when one specific cover is right
  except for a detail — real, but much rarer than it seemed before there was a
  gallery to look at.
- **The cost is the highest in the project.** Hit-testing overlapping polygons
  (tkinter's `find_closest` works on bounding boxes and picks the wrong tile
  constantly), inverting the fit transform to turn pixel drags back into patch
  units, inventing a rotation gesture, plus undo, dirty-state and save scaffolding.
- **It is the one component that cannot be verified the way everything else was.**
  Every other phase is checkable by running tests and looking at a PNG. A GUI needs
  a human clicking on it for every iteration.
- **It would now lie about the output.** The renderer does supersampling, LANCZOS
  downscaling and coverage-counted overlap colouring. A tkinter canvas does none of
  those, so the editor preview would visibly differ from the printed result — which
  defeats the point of a positioning tool.

**If it is ever revisited**, nothing needs redesigning: section 4's format already
round-trips, so an editor is purely additive. The sketch was: tkinter Canvas, load a
`ShatterLayout`, draw tiles through the same fit-to-box and inset maths, select a
tile, drag it (`dx,dy`), rotate it (`rot`), delete it (`hidden`), save back to the
same JSON; show the box border and title band so you can judge what crosses them;
never render the final image from the editor. A browser/SVG editor driven by the
same JSON is the alternative if tkinter's interaction proves too limiting — nicer
to use, at the cost of splitting the codebase across two languages.

The honest trigger for reconsidering: **if you find yourself actually wanting to
drag something** after using section 11's workflow on a real cover.

### 14.2 Other things consciously left out

- Text rendering of any kind (section 1 — someone else's job).
- PDF or layered output (section 9 — PNG only).
- Multi-colour palettes, Sanzo Wada colour selection, colour-by-prototile.
- A GUI for parameter tuning; `contact` sheets cover the same need more cheaply.
