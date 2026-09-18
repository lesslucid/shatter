import json

import pytest
from conftest import has_label_pixels

from shatter.cli import main

FAST = ["--dpi", "50", "--supersample", "1"]


def generate(out, layout=None, *extra):
    argv = ["generate", "--seed", "42", "--only", "front", "--out", str(out), *FAST]
    if layout is not None:
        argv += ["--emit-layout", str(layout)]
    main(argv + list(extra))


def render(layout, out, *extra):
    main(["render", str(layout), "--only", "front", "--out", str(out), *FAST, *extra])


def test_render_reproduces_generate_exactly(tmp_path):
    """The round-trip is the whole point of the format (section 4)."""
    layout = tmp_path / "layout.json"
    generate(tmp_path / "gen", layout)
    render(layout, tmp_path / "ren")

    assert (tmp_path / "gen" / "front.png").read_bytes() == (
        tmp_path / "ren" / "front.png"
    ).read_bytes()


def test_hiding_a_tile_by_hand_changes_the_render(tmp_path):
    layout = tmp_path / "layout.json"
    generate(tmp_path / "gen", layout)

    data = json.loads(layout.read_text())
    target = next(i for i, edit in enumerate(data["edits"]) if not edit["hidden"])
    data["edits"][target]["hidden"] = True
    layout.write_text(json.dumps(data))

    render(layout, tmp_path / "ren")
    assert (tmp_path / "gen" / "front.png").read_bytes() != (
        tmp_path / "ren" / "front.png"
    ).read_bytes()


def test_presentation_flags_apply_to_render(tmp_path):
    layout = tmp_path / "layout.json"
    generate(tmp_path / "gen", layout)
    render(layout, tmp_path / "plain", "--box-color", "bg")

    assert (tmp_path / "gen" / "front.png").read_bytes() != (
        tmp_path / "plain" / "front.png"
    ).read_bytes()


def test_render_rejects_the_shatter_knobs(tmp_path):
    """Those knobs made the layout; re-applying them would mean a new one."""
    layout = tmp_path / "layout.json"
    generate(tmp_path / "gen", layout)
    with pytest.raises(SystemExit):
        render(layout, tmp_path / "ren", "--core-fraction", "0.9")


def test_render_reports_a_missing_layout(tmp_path):
    with pytest.raises(SystemExit, match="Cannot read"):
        render(tmp_path / "nope.json", tmp_path / "out")


def test_render_reports_malformed_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(SystemExit, match="not valid JSON"):
        render(bad, tmp_path / "out")


def test_render_reports_a_layout_missing_fields(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"family": "p3", "depth": 3}))
    with pytest.raises(SystemExit, match="not a valid layout"):
        render(bad, tmp_path / "out")


def test_render_reports_a_layout_built_for_another_patch(tmp_path):
    layout = tmp_path / "layout.json"
    generate(tmp_path / "gen", layout)

    data = json.loads(layout.read_text())
    data["depth"] = data["depth"] + 1
    layout.write_text(json.dumps(data))

    with pytest.raises(SystemExit, match="different patch"):
        render(layout, tmp_path / "ren")


def test_wrap_requires_a_page_count(tmp_path):
    layout = tmp_path / "layout.json"
    generate(tmp_path / "gen", layout)
    with pytest.raises(SystemExit, match="needs --pages"):
        main(
            ["render", str(layout), "--only", "wrap", "--out", str(tmp_path), *FAST]
        )


def test_bad_colour_is_reported_cleanly(tmp_path):
    with pytest.raises(SystemExit, match="RRGGBB"):
        generate(tmp_path / "gen", None, "--bg", "not-a-colour")


def test_label_tiles_writes_a_separate_reference_file(tmp_path):
    """front.png must stay a clean print asset; labels go in their own file."""
    from PIL import Image

    layout = tmp_path / "layout.json"
    generate(tmp_path / "gen", layout)
    render(layout, tmp_path / "ren", "--label-tiles")

    clean = tmp_path / "ren" / "front.png"
    labelled = tmp_path / "ren" / "front_labels.png"
    assert clean.exists() and labelled.exists()

    with Image.open(clean) as image:
        assert not has_label_pixels(image)
    with Image.open(labelled) as image:
        assert has_label_pixels(image)


def test_no_labels_unless_asked(tmp_path):
    layout = tmp_path / "layout.json"
    generate(tmp_path / "gen", layout)
    render(layout, tmp_path / "ren")
    assert not (tmp_path / "ren" / "front_labels.png").exists()


