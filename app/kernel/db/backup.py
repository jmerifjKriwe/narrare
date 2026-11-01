"""The pre-migration dump — design D5's copy of the database as it was.

Before an upgrade applies pending revisions to a database that holds tables,
the database is dumped in pg_dump's custom format: a run with pending
revisions either produces a restorable dump or migrates nothing. The dump is
a precondition of that one run, not of the installation — with nothing
pending or nothing to protect (an empty first boot takes no dump), no dump
tool is ever invoked. ``pg_restore --dbname=<fresh database> <file>`` brings a
dump back; the gates' round-trip test proves it.

Everything that can go wrong here — the directory, the command template,
the subprocess, the write — raises ``BackupFailed``, so the caller's one
refusal covers every way a dump cannot be produced. The subprocess is
bounded by ``NARRE_BACKUP_TIMEOUT`` (seconds, default 300): a ``pg_dump``
that stalls — or sits at a password prompt — is killed and becomes that
refusal, not a startup that never returns.
"""

import asyncio
import shlex
import subprocess
from datetime import UTC, datetime
from os import environ, replace
from typing import TYPE_CHECKING

from sqlalchemy.engine import make_url

if TYPE_CHECKING:
    from pathlib import Path


class BackupFailed(RuntimeError):  # noqa: N818  the name is the task interface
    """The pre-migration dump could not be produced."""


# Seconds a dump may run before it is killed and the run fails (D5): a
# stalled pg_dump must not block startup forever.
DEFAULT_BACKUP_TIMEOUT = 300.0


def _backup_timeout() -> float:
    """The dump subprocess's budget, from ``NARRE_BACKUP_TIMEOUT`` (seconds)."""
    raw = environ.get("NARRE_BACKUP_TIMEOUT")
    if not raw:
        return DEFAULT_BACKUP_TIMEOUT
    try:
        seconds = float(raw)
    except ValueError:
        raise BackupFailed(
            f"NARRE_BACKUP_TIMEOUT is not a number of seconds: {raw!r}; set it to a "
            "positive number, or unset it for the default "
            f"{DEFAULT_BACKUP_TIMEOUT:g}"
        ) from None
    if seconds <= 0:
        raise BackupFailed(
            f"NARRE_BACKUP_TIMEOUT must be a positive number of seconds, not {raw!r}"
        )
    return seconds


def backup_command(database_url: str, file: Path) -> list[str]:
    """The dump command for one database and one target file.

    ``NARRE_BACKUP_COMMAND`` is a template with ``{url}`` and ``{file}``;
    the compose deployment's form runs pg_dump inside the database container,
    where the client lives, and lets the dump arrive on standard output. The
    default runs ``pg_dump`` from PATH and lets it write the file itself —
    ``dump_database`` accepts either: a written file wins, stdout is taken
    when no file appeared. The URL goes in as the app speaks it and comes
    out as libpq does: ``+asyncpg`` gone, and asyncpg's ``ssl`` option as
    libpq's ``sslmode`` (CodeRabbit round 3, 2026-11-01) — a template's
    ``{url}`` gets the same translation.

    A template with a stray brace or an unbalanced quote raises here;
    ``dump_database`` turns that into ``BackupFailed``.
    """
    url = _libpq_url(database_url)
    template = environ.get("NARRE_BACKUP_COMMAND")
    if template:
        command = shlex.split(template.format(url=url, file=file))
        if not command:
            raise BackupFailed("NARRE_BACKUP_COMMAND resolved to an empty command")
        return command
    return ["pg_dump", "--format=custom", "--no-owner", "--file", str(file), url]


def _libpq_url(database_url: str) -> str:
    """The URL as libpq's pg_dump speaks it: ``+asyncpg`` gone, ``ssl`` renamed.

    The asyncpg dialect spells the TLS option ``ssl``; libpq knows
    ``sslmode``. A URL that reached pg_dump as ``?ssl=require`` died on the
    unknown parameter, and a database reachable only over TLS never got its
    dump (CodeRabbit round 3, 2026-11-01). The value vocabulary is shared
    (require, prefer, disable, verify-ca, verify-full), so the key is the
    only difference: an ``ssl`` becomes ``sslmode``; an ``sslmode`` already
    present stays untouched and a duplicate ``ssl`` is dropped rather than
    sent twice; every other parameter passes through.
    """
    url = make_url(database_url.replace("+asyncpg", ""))
    query = dict(url.query)
    if "ssl" in query:
        value = query.pop("ssl")
        query.setdefault("sslmode", value)
    return url.set(query=query).render_as_string(hide_password=False)


