"""The phase 10 guard: the colour refactor must not move a single pixel.

Every other test here says what the renderer *should* do. This one says only that
it does exactly what it did before, which is the one claim a pure refactor has to
make and the one hardest to make by reading a diff.

Regenerate with `python tests/make_golden.py`, and only when you have decided the
output should change. Turning a red golden green by regenerating it deletes the
guard without deleting the test, which is worse than having neither.
"""

from pathlib import Path

import pytest
from golden_specs import GOLDEN_SPECS, render_golden
from PIL import Image

GOLDEN_DIR = Path(__file__).parent / "golden"


def describe_difference(actual: Image.Image, expected: Image.Image) -> str:
    """Enough detail to tell a real regression from an encoder wobble."""
    if actual.size != expected.size:
        return f"size {actual.size} != {expected.size}"

    a, b = actual.convert("RGB"), expected.convert("RGB")
    pixels_a, pixels_b = list(a.getdata()), list(b.getdata())
    differing = [
        (i, x, y) for i, (x, y) in enumerate(zip(pixels_a, pixels_b)) if x != y
    ]
    worst = max(
        (abs(c - d) for _i, x, y in differing for c, d in zip(x, y)), default=0
    )
    first = differing[0] if differing else None
    where = f" first at ({first[0] % a.width}, {first[0] // a.width})" if first else ""
    return (
        f"{len(differing)} of {len(pixels_a)} pixels differ "
        f"({100 * len(differing) / len(pixels_a):.2f}%), "
        f"largest channel delta {worst}{where}"
    )


@pytest.mark.parametrize("name", sorted(GOLDEN_SPECS))
def test_render_matches_the_golden(name):
    path = GOLDEN_DIR / f"{name}.png"
    assert path.exists(), f"missing golden {path}; run python tests/make_golden.py"

    actual = render_golden(GOLDEN_SPECS[name]).convert("RGB")
    with Image.open(path) as stored:
        expected = stored.convert("RGB")

    # Compare decoded pixels, not file bytes: a zlib or Pillow encoder change can
    # alter the compressed stream without altering a single pixel, and a guard
    # that cries wolf over that gets regenerated away.
    #
    # pytest.fail rather than assert, because pytest's own bytes diff on a 180KB
    # image buries the one line that says where and by how much.
    if actual.tobytes() != expected.tobytes():
        pytest.fail(f"{name} changed: {describe_difference(actual, expected)}")


def test_the_golden_set_covers_every_stored_file():
    """A renamed spec would otherwise leave a stale PNG nothing ever checks."""
    stored = {path.stem for path in GOLDEN_DIR.glob("*.png")}
    assert stored == set(GOLDEN_SPECS)