def test_config_round_trip_reproduces_the_cover(tmp_path):
    """A saved config must rebuild its cover exactly, or breeding is useless."""
    config = tmp_path / "spec.json"
    main(
        ["generate", "--seed", "77", "--jitter", "0.33", "--only", "front",
         "--emit-config", str(config), "--out", str(tmp_path / "a"), *FAST]
    )
    main(
        ["generate", "--config", str(config), "--only", "front",
         "--out", str(tmp_path / "b"), *FAST]
    )
    assert (tmp_path / "a" / "front.png").read_bytes() == (
        tmp_path / "b" / "front.png"
    ).read_bytes()


def test_explicit_flags_override_the_config(tmp_path):
    config = tmp_path / "spec.json"
    main(
        ["generate", "--only", "front", "--emit-config", str(config),
         "--out", str(tmp_path / "a"), *FAST]
    )
    main(
        ["generate", "--config", str(config), "--box-color", "bg", "--only", "front",
         "--out", str(tmp_path / "b"), *FAST]
    )
    assert (tmp_path / "a" / "front.png").read_bytes() != (
        tmp_path / "b" / "front.png"
    ).read_bytes()


def contact(out, *extra):
    main(["contact", "--count", "4", "--zoom", "60", "--out", str(out), *extra])


def test_contact_writes_a_sheet_and_a_config_per_panel(tmp_path):
    contact(tmp_path / "c", "--breed-seed", "1")
    assert (tmp_path / "c" / "contact.png").exists()
    assert sorted(p.name for p in (tmp_path / "c").glob("*.json")) == [
        "00.json", "01.json", "02.json", "03.json",
    ]


def test_contact_is_reproducible_from_its_breed_seed(tmp_path):
    contact(tmp_path / "a", "--breed-seed", "4", "--vary", "further")
    contact(tmp_path / "b", "--breed-seed", "4", "--vary", "further")
    assert (tmp_path / "a" / "contact.png").read_bytes() == (
        tmp_path / "b" / "contact.png"
    ).read_bytes()


def test_contact_panels_can_be_regenerated_full_size(tmp_path):
    """The saved config is the bridge from 'I like that one' to a real cover."""
    from shatter.spec import CoverSpec

    contact(tmp_path / "c", "--breed-seed", "2", "--vary", "closer")
    chosen = CoverSpec.load(tmp_path / "c" / "02.json")

    main(
        ["generate", "--config", str(tmp_path / "c" / "02.json"), "--only", "front",
         "--out", str(tmp_path / "full"), *FAST]
    )
    assert (tmp_path / "full" / "front.png").exists()
    assert chosen.build_layout().seed == chosen.seed


def test_contact_seed_mode_keeps_the_knobs(tmp_path):
    from shatter.spec import CoverSpec

    contact(tmp_path / "c", "--breed-seed", "3", "--vary", "seed", "--jitter", "0.4")
    for path in sorted((tmp_path / "c").glob("*.json")):
        assert CoverSpec.load(path).jitter == 0.4


def test_generate_writes_a_layout_that_records_its_inputs(tmp_path):
    layout = tmp_path / "layout.json"
    generate(tmp_path / "gen", layout, "--tiling", "p2", "--seed", "7")

    data = json.loads(layout.read_text())
    assert data["family"] == "p2"
    assert data["seed"] == 7
    assert data["drop_partial_tiles"] is True
    assert len(data["edits"]) > 0


# --- Phase 9: --lock --------------------------------------------------------


def test_contact_lock_holds_the_locked_gene_across_every_panel(tmp_path):
    from shatter.spec import CoverSpec

    contact(
        tmp_path / "c", "--breed-seed", "6", "--vary", "further",
        "--lock", "colour,tiling", "--bg", "#DCE8F2", "--tiling", "p2",
    )
    panels = [CoverSpec.load(p) for p in sorted((tmp_path / "c").glob("*.json"))]
    assert {panel.bg for panel in panels} == {"#DCE8F2"}
    assert {panel.family for panel in panels} == {"p2"}


def test_contact_lock_leaves_the_unlocked_genes_free(tmp_path):
    from shatter.spec import CoverSpec

    contact(tmp_path / "c", "--breed-seed", "6", "--vary", "further", "--lock", "colour")
    panels = [CoverSpec.load(p) for p in sorted((tmp_path / "c").glob("*.json"))]
    assert len({panel.core_fraction for panel in panels}) > 1


def test_contact_lock_needs_a_breeding_vary_mode(tmp_path):
    """--vary seed only moves the seed, so a lock is either inert or absurd."""
    with pytest.raises(SystemExit, match="--vary closer or --vary further"):
        contact(tmp_path / "c", "--vary", "seed", "--lock", "colour")


def test_contact_rejects_an_unknown_gene(tmp_path):
    with pytest.raises(SystemExit):
        contact(tmp_path / "c", "--vary", "closer", "--lock", "sparkle")


