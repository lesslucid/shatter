import json
import math

import pytest

from shatter.spec import CoverSpec


def test_round_trips_through_json():
    spec = CoverSpec(family="p2", seed=7, core_fraction=0.42)
    assert CoverSpec.from_dict(json.loads(json.dumps(spec.to_dict()))) == spec


def test_rejects_unknown_config_keys():
    """A typo in a hand-edited config should say so, not be silently ignored."""
    with pytest.raises(ValueError, match="Unknown config keys"):
        CoverSpec.from_dict({"family": "p3", "core_franction": 0.5})


def test_saves_and_loads(tmp_path):
    spec = CoverSpec(seed=99, jitter=0.4)
    assert CoverSpec.load(spec.save(tmp_path / "nested" / "spec.json")) == spec


def test_with_changes_leaves_the_original_alone():
    spec = CoverSpec()
    child = spec.with_changes(seed=1234)
    assert child.seed == 1234
    assert spec.seed == CoverSpec().seed


def test_rotation_is_degrees_in_the_spec_and_radians_in_the_params():
    spec = CoverSpec(max_rotation=90.0)
    assert spec.shatter_params().max_rotation == pytest.approx(math.pi / 2)


def test_shatter_params_carry_the_knobs():
    spec = CoverSpec(core_fraction=0.44, falloff=3.0, max_push=0.9, dropout=0.1)
    params = spec.shatter_params()
    assert (params.core_fraction, params.falloff) == (0.44, 3.0)
    assert (params.max_push, params.dropout) == (0.9, 0.1)


def test_render_params_carry_the_presentation():
    spec = CoverSpec(bg="#ABCDEF", tile_color="white", tile_gap=0.11)
    params = spec.render_params(100, 200, bleed=5, supersample=3)
    assert (params.width, params.height, params.bleed) == (100, 200, 5)
    assert (params.bg, params.tile_color, params.tile_gap) == ("#ABCDEF", "white", 0.11)
    assert params.supersample == 3


def test_depth_overrides_zoom_when_given():
    assert CoverSpec(depth=3).resolved_depth() == 3


def test_zoom_resolves_to_a_depth_that_meets_the_target():
    from shatter.geometry import whole_tiles

    spec = CoverSpec(family="p3", zoom=100)
    depth = spec.resolved_depth()
    assert len(whole_tiles("p3", depth)) >= 100


def test_build_layout_is_deterministic():
    spec = CoverSpec(seed=5)
    assert spec.build_layout() == spec.build_layout()


def test_build_layout_records_the_spec():
    spec = CoverSpec(family="p2", seed=13, zoom=80)
    layout = spec.build_layout()
    assert (layout.family, layout.seed) == ("p2", 13)
    assert layout.depth == spec.resolved_depth()


def test_a_config_written_before_phase_15_still_loads():
    """Hard rule 4. `box_corner` is additive with a default, so a config saved
    before rounded corners existed must still load and still render square."""
    old = {"family": "p3", "zoom": 150, "seed": 7, "box_margin": 0.15}
    spec = CoverSpec.from_dict(old)
    assert spec.box_corner == 0.0


def test_the_corner_radius_round_trips():
    spec = CoverSpec(box_corner=0.35)
    assert CoverSpec.from_dict(json.loads(json.dumps(spec.to_dict()))) == spec


def test_a_config_written_before_phase_17_still_loads():
    old = {"family": "p3", "zoom": 150, "box_margin": 0.15}
    spec = CoverSpec.from_dict(old)
    assert spec.clip_tiles is False


def test_a_solid_cover_round_trips():
    spec = CoverSpec(clip_tiles=True, box_margin=-0.12, box_corner=0.2)
    assert CoverSpec.from_dict(json.loads(json.dumps(spec.to_dict()))) == spec


def test_a_config_written_before_phase_18_still_loads():
    spec = CoverSpec.from_dict({"family": "p3", "zoom": 150, "clip_tiles": True})
    assert spec.grid_lines is False


def test_a_gridded_cover_round_trips():
    spec = CoverSpec(grid_lines=True, box_corner=0.2)
    assert CoverSpec.from_dict(json.loads(json.dumps(spec.to_dict()))) == spec
