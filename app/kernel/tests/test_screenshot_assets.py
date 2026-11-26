"""The published master set and its references, pinned to the manifest.

The capture recipe and the manifest are only useful when the checked-in
directory, the generated overview and the README agree: a missing master is a
broken link, a stale master is a claim about a surface that no longer exists,
and a renamed frame under an old URL is cached bytes GitHub will keep serving.
These tests read the committed files, never the running stack.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

from scripts.screenshot_manifest import SHOTS, render_index

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / "assets" / "screenshots"
INDEX = ROOT / "docs" / "screenshots" / "README.md"
README = ROOT / "README.md"
MAX_BYTES = 1_000_000
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _manifest_names() -> set[str]:
    return {shot.filename for shot in SHOTS}


def _committed_names() -> set[str]:
    return {path.name for path in ASSETS.iterdir() if path.is_file()}


def test_png_directory_exactly_matches_the_manifest() -> None:
    assert ASSETS.is_dir()
    assert _committed_names() == _manifest_names()


def test_every_master_is_a_png() -> None:
    for name in sorted(_manifest_names()):
        path = ASSETS / name
        assert path.suffix == ".png"
        assert path.read_bytes().startswith(PNG_MAGIC), name


def test_every_master_is_1600_by_1000() -> None:
    for shot in SHOTS:
        with Image.open(ASSETS / shot.filename) as image:
            assert image.size == (1600, 1000), shot.name


def test_every_master_is_below_one_megabyte() -> None:
    for shot in SHOTS:
        size = (ASSETS / shot.filename).stat().st_size
        assert size < MAX_BYTES, f"{shot.name} is {size} bytes"


def test_index_matches_the_manifest_and_links_each_master_once() -> None:
    rendered = render_index(SHOTS)
    assert INDEX.read_text(encoding="utf-8") == rendered
    for shot in SHOTS:
        assert rendered.count(f"../../assets/screenshots/{shot.filename}") == 1, shot.name


def test_every_readme_screenshot_path_resolves_to_a_master() -> None:
    text = README.read_text(encoding="utf-8")
    paths = re.findall(r'<img[^>]+src="([^"]+)"', text)
    paths += re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    screenshots = [source for source in paths if source.startswith("assets/screenshots/")]
    assert screenshots, "the README embeds no screenshot"
    for source in screenshots:
        committed = ROOT / source
        assert committed.is_file(), source
        assert committed.name in _manifest_names(), source
