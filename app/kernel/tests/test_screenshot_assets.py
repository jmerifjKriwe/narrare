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
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image

from scripts.screenshot_manifest import (
    README_SHOTS,
    README_STAND_IN_DISCLOSURE,
    SHOTS,
    STAND_IN_DISCLOSURE,
    render_index,
)
from scripts.screenshots import _publish, _write_index_temp  # pyright: ignore[reportPrivateUsage]

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


def test_readme_discloses_the_model_stand_ins() -> None:
    text = " ".join(README.read_text(encoding="utf-8").split())
    assert " ".join(README_STAND_IN_DISCLOSURE.split()) in text
    # The README shows no collection frame numbers, so its disclosure names
    # surfaces only; the numbered version belongs to the collection index.
    assert " ".join(STAND_IN_DISCLOSURE.split()) not in text
    assert "(29)" not in text
    assert "(33 and 34)" not in text


def test_readme_does_not_call_live_settings_a_roadmap_phase() -> None:
    text = README.read_text(encoding="utf-8")
    assert "is Phase 1 of the" not in text


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


def test_stitch_readme_links_the_collection_instead_of_the_masters() -> None:
    targets = _collection_targets(STITCH_README)
    assert targets, "the Stitch overview does not link the screenshot collection"
    for target in targets:
        assert (STITCH_README.parent / target).resolve() == INDEX.resolve(), target
    text = STITCH_README.read_text(encoding="utf-8")
    assert "assets/screenshots/" not in text, "the master list is duplicated again"

    paragraph = _paragraph_linking(text, targets[0])
    assert "The Stitch screens above are design evidence, not product captures" in paragraph
    assert "captures of the running application" in paragraph.lower()
    assert f"[screenshot collection]({targets[0]})" in paragraph
    assert "Those captures are design evidence" not in paragraph, "the subject is inverted"
    assert "Reference screens the Stitch project used come from" not in paragraph
    assert "Reference screenshots uploaded into the same Stitch project" not in paragraph


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


def test_index_swap_failure_restores_previous_masters_and_index(
    tmp_path: Path,
) -> None:
    """A failed index swap must leave both previous outputs in place."""
    masters = tmp_path / "masters"
    masters.mkdir()
    (masters / "old.png").write_bytes(b"old master")
    index = tmp_path / "index.md"
    index.write_text("old index\n", encoding="utf-8")
    staged = tmp_path / "staged"
    staged.mkdir()
    written: list[Path] = []
    for shot in SHOTS:
        path = staged / shot.filename
        path.write_bytes(b"new master")
        written.append(path)

    def failing_swap(source: Path, target: Path) -> None:
        if source.name.startswith(f".{index.name}-"):
            raise RuntimeError("index swap failed")
        source.rename(target)

    with pytest.raises(RuntimeError, match="index swap failed"):
        _publish(staged, masters, index, written, swap=failing_swap)

    assert (masters / "old.png").read_bytes() == b"old master"
    assert not (masters / SHOTS[0].filename).exists()
    assert index.read_text(encoding="utf-8") == "old index\n"
    assert list(tmp_path.glob(f".{index.name}-*")) == []
    assert list(tmp_path.glob(".masters-backup-*")) == []


def _staged_capture(staged: Path) -> list[Path]:
    """One staged payload per manifest frame, as a successful capture writes."""
    staged.mkdir()
    written: list[Path] = []
    for shot in SHOTS:
        path = staged / shot.filename
        path.write_bytes(b"new master")
        written.append(path)
    return written


def test_failed_restore_keeps_the_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A restore that fails must leave the backup for manual recovery."""
    masters = tmp_path / "masters"
    masters.mkdir()
    (masters / "old.png").write_bytes(b"old master")
    index = tmp_path / "index.md"
    index.write_text("old index\n", encoding="utf-8")
    written = _staged_capture(tmp_path / "staged")

    def failing_swap(source: Path, target: Path) -> None:
        if source.name.startswith(f".{index.name}-"):
            raise RuntimeError("index swap failed")
        source.rename(target)

    def failing_restore(source: Path, target: Path) -> None:
        if source.name == "masters":
            raise OSError("restore failed")
        source.rename(target)

    monkeypatch.setattr("scripts.screenshots._move", failing_restore)

    with pytest.raises(RuntimeError, match="previous outputs kept in") as raised:
        _publish(tmp_path / "staged", masters, index, written, swap=failing_swap)

    backups = list(tmp_path.glob(".masters-backup-*"))
    assert len(backups) == 1
    assert str(backups[0]) in str(raised.value)
    assert (backups[0] / "masters" / "old.png").read_bytes() == b"old master"
    # The second restore still runs, so the backup holds only what failed.
    assert not (backups[0] / "index").exists()
    assert index.read_text(encoding="utf-8") == "old index\n"
    assert list(tmp_path.glob(f".{index.name}-*")) == []


def test_aborted_rollback_keeps_the_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A rollback that cannot restore must keep the last good copies."""
    masters = tmp_path / "masters"
    masters.mkdir()
    (masters / "old.png").write_bytes(b"old master")
    index = tmp_path / "index.md"
    index.write_text("old index\n", encoding="utf-8")
    written = _staged_capture(tmp_path / "staged")

    def failing_swap(source: Path, target: Path) -> None:
        if source.name.startswith(f".{index.name}-"):
            raise RuntimeError("index swap failed")
        source.rename(target)

    def failing_remove(path: Path) -> None:
        raise OSError("remove failed")

    def failing_move(source: Path, target: Path) -> None:
        raise OSError("restore blocked")

    monkeypatch.setattr("scripts.screenshots._remove", failing_remove)
    monkeypatch.setattr("scripts.screenshots._move", failing_move)

    with pytest.raises(RuntimeError, match="previous outputs kept in") as raised:
        _publish(tmp_path / "staged", masters, index, written, swap=failing_swap)

    backups = list(tmp_path.glob(".masters-backup-*"))
    assert len(backups) == 1
    assert str(backups[0]) in str(raised.value)
    assert (backups[0] / "masters" / "old.png").read_bytes() == b"old master"
    assert (backups[0] / "index").read_text(encoding="utf-8") == "old index\n"


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

    monkeypatch.setattr("scripts.screenshots.os.fdopen", failing_fdopen)

    with pytest.raises(OSError, match="write failed"):
        _write_index_temp(index, "new index\n")

    assert list(tmp_path.glob(f".{index.name}-*")) == []


def test_backup_root_failure_stages_no_index_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed backup-root creation must not leave a staged-index temp."""
    index = tmp_path / "index.md"
    index.write_text("old index\n", encoding="utf-8")
    written = _staged_capture(tmp_path / "staged")

    def failing_mkdtemp(*args: object, **kwargs: object) -> str:
        raise OSError("backup root failed")

    monkeypatch.setattr("scripts.screenshots.tempfile.mkdtemp", failing_mkdtemp)

    with pytest.raises(OSError, match="backup root failed"):
        _publish(tmp_path / "staged", tmp_path / "masters", index, written)

    assert list(tmp_path.glob(f".{index.name}-*")) == []
