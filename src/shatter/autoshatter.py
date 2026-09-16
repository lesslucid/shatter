"""The parametric shatter rule -- where the look lives (section 7).

Distances here are expressed as fractions of the patch radius rather than raw
patch units, because the three families have very different radii (P3 ~0.9, P2
~1.2, Pinwheel ~2.8 at comparable depths) and an absolute push would behave
completely differently in each.
"""

import math
import random
from dataclasses import dataclass

from shatter.geometry import centroid, whole_tiles
from shatter.model import ShatterLayout, TileEdit


@dataclass
class ShatterParams:
    core_fraction: float = 0.6  # radius below which tiles stay intact
    falloff: float = 2.0  # >1 keeps the mid-field calm, flings the rim
    max_push: float = 0.5  # outward displacement, as a fraction of patch radius
    jitter: float = 0.12  # random scatter, same units as max_push
    max_rotation: float = math.radians(40)
    dropout: float = 0.3  # peak probability a rim tile is dropped


def auto_shatter(
    family: str,
    depth: int,
    seed: int,
    params: ShatterParams,
    drop_partial_tiles: bool = True,
) -> ShatterLayout:
    tiles = whole_tiles(family, depth, drop_partial_tiles)
    centroids = [centroid(tile) for tile in tiles]
    radii = [math.hypot(x, y) for x, y in centroids]
    max_radius = max(radii)

    rng = random.Random(seed)
    edits = []
    for (cx, cy), radius in zip(centroids, radii):
        # Drawn for every tile, including intact ones, so that nudging
        # core_fraction re-classifies tiles without re-rolling the whole patch.
        radial_jitter = rng.uniform(-1.0, 1.0)
        tangential_jitter = rng.uniform(-1.0, 1.0)
        spin = rng.uniform(-1.0, 1.0)
        drop_roll = rng.random()

        r = radius / max_radius
        if r <= params.core_fraction:
            edits.append(TileEdit())
            continue

        s = ((r - params.core_fraction) / (1.0 - params.core_fraction)) ** params.falloff

        ux, uy = (cx / radius, cy / radius) if radius else (0.0, 0.0)
        outward = s * (params.max_push + params.jitter * radial_jitter) * max_radius
        sideways = s * params.jitter * tangential_jitter * max_radius

        edits.append(
            TileEdit(
                dx=ux * outward - uy * sideways,
                dy=uy * outward + ux * sideways,
                rot=spin * params.max_rotation * s,
                hidden=drop_roll < params.dropout * s,
            )
        )

    return ShatterLayout(
        family=family,
        depth=depth,
        drop_partial_tiles=drop_partial_tiles,
        seed=seed,
        edits=edits,
    )