def test_contact_without_lock_is_unchanged(tmp_path):
    """Phase 9 must not move the output of a command that does not use it."""
    contact(tmp_path / "a", "--breed-seed", "9", "--vary", "further")
    contact(tmp_path / "b", "--breed-seed", "9", "--vary", "further", "--lock", "")
    assert (tmp_path / "a" / "contact.png").read_bytes() == (
        tmp_path / "b" / "contact.png"
    ).read_bytes()


# --- Phase 11: --border -----------------------------------------------------


def test_border_changes_the_render(tmp_path):
    generate(tmp_path / "plain")
    generate(tmp_path / "edged", None, "--border", "black")
    assert (tmp_path / "plain" / "front.png").read_bytes() != (
        tmp_path / "edged" / "front.png"
    ).read_bytes()


def test_border_none_is_the_default(tmp_path):
    generate(tmp_path / "a")
    generate(tmp_path / "b", None, "--border", "none")
    assert (tmp_path / "a" / "front.png").read_bytes() == (
        tmp_path / "b" / "front.png"
    ).read_bytes()


def test_border_survives_a_config_round_trip(tmp_path):
    from shatter.spec import CoverSpec

    config = tmp_path / "spec.json"
    generate(tmp_path / "gen", None, "--border", "white", "--border-width", "0.2",
             "--emit-config", str(config))
    spec = CoverSpec.load(config)
    assert (spec.border, spec.border_width) == ("white", 0.2)


def test_an_unknown_border_style_is_refused(tmp_path):
    with pytest.raises(SystemExit):
        generate(tmp_path / "x", None, "--border", "dotted")


# --- Phase 12: --tile-split -------------------------------------------------


def test_tile_split_changes_the_render(tmp_path):
    generate(tmp_path / "one")
    generate(tmp_path / "two", None, "--tile-split", "by_type",
             "--tile-color", "dark", "--tile-color-b", "white")
    assert (tmp_path / "one" / "front.png").read_bytes() != (
        tmp_path / "two" / "front.png"
    ).read_bytes()


def test_single_is_the_default_split(tmp_path):
    generate(tmp_path / "a")
    generate(tmp_path / "b", None, "--tile-split", "single")
    assert (tmp_path / "a" / "front.png").read_bytes() == (
        tmp_path / "b" / "front.png"
    ).read_bytes()


def test_tile_color_b_alone_does_nothing(tmp_path):
    """It is only read under by_type, so setting it must not disturb a cover."""
    generate(tmp_path / "a")
    generate(tmp_path / "b", None, "--tile-color-b", "white")
    assert (tmp_path / "a" / "front.png").read_bytes() == (
        tmp_path / "b" / "front.png"
    ).read_bytes()


def test_split_survives_a_config_round_trip(tmp_path):
    from shatter.spec import CoverSpec

    config = tmp_path / "spec.json"
    generate(tmp_path / "gen", None, "--tile-split", "by_type",
             "--tile-color-b", "white", "--emit-config", str(config))
    spec = CoverSpec.load(config)
    assert (spec.tile_split, spec.tile_color_b) == ("by_type", "white")


def test_an_unknown_tile_split_is_refused(tmp_path):
    with pytest.raises(SystemExit):
        generate(tmp_path / "x", None, "--tile-split", "rainbow")


@pytest.mark.parametrize("bad", ["0.8", "-0.1", "1.0"])
def test_generate_rejects_a_corner_radius_outside_the_range(bad, tmp_path):
    """0.5 is already a stadium; Pillow saturates above it, so a larger value
    would be accepted and change nothing. Say so at the flag instead."""
    with pytest.raises(SystemExit):
        main(["generate", "--box-corner", bad, "--out", str(tmp_path)])


def test_generate_accepts_a_corner_radius_and_carries_it_into_the_config(tmp_path):
    config = tmp_path / "spec.json"
    main([
        "generate", "--zoom", "60", "--box-corner", "0.25", "--only", "front",
        "--out", str(tmp_path), "--emit-config", str(config),
    ])
    from shatter.spec import CoverSpec

    assert CoverSpec.load(config).box_corner == 0.25


@pytest.mark.parametrize("bad", ["-0.6", "1.0", "2"])
def test_generate_rejects_a_box_margin_outside_the_range(bad, tmp_path):
    with pytest.raises(SystemExit):
        main(["generate", "--box-margin", bad, "--out", str(tmp_path)])


def test_generate_accepts_the_solid_look(tmp_path):
    """A negative margin overfills the box and --clip-tiles cuts it there."""
    config = tmp_path / "solid.json"
    main([
        "generate", "--zoom", "60", "--box-margin", "-0.1", "--clip-tiles",
        "--only", "front", "--out", str(tmp_path), "--emit-config", str(config),
    ])
    from shatter.spec import CoverSpec

    spec = CoverSpec.load(config)
    assert spec.clip_tiles is True and spec.box_margin == -0.1
