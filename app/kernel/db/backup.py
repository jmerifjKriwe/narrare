"""The pre-migration dump — design D5's copy of the database as it was.

Before an upgrade applies pending revisions, the database is dumped in
pg_dump's custom format: a run with pending revisions either produces a
restorable dump or migrates nothing. The dump is a precondition of that
one run, not of the installation — with nothing pending, no dump tool is
ever invoked. ``pg_restore --dbname=<fresh database> <file>`` brings a
dump back; the gates' round-trip test proves it.
"""

import asyncio
import shlex
import subprocess
from datetime import UTC, datetime
from os import environ
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
    """
    template = environ.get("NARRE_BACKUP_COMMAND")
    if template:
        return shlex.split(template.format(url=url, file=file))
    return ["pg_dump", "--format=custom", "--no-owner", "--file", str(file), url]


async def dump_database(database_url: str, directory: Path, *, keep: int = 3) -> Path:
    """Dump one database into ``directory``; return the dump's path.

    The command comes from ``backup_command``; the URL loses ``+asyncpg``,
    which pg_dump does not speak. A command that exits non-zero, cannot
    start, or produces neither a file nor output raises ``BackupFailed`` —
    the caller refuses the migration and nothing was touched. After a
    successful dump only the newest ``keep`` dumps remain.

    The subprocess runs in a worker thread, like the alembic commands: this
    coroutine's loop must stay free.
    """
    directory.mkdir(parents=True, exist_ok=True)
    database = database_url.rsplit("/", 1)[-1]
    file = directory / f"{database}-{datetime.now(UTC):%Y%m%dT%H%M%S%f}.dump"
    command_line = backup_command(database_url.replace("+asyncpg", ""), file)

    def _dump() -> bytes:
        try:
            result = subprocess.run(  # noqa: S603  the operator's own command template
                command_line, capture_output=True, check=False
            )
        except OSError as exc:
            raise BackupFailed(f"{command_line[0]} could not be run: {exc}") from exc
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            raise BackupFailed(stderr or f"{command_line[0]} exited {result.returncode}")
        return result.stdout or b""

    dump = await asyncio.to_thread(_dump)
    if not file.exists() or file.stat().st_size == 0:
        # The command wrote no file of its own — the dump arrived on stdout
        # (the compose form's way through: pg_dump sits inside the database
        # container and cannot write a host path).
        if not dump.strip():
            raise BackupFailed(f"{command_line[0]} produced neither a dump file nor output")
        file.write_bytes(dump)
    dumps = sorted(directory.glob("*.dump"), key=lambda path: path.stat().st_mtime, reverse=True)
    for stale in dumps[keep:]:
        stale.unlink()
    return file
