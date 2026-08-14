"""Shared pandoc subprocess helper — the SOLE site the ``pandoc`` binary is
spawned (RULE-08 / ADR-081).

RULE-08 (mechanically enforced by
``scripts/architecture/_checkers/export_binary_confinement.py``): no module other
than this one and the two pandoc renderer adapters (``pandoc_md.py``,
``pandoc_epub.py``) that import from it may spawn a pandoc subprocess. The two
adapters call :func:`run_pandoc` here rather than spawning pandoc themselves —
this function is the single ``asyncio.create_subprocess_exec("pandoc", ...)``
site the checker's ``export_binary_allowed_modules`` list exempts.

Binary-name SSOT: :data:`PANDOC_BINARY` carries the literal ``"pandoc"`` and is
the argv[0] element of the spawn. The module is RULE-08-exempt, so the checker
passes regardless of literal-vs-name; keeping the literal in the constant
assignment (rather than building it dynamically) honours the checker's
documented static-resolution limitation (it matches string literals, not
variable reads, so a deliberately evasive ``"pan" + "doc"`` would slip past —
we never do that).

Every failure mode converts to a typed :class:`ExportRenderError` (RULE-11):
non-zero exit, timeout, or the binary vanishing between the ``is_available()``
probe and the spawn. Pandoc never produces partial/wrong output silently.

Non-LLM (no ``narrare_core.agents`` / ``narrare_core.prompts`` imports).
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import structlog

from narrare.export.errors import ExportRenderError

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = structlog.get_logger(__name__)

#: The production render binary this adapter owns. Module-level SSOT so the
#: argv[0] and the RULE-08 allowed-modules documentation share one name. The
#: literal ``"pandoc"`` lives here (never constructed dynamically — see the
#: checker's documented static-resolution limitation).
PANDOC_BINARY = "pandoc"

#: Generous default render timeout (seconds). Manuscripts can be large (hundreds
#: of chapters) and pandoc is fast, but a stuck process must surface as a typed
#: :class:`ExportRenderError` (RULE-11) rather than hang an export job forever.
#: Overridable per call (the failure-path test passes a tiny value).
DEFAULT_TIMEOUT_SECONDS: float = 120.0

#: How many trailing stderr characters to retain in the typed error message.
#: Pandoc's stderr can be verbose; we keep the actionable tail so a logged
#: ``ExportRenderError`` stays queryable (RULE-11) without dumping megabytes.
#: An internal error-formatting detail (1 KiB tail), not a deployment knob —
#: annotated to match the file's other module constants (RULE-18).
_STDERR_TAIL_CHARS: int = 1024


async def run_pandoc(
    argv: Sequence[str],
    stdin_data: bytes,
    *,
    format_label: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> bytes:
    """Run ``pandoc`` with ``argv``, feeding ``stdin_data`` on stdin.

    THE single ``asyncio.create_subprocess_exec("pandoc", ...)`` site (RULE-08).
    The two renderer adapters (:mod:`narrare.export.renderers.pandoc_md`,
    :mod:`narrare.export.renderers.pandoc_epub`) call this helper instead of
    spawning pandoc themselves.

    Args:
        argv: pandoc arguments WITHOUT the binary name (e.g.
            ``["--from=html", "--to=gfm"]``); the helper prepends
            :data:`PANDOC_BINARY`.
        stdin_data: bytes piped to pandoc's stdin (the semantic-HTML payload).
        format_label: the :class:`~narrare.export.options.ExportFormat` value
            (e.g. ``"md"``) carried into the typed error for log clarity.
        timeout_seconds: kill the process after this many seconds and raise
            :class:`ExportRenderError`. Defaults to
            :data:`DEFAULT_TIMEOUT_SECONDS`.

    Returns:
        pandoc's stdout bytes.

    Raises:
        ExportRenderError: on non-zero exit, timeout, or OS-level spawn
            failure (e.g. the binary removed after the availability probe).
    """
    full_argv: list[str] = [PANDOC_BINARY, *argv]
    try:
        proc = await asyncio.create_subprocess_exec(
            *full_argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        # is_available() should have guarded this; a TOCTOU removal between the
        # probe and the spawn still surfaces as a typed error (RULE-11).
        raise ExportRenderError(
            f"pandoc for format '{format_label}' is not installed: {exc}"
        ) from exc

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=stdin_data),
            timeout=timeout_seconds,
        )
    except TimeoutError as exc:
        # Reap the timed-out process so pandoc never leaks as a zombie; the
        # typed error is the signal a client polls (RULE-11 queryable failure).
        await _terminate(proc)
        raise ExportRenderError(
            f"pandoc for format '{format_label}' timed out after {timeout_seconds}s and was killed."
        ) from exc

    if proc.returncode != 0:
        tail = stderr.decode("utf-8", errors="replace").strip()[-_STDERR_TAIL_CHARS:]
        raise ExportRenderError(
            f"pandoc for format '{format_label}' exited {proc.returncode}: {tail}"
        )
    return stdout


async def _terminate(proc: asyncio.subprocess.Process) -> None:
    """Kill + reap a pandoc process so a timeout never leaks a zombie.

    Best-effort: a ``ProcessLookupError`` (process already gone) is suppressed
    both for the signal and the wait — the goal is purely "don't leave a stuck
    pandoc", and a reaped process is already that goal met.
    """
    with contextlib.suppress(ProcessLookupError):
        proc.kill()
    with contextlib.suppress(ProcessLookupError):
        await proc.wait()
