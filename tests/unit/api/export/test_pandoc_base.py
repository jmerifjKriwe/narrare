"""Unit tests for the shared pandoc subprocess helper (RULE-08 / ADR-081).

The confinement site :func:`narrare.export.renderers.pandoc_base.run_pandoc`
converts every failure mode to a typed :class:`ExportRenderError` (RULE-11).
The failure paths here use a fake process (no real pandoc, no I/O); one
smoke test exercises the real binary behind a ``skipif`` guard so the suite
stays green where the toolchain is absent.
"""

from __future__ import annotations

import asyncio
import shutil

import pytest

from narrare.export.errors import ExportRenderError
from narrare.export.renderers import pandoc_base
from narrare.export.renderers.pandoc_base import run_pandoc

_REQUIRES_PANDOC = pytest.mark.skipif(
    shutil.which("pandoc") is None,
    reason="pandoc not installed (install via scripts/install_export_toolchain.sh)",
)


class _FakeProc:
    """Minimal stand-in for ``asyncio.subprocess.Process``.

    Records ``kill``/``wait`` so the timeout test can prove the helper reaps a
    stuck process. ``communicate_delay`` lets a test force the timeout branch.
    """

    def __init__(
        self,
        *,
        returncode: int = 0,
        stdout: bytes = b"",
        stderr: bytes = b"",
        communicate_delay: float = 0.0,
    ) -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self._delay = communicate_delay
        self.killed = False
        self.waited = False

    async def communicate(self, input: bytes | None = None) -> tuple[bytes, bytes]:
        if self._delay:
            await asyncio.sleep(self._delay)
        return self._stdout, self._stderr

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        self.waited = True
        return self.returncode


def _patch_spawn(
    monkeypatch: pytest.MonkeyPatch,
    proc: _FakeProc | None = None,
    *,
    spawn_raises: BaseException | None = None,
) -> None:
    """Replace ``asyncio.create_subprocess_exec`` with a controllable fake."""

    async def fake_exec(*args: object, **kwargs: object) -> _FakeProc:
        if spawn_raises is not None:
            raise spawn_raises
        assert proc is not None
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)


class TestRunPandocSuccess:
    @_REQUIRES_PANDOC
    @pytest.mark.asyncio
    async def test_real_invocation_returns_stdout(self) -> None:
        """Smoke test against the real binary (HTML → GFM)."""
        stdout = await run_pandoc(
            ["--from=html", "--to=gfm"],
            b"<p>hello world</p>",
            format_label="md",
        )
        assert b"hello world" in stdout

    @pytest.mark.asyncio
    async def test_success_returns_stdout_bytes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        proc = _FakeProc(returncode=0, stdout=b"# Title\n\nbody\n", stderr=b"")
        _patch_spawn(monkeypatch, proc)

        result = await run_pandoc(["--from=html", "--to=gfm"], b"<p>x</p>", format_label="md")

        assert result == b"# Title\n\nbody\n"


class TestRunPandocFailures:
    @pytest.mark.asyncio
    async def test_nonzero_exit_raises_with_stderr_tail(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proc = _FakeProc(
            returncode=2,
            stdout=b"",
            stderr=b"Pandoc error: cannot parse input at line 3\n",
        )
        _patch_spawn(monkeypatch, proc)

        with pytest.raises(ExportRenderError) as exc_info:
            await run_pandoc(["--from=html", "--to=gfm"], b"garbage", format_label="md")

        msg = str(exc_info.value)
        assert "md" in msg  # format label carried into the typed error
        assert "exited 2" in msg
        assert "cannot parse input" in msg  # stderr tail retained

    @pytest.mark.asyncio
    async def test_timeout_raises_and_kills_process(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # communicate() blocks long past the tiny timeout → timeout branch.
        proc = _FakeProc(returncode=0, communicate_delay=5.0)
        _patch_spawn(monkeypatch, proc)

        with pytest.raises(ExportRenderError) as exc_info:
            await run_pandoc(
                ["--from=html", "--to=gfm"],
                b"<p>x</p>",
                format_label="md",
                timeout_seconds=0.05,
            )

        assert "timed out" in str(exc_info.value)
        assert proc.killed is True  # reaped — no zombie pandoc leaked
        assert proc.waited is True

    @pytest.mark.asyncio
    async def test_missing_binary_raises_not_installed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # TOCTOU: is_available() passed but the binary vanished before spawn.
        _patch_spawn(monkeypatch, spawn_raises=FileNotFoundError("pandoc"))

        with pytest.raises(ExportRenderError) as exc_info:
            await run_pandoc(["--version"], b"", format_label="md")

        assert "not installed" in str(exc_info.value)


def test_pandoc_binary_constant_is_the_literal() -> None:
    """The argv[0] SSOT carries the literal 'pandoc' (RULE-08 + checker note)."""
    assert pandoc_base.PANDOC_BINARY == "pandoc"
