"""Publish a completed capture without ever splitting the two outputs.

``scripts.screenshots`` captures into a staging directory and then hands both
payloads here: the master directory and the rendered collection index. This
module replaces both canonical outputs together, or leaves both previous
outputs in place.

Each output is backed up on its own filesystem — the masters beside the
masters, the index beside the index — so moving a backup is a rename and never
a cross-device copy that ``EXDEV`` would reject (#987). A staged payload that
lives elsewhere is copied onto the output's filesystem before it is swapped in,
so the publication itself only ever renames within one device.

Backups outlive a failed publication until a complete restore has put both
previous outputs back. A rollback that cannot finish keeps the last good copy,
and the error names the preserved backup directories. An output that is itself
a mount point cannot be replaced by a sibling rename, so publication refuses
that layout before it creates a backup or moves data.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.screenshot_manifest import SHOTS

if TYPE_CHECKING:
    from collections.abc import Callable

    Remove = Callable[[Path], None]
    Device = Callable[[Path], int]


def _device(path: Path) -> int:
    """The filesystem a path lives on; tests inject a lookup, not timing."""
    return path.stat().st_dev


def _swap(source: Path, target: Path) -> None:
    """Replace ``target`` with ``source``; both must sit on one filesystem."""
    os.replace(source, target)


def _move(source: Path, target: Path) -> None:
    """Move one output or backup; a rename on the output's own filesystem."""
    os.replace(source, target)


def _remove(path: Path) -> None:
    """Remove a file or directory if it exists."""
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _write_index_temp(index: Path, text: str) -> Path:
    """Write the overview beside its target; the caller replaces atomically."""
    index.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{index.name}-", dir=index.parent)
    path = Path(name)
    try:
        handle = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
    except BaseException:
        os.close(descriptor)
        path.unlink(missing_ok=True)
        raise
    try:
        with handle:
            handle.write(text)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def _require_complete(staged: Path) -> None:
    """Refuse a capture that does not match the manifest, before moving anything."""
    expected = {shot.filename for shot in SHOTS}
    actual = {path.name for path in staged.iterdir()}
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise SystemExit(
            f"the capture set does not match the manifest: missing={missing} extra={extra}"
        )


def _backup_root(target: Path) -> Path:
    """A holding directory in ``target``'s parent, on the target's filesystem."""
    return Path(tempfile.mkdtemp(prefix=f".{target.name}-backup-", dir=target.parent))


def _require_sibling_device(target: Path, *, device: Device) -> None:
    """Refuse an output that is its own mount, where a sibling backup cannot live.

    Publication moves the previous output into a backup beside the target, so
    the target and its parent must be one filesystem. A mount point at the
    target itself would make that rename an ``EXDEV`` copy after data has
    already moved; refuse it while both outputs are still untouched.
    """
    if not target.exists():
        return
    if device(target) == device(target.parent):
        return
    raise RuntimeError(
        f"{target} is on a different filesystem than its parent {target.parent}: "
        "publication keeps each backup beside its output, so an output that is "
        "itself a mount point cannot be replaced by a sibling rename. Move the "
        "output onto its parent's filesystem."
    )


def _stage_beside(source: Path, target: Path, *, device: Device) -> Path:
    """A staged payload on ``target``'s filesystem, copied when it is elsewhere."""
    if device(source) == device(target.parent):
        return source
    stage = Path(tempfile.mkdtemp(prefix=f".{target.name}-stage-", dir=target.parent))
    staged = stage / source.name
    try:
        if source.is_dir():
            shutil.copytree(source, staged, symlinks=True)
        else:
            shutil.copy2(source, staged)
    except BaseException:
        # A half-written copy is not a publication input; remove it here so a
        # failed copy cannot strand a staging directory beside the output.
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return staged


def _attempt(action: str, operation: Callable[..., None], *paths: Path) -> list[str]:
    """Run one rollback step; a failure is recorded, and the next step still runs.

    Only ordinary exceptions are recorded. ``KeyboardInterrupt`` (and any other
    ``BaseException``) propagates: an operator stopping the process outranks a
    best-effort rollback, and the backup roots stay untouched.
    """
    try:
        operation(*paths)
    except Exception as error:
        return [f"{action} failed ({error})"]
    return []


