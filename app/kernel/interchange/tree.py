"""The abstract tree and its two transports: a directory on disk and a ZIP in memory.

One parser over one tree (`ArchiveTree`), built either from a directory or
from ZIP bytes — the format never learns which. Reading is bounded on both
sides: a directory yields only the format's surface (`metadata.json`,
`chapters/*.md`, `kb/*.md`), and an archive whose files would expand past
`MAX_UNCOMPRESSED_BYTES` refuses by name instead of filling memory. Writing is
the mirror: `write_directory` refuses a non-empty target (an existing export
is never shrunk by a thinner re-export) and `zip_bytes` is byte-deterministic
— fixed entry timestamps, names in sorted order — so the same files always
produce the same ZIP.
"""

from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from uuid import uuid4

from app.kernel.interchange.format import METADATA_NAME, ArchiveError

_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
"""The oldest timestamp a ZIP entry may carry; fixed so bytes never drift."""

MAX_UNCOMPRESSED_BYTES = 100_000_000
"""What one archive may expand to, all files together.

The service's 20 000 000-byte cap bounds the upload, not the archive: what
`read()` holds is the entries' declared sizes, and deflate can expand a few
hundred kilobytes a thousandfold. A real novel archive — prose is text, and
text compresses best — stays far under a megabyte, so 100 MB is a thousand
times a genuine archive while still only five times the largest upload that
cap admits: a decompression bomb meets a named refusal, and no legitimate
novel comes near it.
"""

_FORMAT_DIRS = ("chapters", "kb")
"""The only directories the format reads; everything beside them is ignored."""

_TOO_LARGE = f"the archive expands to more than {MAX_UNCOMPRESSED_BYTES} bytes"
"""The one refusal both transports word the same way."""


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
    """Read a directory's format surface into the tree.

    Only what the serializer writes is read — `metadata.json`, `chapters/*.md`
    and `kb/*.md`. Everything else is ignored on purpose: naming a checkout
    (`typing .` as a target) or `/` would otherwise read `.venv`, `.git`,
    `node_modules` or the whole filesystem to answer a question about a novel.
    The files' total size refuses past `MAX_UNCOMPRESSED_BYTES`, before any of
    them is read.
    """
    if not path.is_dir():
        raise FileNotFoundError(str(path))
    surface = [path / METADATA_NAME]
    for directory in _FORMAT_DIRS:
        base = path / directory
        if base.is_dir():
            surface.extend(sorted(base.rglob("*.md")))
    present = [entry for entry in surface if entry.is_file()]
    if sum(entry.stat().st_size for entry in present) > MAX_UNCOMPRESSED_BYTES:
        raise ArchiveError(str(path), _TOO_LARGE)
    return ArchiveTree(
        {entry.relative_to(path).as_posix(): entry.read_bytes() for entry in present}
    )


def open_zip(data: bytes) -> ArchiveTree:
    """Read ZIP bytes into the tree; entries that leave the root are skipped.

    The declared entry sizes are summed first: an archive claiming to expand
    past `MAX_UNCOMPRESSED_BYTES` refuses by name before anything is read.
    Each entry is then read bounded by what is left of the budget, so a header
    that lies low cannot turn `read()` into an unbounded allocation either.
    """
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        infos: list[zipfile.ZipInfo] = []
        for info in bundle.infolist():
            if info.is_dir():
                continue
            parts = PurePosixPath(info.filename).parts
            if not parts or parts[0] == "/" or ".." in parts:
                continue
            infos.append(info)
        declared = 0
        for info in infos:
            declared += info.file_size
            if declared > MAX_UNCOMPRESSED_BYTES:
                raise ArchiveError(info.filename, _TOO_LARGE)
        remaining = MAX_UNCOMPRESSED_BYTES
        for info in infos:
            with bundle.open(info) as handle:
                payload = handle.read(remaining + 1)
            if len(payload) > remaining:
                raise ArchiveError(info.filename, _TOO_LARGE)
            remaining -= len(payload)
            files[info.filename] = payload
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
