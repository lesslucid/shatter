"""Command line interface.

`generate` builds a new layout from a CoverSpec and renders it; `render` renders
a layout that already exists, hand-edited or not; `contact` breeds a generation
of variants and sheets them for choosing by eye.

Spec-valued flags default to argparse.SUPPRESS so that an unset flag is absent
from the namespace entirely. That is what lets `--config` supply the base while
explicitly passed flags override it.
"""

import argparse
import json
import random
from pathlib import Path

from covers.tiling.registry import TILING_REGISTRY
from shatter.assemble import PrintJob, save_png, write_cover
from shatter.color import BORDER_STYLES, MODES, ROLE_LAYOUTS, TILE_SPLITS
from shatter.breed import (
    GENE_NAMES,
    RADII,
    SEED_LIMIT,
    generation,
    locks_everything,
    parse_locks,
    random_seeds,
)
from shatter.contact import SheetStyle, contact_sheet
from shatter.dimensions import (
    DEFAULT_DPI,
    PAGE_THICKNESS_INCHES,
    parse_trim,
    spine_width_inches,
)
from shatter.model import ShatterLayout
from shatter.spec import SPEC_FIELDS, CoverSpec
from shatter import wada

MAX_ZOOM = 20000
#: Read from the dataset rather than hard-coded, so the flag help and the data
#: cannot drift apart.
WADA_COMBINATION_COUNT = len(wada.all_combinations())
SUPPRESS = argparse.SUPPRESS


def unit_interval(value: str) -> float:
    number = float(value)
    if not 0.0 <= number < 1.0:
        raise argparse.ArgumentTypeError(f"must be in [0, 1), got {value}")
    return number


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {value}")
    return number


def combination_id(value: str) -> int:
    """A Wada combination id. Checked here so a typo fails at the flag."""
    number = int(value)
    if not 1 <= number <= WADA_COMBINATION_COUNT:
        raise argparse.ArgumentTypeError(
            f"must be 1-{WADA_COMBINATION_COUNT}, got {value}"
        )
    return number


def box_margin_fraction(value: str) -> float:
    """The feature box's inset, which may be negative (phase 17).

    Negative pushes the patch *past* the box edge instead of stopping short of
    it, which is how the solid look is reached once `--clip-tiles` is on.
    Measured, -0.035 to -0.20 reaches full coverage depending on the box's shape;
    past about -0.25 the intact core fills the frame and the shatter stops being
    visible. The floor here is looser than that on purpose -- it is a guard
    against a typo, not a judgement about taste.
    """
    number = float(value)
    if not -0.5 <= number < 1.0:
        raise argparse.ArgumentTypeError(
            f"must be in [-0.5, 1) -- negative overfills the box -- got {value}"
        )
    return number


def corner_fraction(value: str) -> float:
    """A feature-box corner radius, as a fraction of the box's shorter side.

    Capped at 0.5 because that is already a stadium: Pillow saturates above it,
    so a larger number would be silently accepted and change nothing.
    """
    number = float(value)
    if not 0.0 <= number <= 0.5:
        raise argparse.ArgumentTypeError(
            f"must be in [0, 0.5] -- 0 is square, 0.5 is fully rounded -- got {value}"
        )
    return number


def non_negative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {value}")
    return number


def zoom(value: str) -> int:
    number = positive_int(value)
    if number > MAX_ZOOM:
        raise argparse.ArgumentTypeError(f"must be <= {MAX_ZOOM}, got {value}")
    return number


def add_output_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--trim", type=parse_trim, default="6x9")
    parser.add_argument("--dpi", type=positive_int, default=DEFAULT_DPI)
    parser.add_argument("--out", type=Path, default=Path("./output"))
    parser.add_argument("--supersample", type=positive_int, default=2)
    parser.add_argument(
        "--only",
        choices=["front", "back", "wrap", "all"],
        default="all",
        help="wrap and all require --pages",
    )
    parser.add_argument("--pages", type=positive_int, help="interior page count")
    parser.add_argument(
        "--paper", choices=sorted(PAGE_THICKNESS_INCHES), default="white"
    )
    parser.add_argument(
        "--guides",
        action="store_true",
        help="also write cover_wrap_guides.png marking panels, margins and spine",
    )


