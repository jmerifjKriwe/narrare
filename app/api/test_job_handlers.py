"""The lane's handler assembly: a duplicate kind is heard, not silent.

``_job_handlers`` merges every capability's ``jobs.py`` by convention. Two
capabilities registering the same kind is an assembly bug the merge must not
paper over: the later folder keeps the dict's last word, but the merge says
so at startup — a warning naming both sources, the same ``narrare`` logger
the rest of startup uses.
"""

from logging import WARNING
from sys import modules
from types import SimpleNamespace
from typing import TYPE_CHECKING

from app.api import main

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.kernel.jobs.models import Job


async def _alpha(session: AsyncSession, job: Job) -> dict[str, object]:
    return {"from": "alpha"}


async def _beta(session: AsyncSession, job: Job) -> dict[str, object]:
    return {"from": "beta"}


def test_duplicate_job_kinds_warn_naming_both_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Two fake capabilities the convention would find: each folder carries a
    # jobs.py, and each module is seeded straight into sys.modules — the
    # import inside _job_handlers resolves there, so no real code runs.
    for name, handler in (("alpha", _alpha), ("beta", _beta)):
        (tmp_path / name).mkdir()
        (tmp_path / name / "jobs.py").touch()
        monkeypatch.setitem(
            modules, f"app.capabilities.{name}.jobs", SimpleNamespace(handlers={"shared": handler})
        )
    monkeypatch.setattr(main, "CAPABILITIES", tmp_path)

    with caplog.at_level(WARNING, logger="narrare"):
        handlers = main._job_handlers()  # pyright: ignore[reportPrivateUsage]

    assert handlers == {"shared": _beta}  # the later folder keeps the last word
    assert "shared" in caplog.text  # and the merge names the kind…
    assert "alpha" in caplog.text and "beta" in caplog.text  # …and both sources


def test_a_single_registration_stays_silent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "jobs.py").touch()
    monkeypatch.setitem(
        modules, "app.capabilities.alpha.jobs", SimpleNamespace(handlers={"only": _alpha})
    )
    monkeypatch.setattr(main, "CAPABILITIES", tmp_path)

    with caplog.at_level(WARNING, logger="narrare"):
        handlers = main._job_handlers()  # pyright: ignore[reportPrivateUsage]

    assert handlers == {"only": _alpha}
    assert caplog.text == ""
