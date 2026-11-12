"""Compose the fidelity artifact: a real surface beside its archived draft.

The Literary Modernism pilot's acceptance is the side-by-side (spec §6.6, §9):
one image per theme holding the E2E screenshot of the seeded route next to the
Stitch WebP it was built against. This script is the composition step — it
scales both panels to one height, labels them and writes one PNG. It is not a
gate: the artifact lands in the wave's ``.superpowers/`` folder for the PR
description, never in ``assets/screenshots/``.

Run against the writing showcase's screenshots (``just test-e2e writing -m
showcase`` writes them to ``/tmp/opencode/showcase/``)::

    uv run python -m scripts.side_by_side \
        --real /tmp/opencode/showcase/shelf.png \
        --draft docs/design/stitch/screens/library/shelf.webp \
        --out .superpowers/sdd/2026-11-11-literary-modernism-pilot/side-by-side-light.png

The dark artifact pairs ``shelf-dark.png`` with ``shelf-dark.webp`` and passes
``--dark`` so the frame around the comparison wears the midnight ground.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PANEL_HEIGHT = 1400
"""The height both panels are scaled to: large enough to read a card's words,
small enough for one artifact."""

PAD = 28
GAP = 32
LABEL_HEIGHT = 56

THEMES = {
    "light": {"ground": "#F6F3ED", "ink": "#1E1B16", "hairline": "#E0DEDA"},
    "dark": {"ground": "#16140F", "ink": "#DFDEDA", "hairline": "#35332D"},
}
"""The comparison's own frame — the app's parchment pair, so the artifact reads
as part of the design record in either theme."""


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """The label face: DejaVu where the machine has it, Pillow's default else."""
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def _panel(path: Path) -> Image.Image:
    """One side of the comparison, at the shared height, RGB."""
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    scale = PANEL_HEIGHT / image.height
    width = round(image.width * scale)
    # Pillow's own stub spells resize's size union with an Unknown member, so
    # strict pyright reports the member as partially unknown; the call is typed.
    return image.resize(  # pyright: ignore[reportUnknownMemberType]
        (width, PANEL_HEIGHT), Image.Resampling.LANCZOS
    )


def compose(
    real: Path,
    draft: Path,
    out: Path,
    *,
    theme: str = "light",
    real_label: str = "Narrare · the real surface (seeded E2E)",
    draft_label: str = "Stitch · the archived draft",
) -> Path:
    """Write one side-by-side PNG and return its path."""
    palette = THEMES[theme]
    panels = [(_panel(real), real_label), (_panel(draft), draft_label)]
    width = PAD * 2 + GAP + sum(panel.width for panel, _ in panels)
    height = PAD * 2 + LABEL_HEIGHT + PANEL_HEIGHT

    canvas = Image.new("RGB", (width, height), palette["ground"])
    draw = ImageDraw.Draw(canvas)
    font = _font(24)

    left = PAD
    for panel, label in panels:
        draw.text(
            (left, PAD + LABEL_HEIGHT // 2), label, fill=palette["ink"], font=font, anchor="lm"
        )
        top = PAD + LABEL_HEIGHT
        canvas.paste(panel, (left, top))
        draw.rectangle(
            (left - 1, top - 1, left + panel.width, top + panel.height),
            outline=palette["hairline"],
        )
        left += panel.width + GAP

    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, format="PNG", optimize=True)
    return out


def main(argv: list[str] | None = None) -> int:
    """Compose one artifact; exit non-zero when an input is missing."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real", type=Path, required=True, help="the E2E screenshot")
    parser.add_argument("--draft", type=Path, required=True, help="the archived Stitch screen")
    parser.add_argument("--out", type=Path, required=True, help="the PNG to write")
    parser.add_argument("--theme", choices=sorted(THEMES), default="light")
    parser.add_argument("--real-label", default="Narrare · the real shelf (seeded E2E)")
    parser.add_argument("--draft-label", default="Stitch · the archived shelf draft")
    args = parser.parse_args(argv)

    for path in (args.real, args.draft):
        if not path.is_file():
            print(f"missing input: {path}", file=sys.stderr)
            return 1
    written = compose(
        args.real,
        args.draft,
        args.out,
        theme=args.theme,
        real_label=args.real_label,
        draft_label=args.draft_label,
    )
    print(f"wrote {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