def add_presentation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, help="CoverSpec JSON to start from")
    parser.add_argument("--bg", default=SUPPRESS)
    parser.add_argument(
        "--tile-color", choices=["white", "dark", "bg"], default=SUPPRESS
    )
    parser.add_argument(
        "--box-color", choices=["white", "dark", "bg"], default=SUPPRESS
    )
    parser.add_argument(
        "--overlap-color",
        default=SUPPRESS,
        help="colour where tiles overlap: 'auto', 'none', or #RRGGBB",
    )
    parser.add_argument(
        "--border", choices=list(BORDER_STYLES), default=SUPPRESS,
        help="tile outline style (phase 11)",
    )
    parser.add_argument(
        "--tile-split", choices=list(TILE_SPLITS), default=SUPPRESS,
        help="by_type colours each prototile shape separately (phase 12)",
    )
    parser.add_argument(
        "--tile-color-b", choices=["white", "dark", "bg"], default=SUPPRESS,
        help="second prototile's fill; only used with --tile-split by_type",
    )
    parser.add_argument(
        "--mode", choices=list(MODES), default=SUPPRESS,
        help="colour model: classic (the default look) or wada (phase 13). "
             "The wada flags below are read only in wada mode, and the classic "
             "colour flags only in classic mode",
    )
    parser.add_argument(
        "--wada-combination", type=combination_id, default=SUPPRESS,
        metavar=f"1-{WADA_COMBINATION_COUNT}",
        help="which Sanzo Wada combination to draw the palette from",
    )
    parser.add_argument(
        "--role-layout", choices=list(ROLE_LAYOUTS), default=SUPPRESS,
        help="which roles the combination's colours fill; box and shapes take a "
             "three-colour combination, full takes a four-colour one",
    )
    parser.add_argument(
        "--role-permutation", type=non_negative_int, default=SUPPRESS,
        help="which assignment of colours to roles; 0 is the default ordering, "
             "and the value is taken modulo the number of orderings",
    )
    parser.add_argument(
        "--border-width", type=float, default=SUPPRESS,
        help="border thickness as a fraction of the median tile radius, not pixels",
    )
    parser.add_argument(
        "--box-corner", type=corner_fraction, default=SUPPRESS, metavar="0-0.5",
        help="feature-box corner radius as a fraction of its shorter side; "
             "0 is square (the default), 0.5 fully rounded",
    )
    parser.add_argument("--tile-gap", type=unit_interval, default=SUPPRESS)
    parser.add_argument(
        "--box-margin", type=box_margin_fraction, default=SUPPRESS,
        help="how far the patch sits inside the feature box; negative overfills "
             "it, which with --clip-tiles gives the solid look",
    )
    parser.add_argument(
        "--grid-lines", dest="grid_lines", action="store_true", default=SUPPRESS,
        help="draw a 9x9 sudoku grid inside the feature box, behind the tiles",
    )
    parser.add_argument(
        "--clip-tiles", dest="clip_tiles", action="store_true", default=SUPPRESS,
        help="cut the tiles off at the box edge instead of letting them spill "
             "onto the background",
    )
    parser.add_argument("--title-band", type=unit_interval, default=SUPPRESS)
    parser.add_argument("--side-margin", type=unit_interval, default=SUPPRESS)
    parser.add_argument("--bottom-margin", type=unit_interval, default=SUPPRESS)