async def dump_database(database_url: str, directory: Path, *, keep: int = 3) -> Path:
    """Dump one database into ``directory``; return the dump's path.

    The command comes from ``backup_command``, which hands pg_dump a URL it
    speaks: ``+asyncpg`` gone, and asyncpg's ``ssl`` option as libpq's
    ``sslmode``. Every failure raises ``BackupFailed``: a
    directory that cannot be created or written, a template that cannot be
    resolved, a command that exits non-zero or cannot start, a command that
    outlives ``NARRE_BACKUP_TIMEOUT`` (seconds, default 300), output no
    pg_restore could read — acceptance is the ``PGDMP`` magic and then
    ``pg_restore --list``, so a truncated archive is refused as roundly as
    a non-dump — a write that does not land. The dump is written
    to a ``.partial`` sink and renamed into place only once accepted, so a
    failed run never leaves a valid-looking ``*.dump`` behind. After a
    successful dump only the newest ``keep`` dumps *of this database* remain
    — the filename prefix carries the database, so dumps another stack keeps
    in the same directory are never eviction victims (CodeRabbit round 1,
    2026-11-01) — and the dump just written is never its own victim,
    whatever ``keep`` says.

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
            command_line = backup_command(database_url, file)
        except (KeyError, IndexError, ValueError) as exc:
            raise BackupFailed(
                f"NARRE_BACKUP_COMMAND is not a usable template ({type(exc).__name__}: {exc}); "
                "it must contain the {url} and {file} placeholders, and quote any path "
                "that has spaces"
            ) from exc
        keep = max(keep, 1)
        file_existed_before = file.exists()  # the name is unique per run; it never does
        # The timeout is resolved before the sink is opened: a bad
        # NARRE_BACKUP_TIMEOUT must not leave a file descriptor behind.
        # The acceptance probe's pg_restore runs under the same budget.
        timeout = _backup_timeout()

        def _dump() -> None:
            try:
                sink = partial.open("wb")
            except OSError as exc:
                raise BackupFailed(f"could not write the dump to {partial}: {exc}") from exc
            try:
                with sink:
                    try:
                        result = subprocess.run(  # noqa: S603  the operator's own template
                            command_line,
                            stdout=sink,
                            stderr=subprocess.PIPE,
                            check=False,
                            timeout=timeout,
                        )
                    except subprocess.TimeoutExpired as exc:
                        # The stalled run's leftovers go the way every failed
                        # run's leftovers go: gone (the name is unique per
                        # run; this file was never pre-existing).
                        if not file_existed_before:
                            file.unlink(missing_ok=True)
                        raise BackupFailed(
                            f"{command_line[0]} did not finish within {timeout:g}s "
                            f"(NARRE_BACKUP_TIMEOUT); a dump that stalls — or sits at a "
                            "password prompt — is killed here instead of blocking startup"
                        ) from exc
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
        # Acceptance is two probes on whichever artifact the run left — the
        # --file form's own target, or the stdout partial when no file
        # appeared. The first is cheap: the ``PGDMP`` magic, which refuses
        # the prose a command wrote into ``{file}`` (``pg_dump`` without
        # ``--format=custom``) without paying for a subprocess. The second
        # is the proof: ``pg_restore --list`` reads the archive's table of
        # contents with the toolchain the restore itself needs, so a
        # truncated or corrupt archive — the magic on five intact bytes, a
        # cut TOC behind them — is refused where the magic alone passed it
        # (CodeRabbit round 3, 2026-11-01).
        artifact = file if file.exists() and file.stat().st_size > 0 else partial
        with artifact.open("rb") as probe:
            magic = probe.read(5)
        if magic != b"PGDMP":
            # The refused artifact goes the way every failed run's leftover
            # goes: gone — unless it pre-existed (the name is unique per
            # run; it never does).
            if not file_existed_before:
                file.unlink(missing_ok=True)
            raise BackupFailed(
                f"{command_line[0]} produced neither a dump file nor output a pg_restore could read"
            )
        try:
            listing = await asyncio.to_thread(
                subprocess.run,
                ["pg_restore", "--list", str(artifact)],
                capture_output=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise BackupFailed(
                f"pg_restore did not finish within {timeout:g}s "
                f"(NARRE_BACKUP_TIMEOUT); an unreadable dump is not accepted"
            ) from exc
        except OSError as exc:
            raise BackupFailed(
                f"pg_restore could not be run: {exc}; install postgresql-client "
                "so the dump can be checked"
            ) from exc
        if listing.returncode != 0:
            # The refusal's cleanup is the magic probe's: the finally takes
            # the partial, and a --file target the command filled is
            # unlinked here — nothing survives that looks like a dump.
            if not file_existed_before:
                file.unlink(missing_ok=True)
            stderr = listing.stderr.decode(errors="replace").strip()
            raise BackupFailed(
                "the dump is unreadable — truncated or corrupt (pg_restore --list "
                f"exited {listing.returncode}: {stderr or 'no message'}); nothing "
                "migrates without a restorable copy"
            )
        if artifact is partial:
            replace(partial, file)

        # Retention, on both paths — the --file form's dump ages just the same.
        # Only this database's dumps count: the filename prefix carries the
        # database, and another stack's dumps sharing the directory are not
        # eviction victims (CodeRabbit round 1, 2026-11-01).
        dumps = sorted(
            (
                path
                for path in directory.glob("*.dump")
                if path != file and path.name.startswith(f"{database}-")
            ),
            key=lambda path: (path.stat().st_mtime, path.name),
            reverse=True,
        )
        for stale in dumps[keep - 1 :]:
            stale.unlink()
        return file
    finally:
        partial.unlink(missing_ok=True)
