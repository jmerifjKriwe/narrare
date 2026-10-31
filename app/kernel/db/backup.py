"""The pre-migration dump — design D5's copy of the database as it was.

Before an upgrade applies pending revisions, the database is dumped in
pg_dump's custom format: a run with pending revisions either produces a
restorable dump or migrates nothing. The dump is a precondition of that
one run, not of the installation — with nothing pending, no dump tool is
ever invoked. ``pg_restore --dbname=<fresh database> <file>`` brings a
dump back; the gates' round-trip test proves it.

Everything that can go wrong here — the directory, the command template,
the subprocess, the write — raises ``BackupFailed``, so the caller's one
refusal covers every way a dump cannot be produced.
"""

import asyncio
import shlex
import subprocess
from datetime import UTC, datetime
from os import environ, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class BackupFailed(RuntimeError):  # noqa: N818  the name is the task interface
    """The pre-migration dump could not be produced."""


def backup_command(url: str, file: Path) -> list[str]:
    """The dump command for one database and one target file.

    ``NARRE_BACKUP_COMMAND`` is a template with ``{url}`` and ``{file}``;
    the compose deployment's form runs pg_dump inside the database container,
    where the client lives, and lets the dump arrive on standard output. The
    default runs ``pg_dump`` from PATH and lets it write the file itself —
    ``dump_database`` accepts either: a written file wins, stdout is taken
    when no file appeared.

    A template with a stray brace or an unbalanced quote raises here;
    ``dump_database`` turns that into ``BackupFailed``.
    """
    template = environ.get("NARRE_BACKUP_COMMAND")
    if template:
        command = shlex.split(template.format(url=url, file=file))
        if not command:
            raise BackupFailed("NARRE_BACKUP_COMMAND resolved to an empty command")
        return command
    return ["pg_dump", "--format=custom", "--no-owner", "--file", str(file), url]


async def dump_database(database_url: str, directory: Path, *, keep: int = 3) -> Path:
    """Dump one database into ``directory``; return the dump's path.

    The command comes from ``backup_command``; the URL loses ``+asyncpg``,
    which pg_dump does not speak. Every failure raises ``BackupFailed``: a
    directory that cannot be created or written, a template that cannot be
    resolved, a command that exits non-zero or cannot start, output no
    pg_restore could read, a write that does not land. The dump is written
    to a ``.partial`` sink and renamed into place only once accepted, so a
    failed run never leaves a valid-looking ``*.dump`` behind. After a
    successful dump only the newest ``keep`` dumps remain — the dump just
    written is never its own victim, whatever ``keep`` says.

    The subprocess runs in a worker thread, like the alembic commands: this
    coroutine's loop must stay free. Its stdout streams straight into the
    sink; only stderr (small) is buffered, for the failure message.
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BackupFailed(f"could not create the dump directory {directory}: {exc}") from exc
    database = database_url.rsplit("/", 1)[-1]
    file = directory / f"{database}-{datetime.now(UTC):%Y%m%dT%H%M%S%f}.dump"
    partial = file.with_name(f"{file.name}.partial")
    try:
        try:
            command_line = backup_command(database_url.replace("+asyncpg", ""), file)
        except (KeyError, IndexError, ValueError) as exc:
            raise BackupFailed(
                f"NARRE_BACKUP_COMMAND is not a usable template ({type(exc).__name__}: {exc}); "
                "it must contain the {url} and {file} placeholders, and quote any path "
                "that has spaces"
            ) from exc
        keep = max(keep, 1)
        file_existed_before = file.exists()  # the name is unique per run; it never does

        def _dump() -> None:
            try:
                sink = partial.open("wb")
            except OSError as exc:
                raise BackupFailed(f"could not write the dump to {partial}: {exc}") from exc
            try:
                with sink:
                    try:
                        result = subprocess.run(  # noqa: S603  the operator's own template
                            command_line, stdout=sink, stderr=subprocess.PIPE, check=False
                        )
                    except OSError as exc:
                        raise BackupFailed(f"{command_line[0]} could not be run: {exc}") from exc
            except OSError as exc:
                # The close flushes what run() streamed — ENOSPC and EIO surface
                # there, not inside run(); they are the write's failure, not the
                # command's. A --file target the command managed to fill under
                # those conditions is not trusted either: the run failed, and a
                # failed run leaves nothing that looks like a dump.
                if not file_existed_before:
                    file.unlink(missing_ok=True)
                raise BackupFailed(f"could not write the dump to {partial}: {exc}") from exc
            if result.returncode != 0:
                stderr = result.stderr.decode(errors="replace").strip()
                # A failed pg_dump --file run leaves its (zero-byte) target
                # behind; it must not survive as a dump, and must not evict a
                # restorable one from retention. Only this run's leftover goes.
                if not file_existed_before:
                    file.unlink(missing_ok=True)
                raise BackupFailed(stderr or f"{command_line[0]} exited {result.returncode}")

        await asyncio.to_thread(_dump)
        if not (file.exists() and file.stat().st_size > 0):
            # The dump arrived on stdout (the compose form's way through:
            # pg_dump sits inside the database container and cannot write a
            # host path) — or something that is not a dump did.
            with partial.open("rb") as probe:
                magic = probe.read(5)
            if magic != b"PGDMP":
                # A command that exits 0 with an empty or garbage {file} (a
                # touch, a script echoing prose) leaves exactly the fake-good
                # artifact the --file cleanup above removes; it goes too.
                if not file_existed_before:
                    file.unlink(missing_ok=True)
                raise BackupFailed(
                    f"{command_line[0]} produced neither a dump file nor output a "
                    "pg_restore could read"
                )
            replace(partial, file)

        # Retention, on both paths — the --file form's dump ages just the same.
        dumps = sorted(
            (path for path in directory.glob("*.dump") if path != file),
            key=lambda path: (path.stat().st_mtime, path.name),
            reverse=True,
        )
        for stale in dumps[keep - 1 :]:
            stale.unlink()
        return file
    finally:
        partial.unlink(missing_ok=True)
