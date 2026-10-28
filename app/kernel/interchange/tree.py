"""The abstract tree and its two transports: a directory on disk and a ZIP in memory.

One parser over one tree (`ArchiveTree`), built either from a directory or
from ZIP bytes — the format never learns which. Writing is the mirror:
`write_directory` refuses a non-empty target (an existing export is never
shrunk by a thinner re-export) and `zip_bytes` is byte-deterministic — fixed
entry timestamps, names in sorted order — so the same files always produce
the same ZIP.
"""

from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from uuid import uuid4

from app.kernel.interchange.format import ArchiveError

_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
"""The oldest timestamp a ZIP entry may carry; fixed so bytes never drift."""


class ArchiveTree:
    """A parsed archive's files by relative path, transport already forgotten."""

    def __init__(self, files: dict[str, bytes]) -> None:
        self._files = files

    def read_bytes(self, relpath: str) -> bytes:
        """The file's bytes; a missing path raises `FileNotFoundError`."""
        try:
            return self._files[relpath]
        except KeyError:
            raise FileNotFoundError(relpath) from None

    def chapter_names(self) -> list[str]:
        """Every `chapters/*.md` relative path, sorted."""
        return sorted(
            name for name in self._files if name.startswith("chapters/") and name.endswith(".md")
        )

    def kb_names(self) -> list[str]:
        """Every `kb/*.md` relative path, sorted."""
        return sorted(
            name for name in self._files if name.startswith("kb/") and name.endswith(".md")
        )


def open_directory(path: Path) -> ArchiveTree:
    """Read a directory on disk into the tree."""
    if not path.is_dir():
        raise FileNotFoundError(str(path))
    files: dict[str, bytes] = {}
    for entry in sorted(path.rglob("*")):
        if entry.is_file():
            files[entry.relative_to(path).as_posix()] = entry.read_bytes()
    return ArchiveTree(files)


def open_zip(data: bytes) -> ArchiveTree:
    """Read ZIP bytes into the tree; entries that leave the root are skipped."""
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        for info in bundle.infolist():
            if info.is_dir():
                continue
            parts = PurePosixPath(info.filename).parts
            if not parts or parts[0] == "/" or ".." in parts:
                continue
            files[info.filename] = bundle.read(info)
    return ArchiveTree(files)


def write_directory(path: Path, files: dict[str, bytes]) -> None:
    """Write the files under `path`; an existing non-empty target refuses.

    The tree lands in a sibling staging directory and is renamed into place
    only when complete: a write that dies mid-loop (a full disk, a permission
    revoked) leaves no partial target behind, so a retry meets an absent
    target instead of its own debris as `target not empty`.
    """
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ArchiveError(str(path), "target not empty")
    staging = path.with_name(f".{path.name}.tmp-{uuid4().hex}")
    try:
        staging.mkdir(parents=True)
        for relpath, data in files.items():
            target = staging.joinpath(*PurePosixPath(relpath).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if path.exists():
            path.rmdir()  # the guard above leaves only an empty directory here
        staging.rename(path)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def zip_bytes(files: dict[str, bytes]) -> bytes:
    """The files as a deterministic ZIP: sorted names, fixed entry timestamps."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            bundle.writestr(info, files[name])
    return buffer.getvalue()
