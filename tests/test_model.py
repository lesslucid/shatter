import json

from shatter.model import ShatterLayout, TileEdit


def make_layout():
    return ShatterLayout(
        family="p3",
        depth=3,
        drop_partial_tiles=True,
        seed=42,
        edits=[
            TileEdit(),
            TileEdit(dx=0.25, dy=-0.5, rot=0.7853981633974483),
            TileEdit(hidden=True),
        ],
    )


def test_layout_round_trips_through_json():
    layout = make_layout()
    restored = ShatterLayout.from_dict(json.loads(json.dumps(layout.to_dict())))
    assert restored == layout


def test_tile_edit_defaults_are_a_no_op():
    assert TileEdit() == TileEdit(dx=0.0, dy=0.0, rot=0.0, hidden=False)


def test_drop_partial_tiles_survives_the_round_trip():
    """It is part of tile identity -- losing it silently shifts every index."""
    layout = make_layout()
    layout.drop_partial_tiles = False
    restored = ShatterLayout.from_dict(json.loads(json.dumps(layout.to_dict())))
    assert restored.drop_partial_tiles is False
