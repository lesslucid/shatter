"""The chooser window (section 11.2).

A thin shell over breed.py and contact.py: show real renders small, let the user
pick one, breed from it. All the interesting logic lives in the tested modules.
"""

import json
import random
import tkinter as tk
from collections.abc import Iterable
from pathlib import Path

from PIL import Image, ImageTk

from shatter.assemble import PrintJob, write_cover
from shatter.breed import (
    GENES,
    RADII,
    SEED_LIMIT,
    generation,
    is_inert,
    movable_genes,
    random_seeds,
    resolve_locks,
)
from shatter import dial
from shatter.color import MODES
from shatter.contact import SheetStyle, describe, describe_colour, thumbnail
from shatter.spec import CoverSpec

COLUMNS = 5
STYLE = SheetStyle(thumb_width=170, thumb_height=255, supersample=2)

SELECTED_EDGE = "#cc143c"
PLAIN_EDGE = "#d9d9d9"
EMPTY_FILL = (232, 232, 232)

ROW_LABELS = ("chosen from", "variations")

#: Named feature-box corner radii for the window (phase 15). The spec field is
#: continuous and `--box-corner` takes any value in [0, 0.5]; these are the four
#: worth a click. They live here rather than in `render.py` because they are a
#: convenience of this window, not part of the colour or drawing model -- nothing
#: outside the chooser has any reason to know the names.
CORNER_PRESETS = {"square": 0.0, "soft": 0.08, "round": 0.2, "stadium": 0.5}

#: How far a "solid" cover overfills its box. Inside the measured band that
#: reaches full coverage (-0.035 to -0.20) without going so far that the shatter
#: stops being visible -- see section 12.1, decision 25.
SOLID_BOX_MARGIN = -0.10

#: The three looks phase 17 opens, over the two orthogonal fields underneath
#: (decision 24). Names where they help a hand; `clip_tiles` and `box_margin`
#: stay independently settable from the CLI.
TILE_FITS = ("float", "clipped", "solid")


def tile_fit_name(spec: CoverSpec) -> str:
    """Which of the three looks a cover is currently wearing."""
    if not spec.clip_tiles:
        return "float"
    return "solid" if spec.box_margin < 0 else "clipped"


def corner_preset_name(value: float) -> str:
    """The preset a radius matches, or "" for a value only the CLI can set.

    An empty string leaves every radio button unlit, which is the honest way to
    show `--box-corner 0.22`: the cover really is not any of the four, and
    lighting the nearest would misreport it.
    """
    for name, preset in CORNER_PRESETS.items():
        if preset == value:
            return name
    return ""

def inert_message(radius_name: str, locked: frozenset[str]) -> str:
    """Why a button did nothing, and what to unticking would fix it.

    Closer only ever moves the minor genes (section 11.2), so it goes inert with
    three locks rather than six -- naming which ones is the difference between a
    locked gene doing its job and the window looking broken.
    """
    blocked = sorted(movable_genes(RADII[radius_name]))
    return (
        f"{radius_name.capitalize()} can only vary {', '.join(blocked)}, "
        "and those are all locked. Untick one."
    )


