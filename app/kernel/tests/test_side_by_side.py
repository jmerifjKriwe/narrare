"""The side-by-side compositor's contract: both panels at the shared height,
one labelled PNG in the requested theme's frame, and an honest exit when an
input is missing. The artifact itself is the pilot's proof, not this file's
subject — the pixels' content is the E2E's and the archive's.
"""

from typing import TYPE_CHECKING

from PIL import Image

from scripts.side_by_side import GAP, LABEL_HEIGHT, PAD, PANEL_HEIGHT, compose, main

if TYPE_CHECKING:
    from pathlib import Path


def _image(path: Path, size: tuple[int, int], colour: str) -> Path:
    Image.new("RGB", size, colour).save(path)
    return path


def test_compose_scales_both_panels_to_the_shared_height(tmp_path: Path) -> None:
    real = _image(tmp_path / "real.png", (1600, 2400), "#FFFFFF")
    draft = _image(tmp_path / "draft.webp", (1600, 1500), "#000000")

    written = compose(real, draft, tmp_path / "out.png")

    with Image.open(written) as composed:
        assert composed.format == "PNG"
        assert composed.height == PAD * 2 + LABEL_HEIGHT + PANEL_HEIGHT
        # Both panels keep their own width at the shared height, with the gap
        # and the frame's padding around them.
        assert composed.width == (
            PAD * 2 + GAP + round(1600 * PANEL_HEIGHT / 2400) + round(1600 * PANEL_HEIGHT / 1500)
        )


def test_compose_wears_the_theme_ground(tmp_path: Path) -> None:
    real = _image(tmp_path / "real.png", (100, 100), "#FFFFFF")
    draft = _image(tmp_path / "draft.webp", (100, 100), "#000000")

    written = compose(real, draft, tmp_path / "out.png", theme="dark")

    with Image.open(written) as composed:
        # The top-left corner is the frame's own ground, outside both panels.
        assert composed.getpixel((0, 0)) == (0x16, 0x14, 0x0F)


def test_main_refuses_a_missing_input(tmp_path: Path) -> None:
    real = _image(tmp_path / "real.png", (100, 100), "#FFFFFF")
    out = tmp_path / "out.png"

    assert (
        main(
            [
                "--real",
                str(real),
                "--draft",
                str(tmp_path / "absent.webp"),
                "--out",
                str(out),
            ]
        )
        == 1
    )
    assert not out.exists()
