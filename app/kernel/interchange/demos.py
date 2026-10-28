"""The bundled demo corpus: three novels in the interchange format, shipped
as data under this package and loaded through the one archive parser.

The demos are hand-maintained source (no `id`/`updated` in their
frontmatter): *Im Stillen Wald* (literary, de), *Dead Signal* (sci-fi, en)
and *Echoes of the Thornwall* (fantasy, en), ported from the v1 demo data.
The corpus doubles as the WP's golden fixture — the round-trip test over it
runs in the kernel suite — so the manifest here and the folders beside this
module move together: a demo added to one and not the other fails
`test_every_demo_parses` on the mismatch.
"""

from __future__ import annotations

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


DEMOS: tuple[DemoInfo, ...] = (
    DemoInfo(slug="im-stillen-wald", title="Im Stillen Wald", language="de"),
    DemoInfo(slug="dead-signal", title="Dead Signal", language="en"),
    DemoInfo(slug="echoes-of-the-thornwall", title="Echoes of the Thornwall", language="en"),
)
"""The demo corpus in picker order: German literary, sci-fi, fantasy."""

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