class Chooser:
    def __init__(
        self,
        root: tk.Tk,
        base: CoverSpec,
        out: Path,
        rng: random.Random,
        pages: int = 120,
        locked: Iterable[str] = (),
    ):
        self.root = root
        self.out = out
        self.rng = rng
        starting = resolve_locks(locked)
        self.lock_vars = {
            gene.name: tk.BooleanVar(master=root, value=gene.name in starting)
            for gene in GENES
        }
        self.mode_var = tk.StringVar(master=root, value=base.mode)
        # Preset *names*, not floats: tk variables round-trip through Tcl as
        # strings, and comparing 0.08 that way is a good way to have a radio
        # silently fail to light.
        self.corner_var = tk.StringVar(
            master=root, value=corner_preset_name(base.box_corner)
        )
        self.fit_var = tk.StringVar(master=root, value=tile_fit_name(base))
        self.grid_var = tk.BooleanVar(master=root, value=base.grid_lines)
        # The dial browses independently of the selection (decision 23): clicking
        # one of the covers it put on screen must not lose your place in the
        # sweep, so the cover it is walking from is remembered separately.
        self.dial_anchor: CoverSpec | None = None
        self.colour_page: int | None = None
        self.rows: list[list[CoverSpec]] = [random_seeds(base, COLUMNS, rng), []]
        self.selected: tuple[int, int] | None = None
        self.photos: dict[tuple[int, int], ImageTk.PhotoImage] = {}
        self.blank = ImageTk.PhotoImage(
            Image.new("RGB", (STYLE.thumb_width, STYLE.thumb_height), EMPTY_FILL)
        )

        root.title("shatter - chooser")
        self._build()
        self.refresh("Pick the one you like best, then Closer or Further.")

    def _build(self) -> None:
        self.cells = []
        for row in range(2):
            tk.Label(self.root, text=ROW_LABELS[row], anchor="w", fg="#666").pack(
                fill="x", padx=12, pady=(8, 0)
            )
            strip = tk.Frame(self.root)
            strip.pack(padx=8)
            cells = []
            for column in range(COLUMNS):
                holder = tk.Frame(strip, bg=PLAIN_EDGE, padx=3, pady=3)
                holder.grid(row=0, column=column, padx=5, pady=3)
                label = tk.Label(holder, image=self.blank, cursor="hand2")
                label.pack()
                label.bind(
                    "<Button-1>",
                    lambda _event, r=row, c=column: self.select(r, c),
                )
                caption = tk.Label(strip, text="", fg="#888", font=("TkDefaultFont", 8))
                caption.grid(row=1, column=column)
                cells.append((holder, label, caption))
            self.cells.append(cells)

        locks = tk.Frame(self.root)
        locks.pack(pady=(10, 0))
        tk.Label(locks, text="lock:", fg="#666").pack(side="left", padx=(0, 4))
        for gene in GENES:
            tk.Checkbutton(
                locks,
                text=gene.name,
                variable=self.lock_vars[gene.name],
                command=lambda g=gene: self.explain_lock(g),
            ).pack(side="left")

        modes = tk.Frame(self.root)
        modes.pack(pady=(6, 0))
        # "colour model", not "colour": there is a lock checkbox called `colour`
        # directly above this row, and the two mean different things.
        tk.Label(modes, text="colour model:", fg="#666").pack(side="left", padx=(0, 4))
        for name in MODES:
            tk.Radiobutton(
                modes,
                text=name,
                value=name,
                variable=self.mode_var,
                command=self.switch_mode,
            ).pack(side="left")

        corners = tk.Frame(self.root)
        corners.pack(pady=(4, 0))
        tk.Label(corners, text="box corners:", fg="#666").pack(side="left", padx=(0, 4))
        for name in CORNER_PRESETS:
            tk.Radiobutton(
                corners,
                text=name,
                value=name,
                variable=self.corner_var,
                command=self.switch_corner,
            ).pack(side="left")

        fits = tk.Frame(self.root)
        fits.pack(pady=(4, 0))
        tk.Label(fits, text="tiles:", fg="#666").pack(side="left", padx=(0, 4))
        for name in TILE_FITS:
            tk.Radiobutton(
                fits,
                text=name,
                value=name,
                variable=self.fit_var,
                command=self.switch_fit,
            ).pack(side="left")

        tk.Checkbutton(
            fits, text="grid", variable=self.grid_var, command=self.switch_grid
        ).pack(side="left", padx=(12, 0))

        colours = tk.Frame(self.root)
        colours.pack(pady=(4, 0))
        tk.Label(colours, text="colours:", fg="#666").pack(side="left", padx=(0, 4))
        tk.Button(
            colours, text="\u25c0", width=3, command=lambda: self.dial_step(-1)
        ).pack(side="left", padx=2)
        tk.Button(
            colours, text="\u25b6", width=3, command=lambda: self.dial_step(1)
        ).pack(side="left", padx=2)
        tk.Button(
            colours, text="roles \u21bb", width=8, command=self.cycle_roles
        ).pack(side="left", padx=(12, 0))

        controls = tk.Frame(self.root)
        controls.pack(pady=10)
        tk.Button(
            controls, text="Closer", width=10, command=lambda: self.breed("closer")
        ).pack(side="left", padx=4)
        tk.Button(
            controls, text="Further", width=10, command=lambda: self.breed("further")
        ).pack(side="left", padx=4)
        tk.Button(controls, text="Print!", width=10, command=self.print_cover).pack(
            side="left", padx=16
        )
        tk.Label(controls, text="pages").pack(side="left", padx=(8, 2))
        self.pages_entry = tk.Entry(controls, width=6)
        self.pages_entry.insert(0, "120")
        self.pages_entry.pack(side="left")

        self.status = tk.Label(self.root, text="", anchor="w", fg="#333")
        self.status.pack(fill="x", padx=12, pady=(0, 10))

    def locked_genes(self) -> frozenset[str]:
        return frozenset(
            name for name, var in self.lock_vars.items() if var.get()
        )

    def explain_lock(self, gene) -> None:
        """Say what a lock just did, and warn before a button goes dead.

        The checkbox label is one word, and 'spacing' or 'shatter' does not say
        which knobs it covers.
        """
        locked = self.locked_genes()
        dead = [name for name in RADII if is_inert(RADII[name], locked)]
        if dead:
            self.say(inert_message(dead[0], locked))
            return
        state = "held" if self.lock_vars[gene.name].get() else "free"
        self.say(f"{gene.name} ({gene.describe}) is now {state}.")

    def spec_at(self, row: int, column: int) -> CoverSpec | None:
        if column < len(self.rows[row]):
            return self.rows[row][column]
        return None

    def selected_spec(self) -> CoverSpec | None:
        if self.selected is None:
            return None
        return self.spec_at(*self.selected)

    def select(self, row: int, column: int) -> None:
        spec = self.spec_at(row, column)
        if spec is None:
            return
        self.selected = (row, column)
        # The radio reports the selection's mode rather than a window-wide
        # setting. Setting the variable does not fire the widget's command --
        # tkinter only does that on a click -- so this cannot convert anything.
        self.mode_var.set(spec.mode)
        self.corner_var.set(corner_preset_name(spec.box_corner))
        self.fit_var.set(tile_fit_name(spec))
        self.grid_var.set(spec.grid_lines)
        if row == 0:
            # Choosing a different cover to work from re-anchors the dial;
            # clicking one of its own results does not (decision 23).
            self.dial_anchor = None
            self.colour_page = None
        self.refresh()

    def switch_mode(self) -> None:
        """Convert the selected cover to the other colour model.

        Mode is still **not** a gene (section 12.1, decision 5): `Further` never
        crosses between the two aesthetics, so one button still means one thing
        and a `colour` lock is still unambiguous about what it holds. This is the
        user saying which aesthetic to explore, which is the part decision 5
        always left to them -- it just no longer has to be said at launch.

        Converting is free in both directions because each mode reads only its
        own fields (decision 15): the classic settings survive a trip through
        `wada` untouched, and vice versa, so switching back and forth loses
        nothing.
        """
        spec = self.selected_spec()
        wanted = self.mode_var.get()
        if spec is None:
            self.say("Pick a cover first, then switch the colour model.")
            return
        if spec.mode == wanted:
            return

        row, column = self.selected
        self.rows[row][column] = spec.with_changes(mode=wanted)
        self.refresh(
            f"{wanted}: {describe_colour(self.rows[row][column])}. "
            "Closer or Further to explore it."
        )

    def switch_corner(self) -> None:
        """Set the selected cover's feature-box corner radius.

        The same semantics as `switch_mode`: it converts the selection rather
        than the window, so a row can hold a square cover beside a rounded one
        and the two can be compared directly.

        This control is the *only* way to explore the setting once the window is
        open. `box_corner` is deliberately not a gene (section 12.1, decision
        18), so `Further` never moves it -- which is exactly why it needs a
        control. Children do inherit it unchanged, so choosing a corner here and
        breeding keeps it for the whole row.
        """
        spec = self.selected_spec()
        wanted = self.corner_var.get()
        if spec is None:
            self.say("Pick a cover first, then choose its corners.")
            return
        if not wanted:
            return  # a CLI-set radius that matches no preset; nothing to apply
        radius = CORNER_PRESETS[wanted]
        if spec.box_corner == radius:
            return

        row, column = self.selected
        self.rows[row][column] = spec.with_changes(box_corner=radius)
        self.refresh(f"box corners: {wanted} ({radius:g}).")

    def switch_fit(self) -> None:
        """Move the selected cover between floating, clipped and solid.

        Three names over two orthogonal fields (decision 24): `float` lets the
        debris spill onto the ground as it always has, `clipped` cuts it at the
        box edge, and `solid` also overfills the box so the tiles reach its
        corners. `clip_tiles` and `box_margin` remain separately settable from
        the CLI -- this is the shortcut, not the model.

        Like the other two switches it converts the selection rather than the
        window, so a row can hold all three looks side by side.
        """
        spec = self.selected_spec()
        wanted = self.fit_var.get()
        if spec is None:
            self.say("Pick a cover first, then choose how the tiles sit.")
            return
        if tile_fit_name(spec) == wanted:
            return

        if wanted == "float":
            changed = spec.with_changes(clip_tiles=False)
        elif wanted == "solid":
            changed = spec.with_changes(clip_tiles=True, box_margin=SOLID_BOX_MARGIN)
        else:
            # Coming back from solid, the overfill has to go or it would still
            # read as solid; anything already positive is the user's and is kept.
            margin = spec.box_margin if spec.box_margin >= 0 else CoverSpec().box_margin
            changed = spec.with_changes(clip_tiles=True, box_margin=margin)

        row, column = self.selected
        self.rows[row][column] = changed
        self.refresh(f"tiles: {wanted} (box margin {changed.box_margin:+.2f}).")

    def switch_grid(self) -> None:
        """Turn the sudoku grid on or off for the selected cover.

        Not a bred gene (decision 29), so this is the only way to reach it once
        the window is open -- the same reason the corner and tile controls exist.
        """
        spec = self.selected_spec()
        wanted = self.grid_var.get()
        if spec is None:
            self.grid_var.set(False)
            self.say("Pick a cover first, then turn the grid on.")
            return
        if spec.grid_lines == wanted:
            return

        row, column = self.selected
        self.rows[row][column] = spec.with_changes(grid_lines=wanted)
        note = "" if not wanted else (
            " It is invisible under solid tiles."
            if spec.clip_tiles and spec.box_margin < 0 else ""
        )
        self.refresh(f"grid: {'on' if wanted else 'off'}.{note}")

    def dial_step(self, step: int) -> None:
        """Fill the variations row with the next or previous page of colours.

        This is not breeding: no random draw is made, nothing else about the
        cover moves, and the same page always holds the same covers. It is a walk
        through `dial.entries`, which is ordered by the background's hue so that
        hunting a remembered scheme is a sweep rather than a wait (decisions 20
        and 21).
        """
        if self.dial_anchor is None:
            anchor = self.selected_spec()
            if anchor is None:
                self.say("Pick a cover first, then step through its colours.")
                return
            self.dial_anchor = anchor
            self.colour_page = dial.position(anchor) // dial.PAGE

        total = dial.page_count(self.dial_anchor)
        self.colour_page = (self.colour_page + step) % total
        self.rows[1] = dial.page(self.dial_anchor, self.colour_page)
        self.refresh(
            f"colours {self.colour_page + 1}/{total} "
            f"- {describe_colour(self.rows[1][0])} onward. "
            "Pick one, or keep stepping."
        )

    def cycle_roles(self) -> None:
        """Step the selected cover to its next legal role assignment.

        The last move of a hunt (decision 22): the dial finds a combination, this
        tries the six or twenty-four ways of hanging it on the roles. Only
        assignments that clear the contrast floor are offered, so this can never
        produce a cover the mode would not have.
        """
        spec = self.selected_spec()
        if spec is None:
            self.say("Pick a cover first.")
            return
        if spec.mode != "wada":
            self.say("Only wada covers have a role assignment to cycle.")
            return

        moved = dial.next_permutation(spec)
        if moved == spec:
            self.say("This combination has only one assignment that clears the floor.")
            return

        row, column = self.selected
        self.rows[row][column] = moved
        self.refresh(f"roles: {describe_colour(moved)}.")

    def breed(self, radius_name: str) -> None:
        parent = self.selected_spec()
        if parent is None:
            self.say("Pick a cover first.")
            return

        locked = self.locked_genes()
        if is_inert(RADII[radius_name], locked):
            # Five identical thumbnails read as a bug, so refuse and say why
            # rather than breeding a row of copies.
            self.say(inert_message(radius_name, locked))
            return

        # Breeding moves on from the cover the dial was walking from, so the
        # old position means nothing (decision 23).
        self.dial_anchor = None
        self.colour_page = None

        row, column = self.selected
        if row == 1:
            self.rows[0] = self.rows[1]
            self.selected = (0, column)
        self.rows[1] = generation(
            parent, COLUMNS, RADII[radius_name], self.rng, locked
        )

        message = f"{radius_name} variations of seed {parent.seed}"
        if locked:
            message += f" - holding {', '.join(sorted(locked))}"
        self.refresh(message)

    def print_cover(self) -> None:
        spec = self.selected_spec()
        if spec is None:
            self.say("Pick a cover first.")
            return
        try:
            pages = int(self.pages_entry.get())
            if pages < 1:
                raise ValueError
        except ValueError:
            self.say("Pages must be a whole number of 1 or more.")
            return

        self.say("Rendering at full size...")
        layout = spec.build_layout()
        job = PrintJob(out=self.out, pages=pages, guides=True)
        written = write_cover(layout, spec, job)

        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "layout.json").write_text(json.dumps(layout.to_dict(), indent=2))
        spec.save(self.out / "spec.json")
        self.say(f"Wrote {len(written) + 2} files to {self.out}")

    def refresh(self, message: str | None = None) -> None:
        self.say(message or "Rendering...")
        for row in range(2):
            for column in range(COLUMNS):
                self._draw_cell(row, column)
        if message:
            self.say(message)

    def _draw_cell(self, row: int, column: int) -> None:
        holder, label, caption = self.cells[row][column]
        spec = self.spec_at(row, column)

        if spec is None:
            label.configure(image=self.blank)
            caption.configure(text="")
            holder.configure(bg=PLAIN_EDGE)
            return

        photo = ImageTk.PhotoImage(thumbnail(spec, STYLE))
        self.photos[(row, column)] = photo  # tkinter does not hold its own reference
        label.configure(image=photo)
        caption.configure(text=describe(spec))
        holder.configure(
            bg=SELECTED_EDGE if self.selected == (row, column) else PLAIN_EDGE
        )

    def say(self, message: str) -> None:
        self.status.configure(text=message)
        self.root.update_idletasks()


def run(
    base: CoverSpec,
    out: Path,
    breed_seed: int | None = None,
    locked: Iterable[str] = (),
) -> None:
    seed = breed_seed if breed_seed is not None else random.randrange(SEED_LIMIT)
    print(f"chooser breed seed {seed}")
    root = tk.Tk()
    Chooser(root, base, out, random.Random(seed), locked=locked)
    root.mainloop()
