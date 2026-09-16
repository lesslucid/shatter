"""The shared data format: one layout, produced by either the auto generator
or the editor, consumed by one renderer."""

from dataclasses import asdict, dataclass


@dataclass
class TileEdit:
    dx: float = 0.0
    dy: float = 0.0
    rot: float = 0.0
    hidden: bool = False


@dataclass
class ShatterLayout:
    """Tile arrangement only -- no colours, box geometry or DPI.

    family, depth and drop_partial_tiles together determine the tile list that
    `edits` runs parallel to; changing any of them reassigns every edit to the
    wrong tile. seed is provenance, not an input to rendering.
    """

    family: str
    depth: int
    drop_partial_tiles: bool
    seed: int
    edits: list[TileEdit]

    def to_dict(self) -> dict:
        return {
            "family": self.family,
            "depth": self.depth,
            "drop_partial_tiles": self.drop_partial_tiles,
            "seed": self.seed,
            "edits": [asdict(edit) for edit in self.edits],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ShatterLayout":
        return cls(
            family=data["family"],
            depth=data["depth"],
            drop_partial_tiles=data["drop_partial_tiles"],
            seed=data["seed"],
            edits=[TileEdit(**edit) for edit in data["edits"]],
        )
