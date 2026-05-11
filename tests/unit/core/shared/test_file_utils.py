"""Tests for shared/file_utils.py — async file operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from narrare_core.shared.file_utils import (
    delete_file,
    ensure_dir,
    find_files,
    read_text,
    read_text_or_none,
    write_text,
)


class TestReadText:
    async def test_reads_existing_file(self, tmp_path: Path) -> None:
        file = tmp_path / "test.txt"
        file.write_text("hello world", encoding="utf-8")

        result = await read_text(file)
        assert result == "hello world"

    async def test_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            await read_text(tmp_path / "nonexistent.txt")


class TestReadTextOrNone:
    async def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        result = await read_text_or_none(tmp_path / "missing.txt")
        assert result is None

    async def test_returns_content_for_existing_file(self, tmp_path: Path) -> None:
        file = tmp_path / "exists.txt"
        file.write_text("content", encoding="utf-8")

        result = await read_text_or_none(file)
        assert result == "content"


class TestWriteText:
    async def test_writes_content_to_file(self, tmp_path: Path) -> None:
        file = tmp_path / "output.txt"

        await write_text(file, "written content")

        assert file.read_text() == "written content"

    async def test_creates_parent_directories(self, tmp_path: Path) -> None:
        file = tmp_path / "deep" / "nested" / "dir" / "file.txt"

        await write_text(file, "nested content")

        assert file.read_text() == "nested content"

    async def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        file = tmp_path / "overwrite.txt"
        file.write_text("old content")

        await write_text(file, "new content")

        assert file.read_text() == "new content"


class TestDeleteFile:
    async def test_deletes_existing_file(self, tmp_path: Path) -> None:
        file = tmp_path / "to_delete.txt"
        file.write_text("delete me")

        result = await delete_file(file)

        assert result is True
        assert not file.exists()

    async def test_returns_false_for_missing_file_when_missing_ok(self, tmp_path: Path) -> None:
        result = await delete_file(tmp_path / "missing.txt", missing_ok=True)
        assert result is False

    async def test_raises_for_missing_file_when_not_missing_ok(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            await delete_file(tmp_path / "missing.txt", missing_ok=False)


class TestEnsureDir:
    async def test_creates_directory(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "new" / "nested" / "dir"

        await ensure_dir(new_dir)

        assert new_dir.is_dir()

    async def test_does_nothing_for_existing_directory(self, tmp_path: Path) -> None:
        existing = tmp_path / "existing"
        existing.mkdir()

        await ensure_dir(existing)  # should not raise


class TestFindFiles:
    def test_finds_matching_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("a")
        (tmp_path / "b.md").write_text("b")
        (tmp_path / "c.txt").write_text("c")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "d.md").write_text("d")

        result = find_files(tmp_path, "*.md")

        assert len(result) == 3
        assert all(str(p).endswith(".md") for p in result)

    def test_returns_empty_for_nonexistent_root(self, tmp_path: Path) -> None:
        result = find_files(tmp_path / "nonexistent")
        assert result == []

    def test_returns_sorted_results(self, tmp_path: Path) -> None:
        (tmp_path / "z.md").write_text("z")
        (tmp_path / "a.md").write_text("a")

        result = find_files(tmp_path, "*.md")

        assert result == sorted(result)
