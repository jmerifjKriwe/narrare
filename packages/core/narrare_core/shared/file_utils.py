"""
File system utilities for safe async I/O.

All file operations in Narrare go through these helpers to ensure
consistent encoding, error handling, and locking behavior.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import aiofiles
import aiofiles.os
from filelock import FileLock


async def read_text(path: Path, *, encoding: str = "utf-8") -> str:
    """
    Read a text file asynchronously.

    Args:
        path: File path to read.
        encoding: Text encoding (default utf-8).

    Returns:
        File contents as string.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: On other I/O errors.
    """
    async with aiofiles.open(path, encoding=encoding) as f:
        return await f.read()


async def read_text_or_none(path: Path, *, encoding: str = "utf-8") -> str | None:
    """
    Read a text file, returning None if it does not exist.

    Args:
        path: File path to read.
        encoding: Text encoding (default utf-8).

    Returns:
        File contents as string, or None if not found.
    """
    try:
        return await read_text(path, encoding=encoding)
    except FileNotFoundError:
        return None


async def write_text(
    path: Path,
    content: str,
    *,
    encoding: str = "utf-8",
    create_parents: bool = True,
) -> None:
    """
    Write text to a file asynchronously with optional parent creation.

    Args:
        path: Destination file path.
        content: Text content to write.
        encoding: Text encoding (default utf-8).
        create_parents: Create parent directories if they don't exist.
    """
    if create_parents:
        await aiofiles.os.makedirs(str(path.parent), exist_ok=True)
    async with aiofiles.open(path, "w", encoding=encoding) as f:
        await f.write(content)


async def write_text_locked(
    path: Path,
    content: str,
    *,
    encoding: str = "utf-8",
    create_parents: bool = True,
    timeout: float = 10.0,
) -> None:
    """
    Write text to a file with file locking to prevent concurrent writes.

    Used for user-facing files (KB entries, prompts) that could be written
    by multiple processes simultaneously.

    Args:
        path: Destination file path.
        content: Text content to write.
        encoding: Text encoding (default utf-8).
        create_parents: Create parent directories if they don't exist.
        timeout: Lock acquisition timeout in seconds.
    """
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock = FileLock(str(lock_path), timeout=timeout)

    def _write() -> None:
        if create_parents:
            path.parent.mkdir(parents=True, exist_ok=True)
        with lock:
            path.write_text(content, encoding=encoding)

    await asyncio.get_event_loop().run_in_executor(None, _write)


async def delete_file(path: Path, *, missing_ok: bool = True) -> bool:
    """
    Delete a file asynchronously.

    Args:
        path: File to delete.
        missing_ok: If True, return False instead of raising when file missing.

    Returns:
        True if file was deleted, False if it didn't exist (when missing_ok=True).

    Raises:
        FileNotFoundError: If file doesn't exist and missing_ok=False.
    """
    try:
        await aiofiles.os.remove(str(path))
        return True
    except FileNotFoundError:
        if missing_ok:
            return False
        raise


async def ensure_dir(path: Path) -> None:
    """Create directory and parents if they don't exist."""
    await aiofiles.os.makedirs(str(path), exist_ok=True)


def find_files(root: Path, pattern: str = "*.md") -> list[Path]:
    """
    Find files matching a glob pattern under a root directory.

    Synchronous — use for startup/config loading, not hot paths.

    Args:
        root: Directory to search.
        pattern: Glob pattern (default *.md).

    Returns:
        Sorted list of matching paths.
    """
    if not root.exists():
        return []
    return sorted(root.rglob(pattern))
