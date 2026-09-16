"""Regenerate the golden PNGs. Run deliberately, never from the test suite.

    python tests/make_golden.py

Only run this when you have *decided* the render should change (or Pillow moved
under you). Regenerating to make a red test go green destroys the guard.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from golden_specs import GOLDEN_SPECS, render_golden  # noqa: E402

GOLDEN_DIR = Path(__file__).parent / "golden"


def main() -> None:
    GOLDEN_DIR.mkdir(exist_ok=True)
    for name, spec in GOLDEN_SPECS.items():
        path = GOLDEN_DIR / f"{name}.png"
        render_golden(spec).save(path, "PNG")
        print(f"-> {path.relative_to(Path.cwd())} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
