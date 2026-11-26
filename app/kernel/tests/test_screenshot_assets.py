"""The published master set and its references, pinned to the manifest.

The capture recipe and the manifest are only useful when the checked-in
directory, the generated overview and the README agree: a missing master is a
broken link, a stale master is a claim about a surface that no longer exists,
and a renamed frame under an old URL is cached bytes GitHub will keep serving.
These tests read the committed files, never the running stack.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from PIL import Image

from scripts.screenshot_manifest import (
    README_SHOTS,
    README_STAND_IN_DISCLOSURE,
    SHOTS,
    STAND_IN_DISCLOSURE,
    STAND_INS,
    render_index,
)
from scripts.screenshots_publish import (  # pyright: ignore[reportPrivateUsage]
    _write_index_temp,  # pyright: ignore[reportPrivateUsage]
    publish,
)

if TYPE_CHECKING:
    from collections.abc import Callable

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / "assets" / "screenshots"
INDEX = ROOT / "docs" / "screenshots" / "README.md"
README = ROOT / "README.md"
DOCS_README = ROOT / "docs" / "README.md"
STITCH_README = ROOT / "docs" / "design" / "stitch" / "README.md"
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


_IMG_TAG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_IMG_ATTR = re.compile(r'([a-zA-Z-]+)="([^"]*)"')


def _readme_screenshots() -> list[tuple[str, str]]:
    """Every README ``<img>`` whose source is a screenshot, as ``(src, alt)``."""
    images: list[tuple[str, str]] = []
    for tag in _IMG_TAG.findall(README.read_text(encoding="utf-8")):
        attrs = dict(_IMG_ATTR.findall(tag))
        source = attrs.get("src", "")
        if source.startswith("assets/screenshots/"):
            images.append((source, attrs.get("alt", "")))
    return images


def test_readme_gallery_is_the_curated_manifest_in_order() -> None:
    images = _readme_screenshots()
    expected = [f"assets/screenshots/{shot.filename}" for shot in README_SHOTS]
    assert [source for source, _ in images] == expected
    for (source, alt), shot in zip(images, README_SHOTS, strict=True):
        assert (ROOT / source).is_file(), source
        assert alt == shot.caption, source


def test_readme_discloses_every_model_stand_in() -> None:
    text = " ".join(README.read_text(encoding="utf-8").split())
    assert " ".join(README_STAND_IN_DISCLOSURE.split()) in text
    # One structured list feeds both pages: every surface it names must reach
    # the README, not only the collection index (the omission #991 fixed).
    for entry in STAND_INS:
        subject = f"both {entry.surface} frames" if entry.both else f"the {entry.surface} frame"
        assert subject in README_STAND_IN_DISCLOSURE, entry.surface
        assert subject in text, entry.surface
    # The README shows no collection frame numbers, so its disclosure names
    # surfaces only; the numbered version belongs to the collection index.
    assert " ".join(STAND_IN_DISCLOSURE.split()) not in text
    assert "(29)" not in text
    assert "(33 and 34)" not in text


def test_index_discloses_every_model_stand_in() -> None:
    text = " ".join(render_index(SHOTS).split())
    assert " ".join(STAND_IN_DISCLOSURE.split()) in text
    for entry in STAND_INS:
        subject = f"both {entry.surface} frames" if entry.both else f"the {entry.surface} frame"
        assert subject in text, entry.surface
        if entry.frames:
            assert f"{subject} ({' and '.join(entry.frames)})" in text, entry.surface


# The settings page is live, so describing it as future work is the stale claim
# this guard exists for (#988). The markers below are the meanings that carry
# that claim: a reworded roadmap sentence still trips one, and checking the
# whole settings section rather than one phrase catches it wherever it lands.
_FUTURE_WORK = re.compile(
    r"\b(?:phase\s+\d|roadmap|planned|not\s+yet|coming\s+soon|upcoming|future\s+release)\b",
    re.IGNORECASE,
)


def _readme_section(text: str, heading: str) -> str:
    """One README section, from its level-two heading to the next one."""
    match = re.search(rf"^## {re.escape(heading)}$", text, re.MULTILINE)
    assert match is not None, f"the README has no {heading!r} section"
    body = text[match.end() :]
    following = re.search(r"^## ", body, re.MULTILINE)
    return body[: following.start()] if following else body


def test_readme_does_not_describe_live_settings_as_future_work() -> None:
    section = _readme_section(README.read_text(encoding="utf-8"), "Settings & prompts")
    assert section.strip(), "the settings section is empty"
    stale = _FUTURE_WORK.search(section)
    assert stale is None, f"the settings section calls live work future: {stale.group(0)}"


def test_future_work_guard_catches_rewording_not_one_phrase() -> None:
    for stale in (
        "Settings is Phase 1 of the rebuild.",
        "Settings is on the roadmap.",
        "Appearance is planned for a later release.",
        "Prompts are not yet editable.",
        "Provider profiles are coming soon.",
    ):
        assert _FUTURE_WORK.search(stale), stale
    assert _FUTURE_WORK.search("Settings holds language, appearance and the profile.") is None


def _markdown_targets(text: str) -> list[str]:
    return re.findall(r"\[[^\]]*\]\(([^)]+)\)", text)


def _collection_targets(readme: Path) -> list[str]:
    text = readme.read_text(encoding="utf-8")
    return [
        target for target in _markdown_targets(text) if target.endswith("screenshots/README.md")
    ]


def _paragraph_linking(text: str, target: str) -> str:
    paragraphs = re.split(r"\n\s*\n", text)
    matching = [paragraph for paragraph in paragraphs if f"]({target})" in paragraph]
    assert len(matching) == 1, f"expected one paragraph linking {target}"
    return " ".join(matching[0].split())


def test_docs_readme_links_the_screenshot_collection() -> None:
    targets = _collection_targets(DOCS_README)
    assert targets, "docs/README.md does not link the screenshot collection"
    for target in targets:
        assert (DOCS_README.parent / target).resolve() == INDEX.resolve(), target


# The paragraph's one claim, split into the meanings it must carry: the drafts
# are design evidence, the captures are the product, and the running
# application is the authority. Markers rather than a sentence, so a rewording
# keeps its meaning (#988).
_STITCH_REQUIRED = ("design evidence", "product captures", "running application")

# Claims that flip the provenance or the subject: the drafts were never
# uploaded from the product, and the captures are not the design evidence.
_STITCH_FORBIDDEN = (
    "reference screen",
    "uploaded into",
    "screens the stitch project used",
    "those captures are design evidence",
    "came from the running application",
)


def test_stitch_readme_links_the_collection_instead_of_the_masters() -> None:
    targets = _collection_targets(STITCH_README)
    assert targets, "the Stitch overview does not link the screenshot collection"
    for target in targets:
        assert (STITCH_README.parent / target).resolve() == INDEX.resolve(), target
    text = STITCH_README.read_text(encoding="utf-8")
    assert "assets/screenshots/" not in text, "the master list is duplicated again"

    paragraph = _paragraph_linking(text, targets[0])
    lowered = paragraph.lower()
    for marker in _STITCH_REQUIRED:
        assert marker in lowered, f"the Stitch paragraph lost {marker!r}"
    for marker in _STITCH_FORBIDDEN:
        assert marker not in lowered, f"the Stitch paragraph claims {marker!r}"
    assert f"[screenshot collection]({targets[0]})" in paragraph


def test_stitch_guards_reject_inverted_provenance_not_one_sentence() -> None:
    for wrong in (
        "Those captures are design evidence, not product captures.",
        "Reference screens the Stitch project used come from the running application.",
        "Reference screenshots uploaded into the same Stitch project.",
    ):
        assert any(marker in wrong.lower() for marker in _STITCH_FORBIDDEN), wrong
    reworded = (
        "The drafts are design evidence, not product captures; the running application "
        "decides how the shell behaves."
    )
    for marker in _STITCH_REQUIRED:
        assert marker in reworded.lower(), marker
    for marker in _STITCH_FORBIDDEN:
        assert marker not in reworded.lower(), marker


_INLINE_MARKDOWN_LINK = re.compile(
    r"!?\[[^\]]*\]\(\s*"
    r"(?:<(?P<angle>[^>]*)>|(?P<bare>[^\s)]+))"
    r'(?:\s+(?:"[^"]*"|\'[^\']*\'|\([^)]*\)))?'
    r"\s*\)"
)
_REFERENCE_DEFINITION = re.compile(r"^ {0,3}\[[^\]]+\]:\s*(?:<(?P<angle>[^>]*)>|(?P<bare>\S+))")
_ABSOLUTE_TARGET = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _link_target(match: re.Match[str]) -> str | None:
    return match.group("angle") if match.group("angle") is not None else match.group("bare")


def _markdown_link_targets(text: str) -> list[str]:
    """Every inline link and reference definition target in a Markdown text.

    An inline target may be ``<...>``-wrapped and followed by a title. A
    reference-style usage resolves through its definition, so only the
    definition line carries the target. Fragments stay attached here; the
    resolver strips them.
    """
    targets: list[str] = []
    for match in _INLINE_MARKDOWN_LINK.finditer(text):
        target = _link_target(match)
        if target is not None:
            targets.append(target)
    for line in text.splitlines():
        match = _REFERENCE_DEFINITION.match(line)
        if match is not None:
            target = _link_target(match)
            if target is not None:
                targets.append(target)
    return targets


def _relative_markdown_targets(readme: Path) -> list[str]:
    """Every repository-relative link target in a Markdown file.

    Pure fragments and absolute URLs name no file in the repository and are
    dropped.
    """
    targets = _markdown_link_targets(readme.read_text(encoding="utf-8"))
    return [
        target
        for target in targets
        if target and not target.startswith("#") and not _ABSOLUTE_TARGET.match(target)
    ]


def _resolve_markdown_target(readme: Path, target: str, *, root: Path = ROOT) -> Path:
    """Resolve a local Markdown target, repository-rooted or file-relative."""
    path = target.split("#", 1)[0]
    if path.startswith("/"):
        return (root / path.lstrip("/")).resolve()
    return (readme.parent / path).resolve()


def test_relative_markdown_targets_read_every_link_form(tmp_path: Path) -> None:
    document = tmp_path / "README.md"
    document.write_text(
        "\n".join(
            [
                "[plain](docs/plain.md)",
                '[titled](docs/titled.md "A title")',
                "[wrapped](<docs/a path.md>)",
                "[fragment](docs/plain.md#a-section)",
                "[rooted](/docs/rooted.md)",
                "[reference][ref]",
                "[ref]: docs/reference.md",
                '[angled]: <docs/angled path.md> "Reference title"',
                "[remote](https://example.com/remote.md)",
                "[anchor](#top)",
            ]
        ),
        encoding="utf-8",
    )

    assert _relative_markdown_targets(document) == [
        "docs/plain.md",
        "docs/titled.md",
        "docs/a path.md",
        "docs/plain.md#a-section",
        "/docs/rooted.md",
        "docs/reference.md",
        "docs/angled path.md",
    ]


def test_markdown_targets_resolve_as_written(tmp_path: Path) -> None:
    source = tmp_path / "docs" / "design" / "stitch"
    source.mkdir(parents=True)
    document = source / "README.md"
    document.write_text(
        "\n".join(
            [
                "[plain](docs/plain.md)",
                '[titled](docs/titled.md "A title")',
                "[wrapped](<docs/a path.md>)",
                "[fragment](docs/plain.md#a-section)",
                "[rooted](/docs/rooted.md)",
                "[reference][ref]",
                "[ref]: docs/reference.md",
                '[angled]: <docs/angled path.md> "Reference title"',
            ]
        ),
        encoding="utf-8",
    )
    for relative in ("docs/plain.md", "docs/titled.md", "docs/a path.md", "docs/reference.md"):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# here\n", encoding="utf-8")
    rooted = tmp_path / "docs" / "rooted.md"
    rooted.parent.mkdir(parents=True, exist_ok=True)
    rooted.write_text("# here\n", encoding="utf-8")
    angled = source / "docs" / "angled path.md"
    angled.write_text("# here\n", encoding="utf-8")

    for target in _relative_markdown_targets(document):
        assert _resolve_markdown_target(document, target, root=tmp_path).is_file(), target


def test_all_relative_stitch_markdown_links_resolve() -> None:
    targets = _relative_markdown_targets(STITCH_README)
    parsed = {Path(target.split("#", 1)[0]).name for target in targets}
    assert {
        "2026-10-22-frontend-design.md",
        "2026-10-21-narrare-v2-architecture-design.md",
    } <= parsed, "the Stitch overview's spec links were not parsed"
    missing = [
        target for target in targets if not _resolve_markdown_target(STITCH_README, target).exists()
    ]
    assert not missing, f"unresolved Stitch overview links: {missing}"


def test_asset_contract_imports_no_capture_stack() -> None:
    """The metadata contract runs where Playwright is not installed (#983)."""
    source = Path(__file__).read_text(encoding="utf-8")
    imported = set(re.findall(r"^(?:from|import)\s+([A-Za-z_][\w.]*)", source, re.MULTILINE))
    assert "scripts.screenshots" not in imported, "the asset tests import the capture stack"
    assert not {name for name in imported if name == "playwright" or name.startswith("playwright.")}

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import scripts.screenshots_publish; "
            "raise SystemExit('playwright' in sys.modules)",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _previous_outputs(masters: Path, index: Path) -> None:
    """The canonical outputs a publication replaces."""
    masters.mkdir(parents=True)
    (masters / "old.png").write_bytes(b"old master")
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text("old index\n", encoding="utf-8")


def _staged_capture(root: Path) -> tuple[Path, Path]:
    """A capture's payload: its masters directory and the rendered index."""
    masters = root / "masters"
    masters.mkdir(parents=True)
    for shot in SHOTS:
        (masters / shot.filename).write_bytes(b"new master")
    index = root / "README.md"
    index.write_text("new index\n", encoding="utf-8")
    return masters, index


def _devices(*mapping: tuple[Path, int]) -> Callable[[Path], int]:
    """A device lookup that gives each root its own filesystem id."""

    def device(path: Path) -> int:
        for root, identifier in mapping:
            if path == root or root in path.parents:
                return identifier
        raise AssertionError(f"no device for {path}")

    return device


def _backups(*parents: Path) -> list[Path]:
    return [path for parent in parents for path in parent.glob(".*-backup-*")]


def _index_temps(index: Path) -> list[Path]:
    return [path for path in index.parent.glob(f".{index.name}-*") if path.is_file()]


def test_publish_stages_each_output_on_its_own_filesystem(tmp_path: Path) -> None:
    """Different devices (#987): copy the staged masters, never rename across."""
    masters = tmp_path / "assets" / "screenshots"
    index = tmp_path / "docs" / "screenshots" / "README.md"
    _previous_outputs(masters, index)
    staged_masters, staged_index = _staged_capture(tmp_path / "capture")
    devices = _devices((staged_masters.parent, 1), (masters.parent, 2), (index.parent, 3))
    renames: list[tuple[Path, Path]] = []

    def checked(source: Path, target: Path) -> None:
        assert devices(source) == devices(target), f"{source} -> {target} crosses devices"
        renames.append((source, target))
        os.replace(source, target)

    publish(
        masters,
        index,
        staged_masters,
        staged_index,
        swap=checked,
        move=checked,
        device=devices,
    )

    # Old aside and new in, for both outputs, all on one device each.
    assert len(renames) == 4
    assert (masters / SHOTS[0].filename).read_bytes() == b"new master"
    assert not (masters / "old.png").exists()
    assert index.read_text(encoding="utf-8") == "new index\n"
    assert _backups(masters.parent, index.parent) == []
    assert _index_temps(index) == []
    assert list(masters.parent.glob(".screenshots-stage-*")) == []


def test_publish_swaps_a_sibling_staging_directory_in_place(tmp_path: Path) -> None:
    """The capture's own layout: staging beside the target, one device, no copy."""
    masters = tmp_path / "assets" / "screenshots"
    index = tmp_path / "docs" / "screenshots" / "README.md"
    _previous_outputs(masters, index)
    staging = tmp_path / "assets" / ".screenshots-abc"
    staged_masters, staged_index = _staged_capture(staging)

    publish(masters, index, staged_masters, staged_index)

    assert not staged_masters.exists(), "the staged masters were copied, not renamed"
    assert (masters / SHOTS[0].filename).read_bytes() == b"new master"
    assert not (masters / "old.png").exists()
    assert index.read_text(encoding="utf-8") == "new index\n"
    assert _backups(masters.parent, index.parent) == []
    assert _index_temps(index) == []


def test_publish_refuses_an_incomplete_capture(tmp_path: Path) -> None:
    """A staged set that misses a manifest frame never reaches the outputs."""
    masters = tmp_path / "assets" / "screenshots"
    index = tmp_path / "docs" / "screenshots" / "README.md"
    _previous_outputs(masters, index)
    staged_masters, staged_index = _staged_capture(tmp_path / "capture")
    (staged_masters / SHOTS[0].filename).unlink()

    with pytest.raises(SystemExit, match="does not match the manifest"):
        publish(masters, index, staged_masters, staged_index)

    assert (masters / "old.png").read_bytes() == b"old master"
    assert index.read_text(encoding="utf-8") == "old index\n"
    assert _backups(masters.parent, index.parent) == []


def test_publish_refuses_an_output_that_is_its_own_mount(tmp_path: Path) -> None:
    """An output on another device than its parent cannot get a sibling backup."""
    masters = tmp_path / "assets" / "screenshots"
    index = tmp_path / "docs" / "screenshots" / "README.md"
    _previous_outputs(masters, index)
    staged_masters, staged_index = _staged_capture(tmp_path / "capture")
    devices = _devices(
        (masters, 9),
        (masters.parent, 2),
        (index.parent, 3),
        (staged_masters.parent, 1),
    )

    with pytest.raises(RuntimeError, match="different filesystem than its parent"):
        publish(masters, index, staged_masters, staged_index, device=devices)

    # The refusal happens before a backup root, a staged copy or a temp exists.
    assert (masters / "old.png").read_bytes() == b"old master"
    assert index.read_text(encoding="utf-8") == "old index\n"
    assert _backups(masters.parent, index.parent) == []
    assert _index_temps(index) == []
    assert list(masters.parent.glob(".screenshots-stage-*")) == []
    assert (staged_masters / SHOTS[0].filename).read_bytes() == b"new master"


def test_failed_staging_copy_leaves_no_stage_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A copy that dies halfway must not strand a staging directory."""
    masters = tmp_path / "assets" / "screenshots"
    index = tmp_path / "docs" / "screenshots" / "README.md"
    _previous_outputs(masters, index)
    staged_masters, staged_index = _staged_capture(tmp_path / "capture")
    devices = _devices((staged_masters.parent, 1), (masters.parent, 2), (index.parent, 3))

    def failing_copy(source: Path, target: Path, **kwargs: object) -> None:
        raise OSError("copy failed")

    monkeypatch.setattr("scripts.screenshots_publish.shutil.copytree", failing_copy)

    with pytest.raises(OSError, match="copy failed"):
        publish(masters, index, staged_masters, staged_index, device=devices)

    assert list(masters.parent.glob(".screenshots-stage-*")) == []
    assert _backups(masters.parent, index.parent) == []
    assert (masters / "old.png").read_bytes() == b"old master"
    assert index.read_text(encoding="utf-8") == "old index\n"


def test_cross_device_copy_is_cleaned_up_when_the_index_swap_fails(
    tmp_path: Path,
) -> None:
    """A copied masters stage is removed on rollback; both old outputs return."""
    masters = tmp_path / "assets" / "screenshots"
    index = tmp_path / "docs" / "screenshots" / "README.md"
    _previous_outputs(masters, index)
    staged_masters, staged_index = _staged_capture(tmp_path / "capture")
    devices = _devices((staged_masters.parent, 1), (masters.parent, 2), (index.parent, 3))

    def failing_swap(source: Path, target: Path) -> None:
        if source.name.startswith(f".{index.name}-"):
            raise RuntimeError("index swap failed")
        os.replace(source, target)

    with pytest.raises(RuntimeError, match="index swap failed"):
        publish(
            masters,
            index,
            staged_masters,
            staged_index,
            swap=failing_swap,
            device=devices,
        )

    assert (masters / "old.png").read_bytes() == b"old master"
    assert not (masters / SHOTS[0].filename).exists()
    assert index.read_text(encoding="utf-8") == "old index\n"
    # The non-empty copy staged beside the masters is gone; the caller's own
    # capture directory is not publication debris.
    assert list(masters.parent.glob(".screenshots-stage-*")) == []
    assert _index_temps(index) == []
    assert _backups(masters.parent, index.parent) == []
    assert (staged_masters / SHOTS[0].filename).read_bytes() == b"new master"


def test_index_swap_failure_restores_previous_masters_and_index(tmp_path: Path) -> None:
    """A failed index swap must leave both previous outputs in place."""
    masters = tmp_path / "assets" / "screenshots"
    index = tmp_path / "docs" / "screenshots" / "README.md"
    _previous_outputs(masters, index)
    staged_masters, staged_index = _staged_capture(tmp_path / "capture")

    def failing_swap(source: Path, target: Path) -> None:
        if source.name.startswith(f".{index.name}-"):
            raise RuntimeError("index swap failed")
        os.replace(source, target)

    with pytest.raises(RuntimeError, match="index swap failed"):
        publish(masters, index, staged_masters, staged_index, swap=failing_swap)

    assert (masters / "old.png").read_bytes() == b"old master"
    assert not (masters / SHOTS[0].filename).exists()
    assert index.read_text(encoding="utf-8") == "old index\n"
    assert _index_temps(index) == []
    assert _backups(masters.parent, index.parent) == []
    assert list(masters.parent.glob(".screenshots-stage-*")) == []


def test_complete_rollback_discards_both_backups(tmp_path: Path) -> None:
    """Backups go only after both previous outputs are back."""
    masters = tmp_path / "assets" / "screenshots"
    index = tmp_path / "docs" / "screenshots" / "README.md"
    _previous_outputs(masters, index)
    staged_masters, staged_index = _staged_capture(tmp_path / "capture")
    restored: list[Path] = []

    def failing_swap(source: Path, target: Path) -> None:
        if source.name.startswith(f".{index.name}-"):
            raise RuntimeError("index swap failed")
        os.replace(source, target)

    def tracking_move(source: Path, target: Path) -> None:
        os.replace(source, target)
        if target in {masters, index}:
            restored.append(target)

    with pytest.raises(RuntimeError, match="index swap failed"):
        publish(
            masters,
            index,
            staged_masters,
            staged_index,
            swap=failing_swap,
            move=tracking_move,
        )

    assert restored == [masters, index], "a restore did not run"
    assert _backups(masters.parent, index.parent) == []


def test_failed_restore_keeps_both_backups(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A restore that fails must leave both backups for manual recovery."""
    masters = tmp_path / "assets" / "screenshots"
    index = tmp_path / "docs" / "screenshots" / "README.md"
    _previous_outputs(masters, index)
    staged_masters, staged_index = _staged_capture(tmp_path / "capture")

    def failing_swap(source: Path, target: Path) -> None:
        if source.name.startswith(f".{index.name}-"):
            raise RuntimeError("index swap failed")
        os.replace(source, target)

    def failing_restore(source: Path, target: Path) -> None:
        if source.name == "masters":
            raise OSError("restore failed")
        os.replace(source, target)

    monkeypatch.setattr("scripts.screenshots_publish._move", failing_restore)

    with pytest.raises(RuntimeError, match="previous outputs kept in") as raised:
        publish(masters, index, staged_masters, staged_index, swap=failing_swap)

    masters_backups = list(masters.parent.glob(".screenshots-backup-*"))
    index_backups = list(index.parent.glob(".README.md-backup-*"))
    assert len(masters_backups) == 1
    assert len(index_backups) == 1
    for root in (*masters_backups, *index_backups):
        assert str(root) in str(raised.value)
    assert "empty when that output was already restored" in str(raised.value)
    assert (masters_backups[0] / "masters" / "old.png").read_bytes() == b"old master"
    # The index restore still ran, so its kept backup holds nothing.
    assert not (index_backups[0] / "index").exists()
    assert index.read_text(encoding="utf-8") == "old index\n"
    assert _index_temps(index) == []


def test_aborted_rollback_keeps_both_backups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rollback that cannot restore must keep the last good copies."""
    masters = tmp_path / "assets" / "screenshots"
    index = tmp_path / "docs" / "screenshots" / "README.md"
    _previous_outputs(masters, index)
    staged_masters, staged_index = _staged_capture(tmp_path / "capture")

    def failing_swap(source: Path, target: Path) -> None:
        if source.name.startswith(f".{index.name}-"):
            raise RuntimeError("index swap failed")
        os.replace(source, target)

    def failing_remove(path: Path) -> None:
        raise OSError("remove failed")

    def failing_move(source: Path, target: Path) -> None:
        if "-backup-" in source.parent.name:
            raise OSError("restore blocked")
        os.replace(source, target)

    monkeypatch.setattr("scripts.screenshots_publish._remove", failing_remove)
    monkeypatch.setattr("scripts.screenshots_publish._move", failing_move)

    with pytest.raises(RuntimeError, match="previous outputs kept in") as raised:
        publish(masters, index, staged_masters, staged_index, swap=failing_swap)

    masters_backups = list(masters.parent.glob(".screenshots-backup-*"))
    index_backups = list(index.parent.glob(".README.md-backup-*"))
    assert len(masters_backups) == 1
    assert len(index_backups) == 1
    for root in (*masters_backups, *index_backups):
        assert str(root) in str(raised.value)
    assert "empty when that output was already restored" in str(raised.value)
    assert (masters_backups[0] / "masters" / "old.png").read_bytes() == b"old master"
    assert (index_backups[0] / "index").read_text(encoding="utf-8") == "old index\n"


def test_interrupt_during_rollback_propagates_and_keeps_both_backups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An interrupt outranks the best-effort rollback; recovery roots stay."""
    masters = tmp_path / "assets" / "screenshots"
    index = tmp_path / "docs" / "screenshots" / "README.md"
    _previous_outputs(masters, index)
    staged_masters, staged_index = _staged_capture(tmp_path / "capture")

    def failing_swap(source: Path, target: Path) -> None:
        if source.name.startswith(f".{index.name}-"):
            raise RuntimeError("index swap failed")
        os.replace(source, target)

    def interrupting_remove(path: Path) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("scripts.screenshots_publish._remove", interrupting_remove)

    with pytest.raises(KeyboardInterrupt):
        publish(masters, index, staged_masters, staged_index, swap=failing_swap)

    masters_backups = list(masters.parent.glob(".screenshots-backup-*"))
    index_backups = list(index.parent.glob(".README.md-backup-*"))
    assert len(masters_backups) == 1
    assert len(index_backups) == 1
    assert (masters_backups[0] / "masters" / "old.png").read_bytes() == b"old master"
    assert (index_backups[0] / "index").read_text(encoding="utf-8") == "old index\n"


def test_index_temp_is_removed_when_its_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed index write must not leave its temporary file behind."""
    index = tmp_path / "index.md"
    handle = Mock()
    handle.__enter__ = Mock(return_value=handle)
    handle.__exit__ = Mock(return_value=False)
    handle.write.side_effect = OSError("write failed")

    def failing_fdopen(descriptor: int, *args: object, **kwargs: object) -> Mock:
        os.close(descriptor)
        return handle

    monkeypatch.setattr("scripts.screenshots_publish.os.fdopen", failing_fdopen)

    with pytest.raises(OSError, match="write failed"):
        _write_index_temp(index, "new index\n")

    assert _index_temps(index) == []


def test_index_write_failure_leaves_outputs_and_backups_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed index write during publish must not disturb either output."""
    masters = tmp_path / "assets" / "screenshots"
    index = tmp_path / "docs" / "screenshots" / "README.md"
    _previous_outputs(masters, index)
    staged_masters, staged_index = _staged_capture(tmp_path / "capture")
    handle = Mock()
    handle.__enter__ = Mock(return_value=handle)
    handle.__exit__ = Mock(return_value=False)
    handle.write.side_effect = OSError("write failed")

    def failing_fdopen(descriptor: int, *args: object, **kwargs: object) -> Mock:
        os.close(descriptor)
        return handle

    monkeypatch.setattr("scripts.screenshots_publish.os.fdopen", failing_fdopen)

    with pytest.raises(OSError, match="write failed"):
        publish(masters, index, staged_masters, staged_index)

    assert (masters / "old.png").read_bytes() == b"old master"
    assert index.read_text(encoding="utf-8") == "old index\n"
    assert _index_temps(index) == []
    assert _backups(masters.parent, index.parent) == []


def test_index_temp_unlink_failure_keeps_the_publication_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing cleanup unlink must not override the error or skip cleanup."""
    masters = tmp_path / "assets" / "screenshots"
    index = tmp_path / "docs" / "screenshots" / "README.md"
    _previous_outputs(masters, index)
    staged_masters, staged_index = _staged_capture(tmp_path / "capture")
    real_unlink = Path.unlink

    def failing_swap(source: Path, target: Path) -> None:
        if source.name.startswith(f".{index.name}-"):
            raise RuntimeError("index swap failed")
        os.replace(source, target)

    def failing_unlink(self: Path, missing_ok: bool = False) -> None:
        if self.name.startswith(f".{index.name}-"):
            raise OSError("unlink failed")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", failing_unlink)

    with pytest.raises(RuntimeError, match="index swap failed"):
        publish(masters, index, staged_masters, staged_index, swap=failing_swap)

    # The primary error and the complete restore win; only the hidden temp stays.
    assert (masters / "old.png").read_bytes() == b"old master"
    assert index.read_text(encoding="utf-8") == "old index\n"
    assert _backups(masters.parent, index.parent) == []
    assert len(_index_temps(index)) == 1


def test_backup_root_failure_stages_no_index_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed backup-root creation must not leave a staged-index temp."""
    masters = tmp_path / "assets" / "screenshots"
    index = tmp_path / "docs" / "screenshots" / "README.md"
    _previous_outputs(masters, index)
    staged_masters, staged_index = _staged_capture(tmp_path / "capture")

    def failing_mkdtemp(*args: object, **kwargs: object) -> str:
        raise OSError("backup root failed")

    monkeypatch.setattr("scripts.screenshots_publish.tempfile.mkdtemp", failing_mkdtemp)

    with pytest.raises(OSError, match="backup root failed"):
        publish(masters, index, staged_masters, staged_index)

    assert _index_temps(index) == []
    assert _backups(masters.parent, index.parent) == []
    assert index.read_text(encoding="utf-8") == "old index\n"
    assert (masters / "old.png").read_bytes() == b"old master"


def test_second_backup_root_failure_leaves_no_empty_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed index backup root must not strand the masters' empty root."""
    masters = tmp_path / "assets" / "screenshots"
    index = tmp_path / "docs" / "screenshots" / "README.md"
    _previous_outputs(masters, index)
    staged_masters, staged_index = _staged_capture(tmp_path / "capture")
    real_mkdtemp = tempfile.mkdtemp
    calls: list[str | None] = []

    def failing_mkdtemp(
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | Path | None = None,
    ) -> str:
        calls.append(prefix)
        if len(calls) == 2:
            raise OSError("index backup root failed")
        return real_mkdtemp(suffix=suffix, prefix=prefix, dir=dir)

    monkeypatch.setattr("scripts.screenshots_publish.tempfile.mkdtemp", failing_mkdtemp)

    with pytest.raises(OSError, match="index backup root failed"):
        publish(masters, index, staged_masters, staged_index)

    assert len(calls) == 2
    assert _backups(masters.parent, index.parent) == []
    assert _index_temps(index) == []