def lock_set(value: str) -> frozenset[str]:
    """argparse would turn breed.py's ValueError into 'invalid lock_set value',
    throwing away the list of genes it names. Re-raise so the user sees it."""
    try:
        return parse_locks(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


def add_lock_argument(parser: argparse.ArgumentParser) -> None:
    """Genes held still while the rest keep rolling (section 12, phase 9)."""
    parser.add_argument(
        "--lock",
        type=lock_set,
        default=frozenset(),
        metavar="GENE,GENE",
        help=f"hold these still while breeding: {', '.join(GENE_NAMES)}",
    )


def add_shatter_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--tiling", dest="family", choices=sorted(TILING_REGISTRY), default=SUPPRESS
    )
    parser.add_argument("--zoom", type=zoom, default=SUPPRESS)
    parser.add_argument(
        "--depth", type=positive_int, default=SUPPRESS, help="raw override for --zoom"
    )
    parser.add_argument("--seed", type=int, default=SUPPRESS)
    parser.add_argument(
        "--keep-partial-tiles",
        dest="drop_partial_tiles",
        action="store_false",
        default=SUPPRESS,
    )
    parser.add_argument("--core-fraction", type=unit_interval, default=SUPPRESS)
    parser.add_argument("--falloff", type=float, default=SUPPRESS)
    parser.add_argument("--max-push", type=float, default=SUPPRESS)
    parser.add_argument("--jitter", type=float, default=SUPPRESS)
    parser.add_argument(
        "--max-rotation", type=float, default=SUPPRESS, help="degrees"
    )
    parser.add_argument("--dropout", type=unit_interval, default=SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shatter")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="build a new layout and render it")
    gen.set_defaults(func=cmd_generate)
    add_shatter_arguments(gen)
    add_presentation_arguments(gen)
    add_output_arguments(gen)
    gen.add_argument("--emit-layout", type=Path, help="also save the ShatterLayout")
    gen.add_argument("--emit-config", type=Path, help="also save the CoverSpec")

    ren = sub.add_parser("render", help="render an existing layout JSON")
    ren.set_defaults(func=cmd_render)
    ren.add_argument("layout", type=Path)
    add_presentation_arguments(ren)
    add_output_arguments(ren)
    ren.add_argument(
        "--label-tiles",
        action="store_true",
        help="also write front_labels.png with each tile's index drawn on it",
    )

    con = sub.add_parser("contact", help="breed a generation and sheet it")
    con.set_defaults(func=cmd_contact)
    add_shatter_arguments(con)
    add_presentation_arguments(con)
    add_lock_argument(con)
    con.add_argument("--count", type=positive_int, default=10)
    con.add_argument(
        "--vary",
        choices=["seed", "closer", "further"],
        default="seed",
        help="seed: same knobs, new arrangements; closer/further: mutate knobs too",
    )
    con.add_argument(
        "--breed-seed", type=int, help="reproduce a previous sheet (printed each run)"
    )
    con.add_argument("--out", type=Path, default=Path("./output/contact"))

    cho = sub.add_parser("choose", help="breed covers in a window (section 11.2)")
    cho.set_defaults(func=cmd_choose)
    add_shatter_arguments(cho)
    add_presentation_arguments(cho)
    add_lock_argument(cho)
    cho.add_argument("--breed-seed", type=int)
    cho.add_argument("--out", type=Path, default=Path("./output/chosen"))

    return parser


def spec_from_args(args: argparse.Namespace) -> CoverSpec:
    """Config file as the base, explicitly passed flags on top."""
    base = CoverSpec.load(args.config) if args.config else CoverSpec()
    provided = {key: value for key, value in vars(args).items() if key in SPEC_FIELDS}
    return base.with_changes(**provided)


def write_outputs(
    layout: ShatterLayout,
    spec: CoverSpec,
    args: argparse.Namespace,
    label_tiles: bool = False,
) -> None:
    job = PrintJob(
        out=args.out,
        trim=args.trim,
        dpi=args.dpi,
        supersample=args.supersample,
        only=args.only,
        pages=args.pages,
        paper=args.paper,
        guides=args.guides,
        label_tiles=label_tiles,
    )
    for path in write_cover(layout, spec, job):
        print(f"-> {path}")
    if args.only in ("wrap", "all"):
        print(f"   spine {spine_width_inches(args.pages, args.paper):.3f}in")


def require_pages(args: argparse.Namespace) -> None:
    if args.only in ("wrap", "all") and args.pages is None:
        raise SystemExit("--only {wrap,all} needs --pages (the spine depends on it)")


def cmd_generate(args: argparse.Namespace) -> None:
    require_pages(args)
    spec = spec_from_args(args)
    layout = spec.build_layout()
    print(f"{spec.family} depth {layout.depth}, {len(layout.edits)} tiles")

    write_outputs(layout, spec, args)

    if args.emit_layout:
        args.emit_layout.parent.mkdir(parents=True, exist_ok=True)
        args.emit_layout.write_text(json.dumps(layout.to_dict(), indent=2))
        print(f"-> {args.emit_layout}")
    if args.emit_config:
        print(f"-> {spec.save(args.emit_config)}")


def load_layout(path: Path) -> ShatterLayout:
    """Read a layout written by --emit-layout, possibly hand-edited since."""
    try:
        data = json.loads(path.read_text())
    except OSError as error:
        raise SystemExit(f"Cannot read {path}: {error}") from None
    except json.JSONDecodeError as error:
        raise SystemExit(f"{path} is not valid JSON: {error}") from None

    try:
        return ShatterLayout.from_dict(data)
    except (KeyError, TypeError) as error:
        raise SystemExit(f"{path} is not a valid layout: {error}") from None


def cmd_render(args: argparse.Namespace) -> None:
    require_pages(args)
    spec = spec_from_args(args)
    layout = load_layout(args.layout)
    hidden = sum(1 for edit in layout.edits if edit.hidden)
    print(
        f"{layout.family} depth {layout.depth}, {len(layout.edits)} tiles "
        f"({hidden} hidden), seed {layout.seed}"
    )
    write_outputs(layout, spec, args, label_tiles=args.label_tiles)


def cmd_contact(args: argparse.Namespace) -> None:
    spec = spec_from_args(args)
    breed_seed = (
        args.breed_seed if args.breed_seed is not None else random.randrange(SEED_LIMIT)
    )
    rng = random.Random(breed_seed)

    if args.vary == "seed":
        if args.lock:
            # --vary seed only ever moves the seed, so any lock either does
            # nothing or (locking 'seed') asks for N copies of one cover.
            raise SystemExit("--lock needs --vary closer or --vary further")
        specs = random_seeds(spec, args.count, rng)
    else:
        specs = generation(spec, args.count, RADII[args.vary], rng, args.lock)

    locks = ",".join(sorted(args.lock)) if args.lock else "none"
    print(
        f"{args.count} variants, --vary {args.vary}, --lock {locks}, "
        f"--breed-seed {breed_seed}"
    )
    if locks_everything(args.lock):
        print("   every gene is locked, so all variants are copies of the parent")

    sheet = contact_sheet(specs, SheetStyle())
    args.out.mkdir(parents=True, exist_ok=True)
    print(f"-> {save_png(sheet, args.out / 'contact.png')}")

    for index, variant in enumerate(specs):
        variant.save(args.out / f"{index:02d}.json")
    print(f"-> {args.out}/NN.json  (generate --config one of these for a full cover)")


def cmd_choose(args: argparse.Namespace) -> None:
    # Imported here so the rest of the CLI still works without tkinter installed.
    from shatter import chooser

    chooser.run(spec_from_args(args), args.out, args.breed_seed, args.lock)


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except ValueError as error:
        raise SystemExit(str(error)) from None


# The console script (pyproject `shatter = "shatter.cli:main"`) is the usual
# entry point; this makes `python -m shatter.cli` work too, which is what the
# orientation notes tell a new session to run.
if __name__ == "__main__":
    main()