def publish(
    masters: Path,
    index: Path,
    staged_masters: Path,
    staged_index: Path,
    *,
    swap: Callable[[Path, Path], None] | None = None,
    move: Callable[[Path, Path], None] | None = None,
    remove: Remove | None = None,
    device: Device | None = None,
) -> None:
    """Replace both outputs only after a full capture, with a joint rollback.

    The previous masters and the previous index move into their own backup
    directories first, each beside its output; both backups stay until the new
    masters and the new index have landed or both previous outputs are back.
    Any failure removes whatever new output was written and restores both
    previous outputs. A restore that cannot finish keeps the backup containing
    the last good copy, and the raised error names it.

    ``swap`` replaces an output with its staged payload; ``move`` moves outputs
    and backups; ``remove`` deletes a partially published output; ``device``
    answers which filesystem a path is on. The defaults are the module's own
    functions, resolved at call time, so tests may inject or monkeypatch them
    without filesystem timing tricks.
    """
    swap = swap or _swap
    move = move or _move
    remove = remove or _remove
    device = device or _device

    _require_complete(staged_masters)
    masters.parent.mkdir(parents=True, exist_ok=True)
    index.parent.mkdir(parents=True, exist_ok=True)
    # Check the sibling-backup assumption while both outputs are untouched.
    _require_sibling_device(masters, device=device)
    _require_sibling_device(index, device=device)

    # Both backup roots exist before the index is staged: a root that cannot be
    # created leaves no temporary index behind. A root that was created but is
    # still empty is safe to discard.
    masters_backup = _backup_root(masters)
    try:
        index_backup = _backup_root(index)
    except BaseException:
        shutil.rmtree(masters_backup, ignore_errors=True)
        raise

    staged_dirs: set[Path] = set()
    staged_index_temp: Path | None = None
    safe_to_discard = False
    try:
        try:
            staged = _stage_beside(staged_masters, masters, device=device)
            if staged.parent != staged_masters.parent:
                staged_dirs.add(staged.parent)
            # The index content is written beside its target, so its swap is a
            # rename even when the capture staged it on another filesystem.
            staged_index_temp = _write_index_temp(index, staged_index.read_text(encoding="utf-8"))
        except BaseException:
            # Nothing has moved yet, so the backup roots hold no output.
            safe_to_discard = True
            raise

        previous_masters = masters_backup / "masters"
        previous_index = index_backup / "index"
        had_masters = masters.exists()
        had_index = index.exists()
        moved_masters = False
        moved_index = False

        def rollback() -> list[str]:
            """Remove new outputs and restore both previous outputs."""
            failures: list[str] = []
            if moved_masters or not had_masters:
                failures += _attempt("removing the new masters", remove, masters)
            if moved_index or not had_index:
                failures += _attempt("removing the new index", remove, index)
            if moved_masters:
                failures += _attempt(
                    "restoring the previous masters", move, previous_masters, masters
                )
            if moved_index:
                failures += _attempt("restoring the previous index", move, previous_index, index)
            return failures

        try:
            if had_masters:
                move(masters, previous_masters)
                moved_masters = True
            if had_index:
                move(index, previous_index)
                moved_index = True
            swap(staged, masters)
            swap(staged_index_temp, index)
        except BaseException as error:
            failures = rollback()
            if failures:
                raise RuntimeError(
                    f"publish failed ({error}); previous outputs kept in "
                    f"{masters_backup} and {index_backup} "
                    f"(a root is empty when that output was already restored): "
                    f"{'; '.join(failures)}"
                ) from error
            safe_to_discard = True
            raise
        safe_to_discard = True
    finally:
        if staged_index_temp is not None:
            # Best-effort by design: a leftover hidden temp is recoverable and
            # must never replace the publication or rollback error, nor skip
            # the staged-directory and backup cleanup below. Interrupts still
            # propagate because only ordinary exceptions are suppressed.
            with contextlib.suppress(Exception):
                staged_index_temp.unlink(missing_ok=True)
        for staging in staged_dirs:
            shutil.rmtree(staging, ignore_errors=True)
        if safe_to_discard:
            shutil.rmtree(masters_backup, ignore_errors=True)
            shutil.rmtree(index_backup, ignore_errors=True)
