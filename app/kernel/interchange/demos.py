"""The bundled demo corpus: three novels in the interchange format, shipped
as data under this package and loaded through the one archive parser.

The demos are hand-maintained source (no `id`/`updated` in their
frontmatter): *Im Stillen Wald* (literary, de), *Dead Signal* (sci-fi, en)
and *Echoes of the Thornwall* (fantasy, en), ported from the v1 demo data.
The corpus doubles as the WP's golden fixture — the kernel suite pins the
bundled bytes as the parser's fixed point — and the setup page's picker
carries its own TS manifest beside this one; the two manifests are
cross-checked against each other and against the parsed archives by the
setup capability's `test_demo_manifest.py`, so a demo added on one side
only — or a card with a wrong count — is a red test, not a wrong picker.

The demo directories are the source of truth: every subdirectory of
`demos/` that carries a `metadata.json` is a demo, in alphabetical slug
order. Adding a demo is creating that directory; nothing else to register.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.kernel.interchange.tree import ArchiveTree, open_directory

DEMOS_DIR = Path(__file__).parent / "demos"
"""The bundled archives, one directory per demo, parser-ready as they sit."""


@dataclass(frozen=True)
class DemoInfo:
    """One demo as the picker shows it: its slug, its own-language title,
    and the language the archive's metadata carries."""

    slug: str
    title: str
    language: str


def _read_demo_info(directory: Path) -> DemoInfo:
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    title = metadata["title"]
    language = metadata["language"]
    if not isinstance(title, str) or not isinstance(language, str):
        raise ValueError(f"demo {directory.name!r}: title and language must be strings")
    return DemoInfo(slug=directory.name, title=title, language=language)


def _discover_demos() -> tuple[DemoInfo, ...]:
    if not DEMOS_DIR.is_dir():
        return ()
    infos: list[DemoInfo] = []
    for directory in sorted(DEMOS_DIR.iterdir(), key=lambda path: path.name):
        if not directory.is_dir():
            continue
        if not (directory / "metadata.json").is_file():
            continue
        infos.append(_read_demo_info(directory))
    return tuple(infos)


DEMOS: tuple[DemoInfo, ...] = _discover_demos()
"""The demo corpus in picker order: alphabetical by slug."""

DEMO_SLUGS: tuple[str, ...] = tuple(info.slug for info in DEMOS)
"""The slugs a first-run request may name; anything else is a 422."""


def demo_tree(slug: str) -> ArchiveTree:
    """One demo's directory as an archive tree, ready for `parse_archive`.

    An unknown slug is a `ValueError`: the request boundary refuses it with a
    422 before this runs, so reaching here means a caller skipped validation.
    """
    if slug not in DEMO_SLUGS:
        raise ValueError(f"unknown demo slug: {slug}")
    return open_directory(DEMOS_DIR / slug)
