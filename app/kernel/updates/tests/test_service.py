"""The update service against a real database and a real release source.

The product's promises: a newer release is announced, a dismissed one is not,
an outage keeps the last known answer, a disabled check touches nothing, the
interval decides when the source is asked, and a prerelease is never announced.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID  # noqa: TC003

import pytest
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.contracts.user import User
from app.kernel.testing.release_vendor import ReleaseVendor  # noqa: TC001
from app.kernel.updates.service import UpdateService
from app.kernel.version import __version__

pytestmark = pytest.mark.timeout(30)


async def test_a_newer_release_is_available(
    session: AsyncSession, user: UUID, vendor: ReleaseVendor
) -> None:
    answer = await UpdateService(session, user).read(force=True)

    assert answer.current_version == __version__
    assert answer.latest_version == "v999.0.0"
    assert answer.update_available is True
    assert answer.release_notes == "## Notes\n\n- new"
    assert answer.release_url == "https://example.test/release"
    assert answer.dismissed is False
    assert answer.checked_at is not None

    stored = await session.get(User, user)
    assert stored is not None
    assert stored.last_known_latest_version == "v999.0.0"
    assert stored.last_known_release_notes == "## Notes\n\n- new"
    assert stored.last_known_release_url == "https://example.test/release"
    assert stored.last_update_check_at is not None


async def test_a_dismissed_version_is_not_available(
    session: AsyncSession, user: UUID, vendor: ReleaseVendor
) -> None:
    service = UpdateService(session, user)
    await service.dismiss("v999.0.0")

    answer = await service.read(force=False)

    assert answer.latest_version == "v999.0.0"
    assert answer.update_available is False
    assert answer.dismissed is True


async def test_a_version_newer_than_the_dismissed_one_reappears(
    session: AsyncSession, user: UUID, vendor: ReleaseVendor
) -> None:
    service = UpdateService(session, user)
    await service.dismiss("v998.0.0")

    answer = await service.read(force=True)

    assert answer.update_available is True
    assert answer.dismissed is False


async def test_a_prerelease_tag_is_not_announced(
    session: AsyncSession, user: UUID, vendor: ReleaseVendor
) -> None:
    vendor.state["tag"] = "v999.0.0-rc.1"

    answer = await UpdateService(session, user).read(force=True)

    assert answer.latest_version == "v999.0.0-rc.1"
    assert answer.update_available is False


async def test_an_over_long_tag_answers_no_update(
    session: AsyncSession, user: UUID, vendor: ReleaseVendor
) -> None:
    """The version column is 64 characters; a longer tag is not announced and
    the check still answers, never a ``DataError`` at the write."""
    vendor.state["tag"] = "v" * 65

    answer = await UpdateService(session, user).read(force=True)

    assert answer.latest_version is None
    assert answer.update_available is False
    assert answer.checked_at is not None

    stored = await session.get(User, user)
    assert stored is not None
    assert stored.last_known_latest_version is None


async def test_an_over_long_release_url_answers_no_update(
    session: AsyncSession, user: UUID, vendor: ReleaseVendor
) -> None:
    """The release-link column is 2048 characters; a longer link is unusable
    too, and the read stays an answer rather than a database error."""
    vendor.state["url"] = "https://example.test/" + "a" * 2049

    answer = await UpdateService(session, user).read(force=True)

    assert answer.latest_version is None
    assert answer.update_available is False
    assert answer.release_url is None


async def test_a_failed_fetch_keeps_the_last_known_answer(
    session: AsyncSession, user: UUID, vendor: ReleaseVendor
) -> None:
    service = UpdateService(session, user)
    first = await service.read(force=True)
    assert first.update_available is True

    vendor.status = 500
    second = await service.read(force=True)

    assert second.latest_version == first.latest_version
    assert second.release_notes == first.release_notes
    assert second.release_url == first.release_url
    assert second.update_available is True


async def test_a_failed_first_fetch_answers_no_update(
    session: AsyncSession, user: UUID, vendor: ReleaseVendor
) -> None:
    """An outage on a row that never heard an answer is the silent no-update:
    the route still answers 200, never an exception."""
    vendor.status = 500

    answer = await UpdateService(session, user).read(force=True)

    assert answer.latest_version is None
    assert answer.update_available is False
    assert answer.checked_at is not None


async def test_a_malformed_url_answers_no_update(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession, user: UUID
) -> None:
    """A bad configured URL is a fetch failure too, not a 500."""
    monkeypatch.setenv("NARRE_UPDATE_CHECK_URL", "http://[::1")

    answer = await UpdateService(session, user).read(force=True)

    assert answer.latest_version is None
    assert answer.update_available is False


async def test_a_disabled_url_answers_no_update(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession, user: UUID
) -> None:
    monkeypatch.setenv("NARRE_UPDATE_CHECK_URL", "off")

    answer = await UpdateService(session, user).read(force=True)

    assert answer.latest_version is None
    assert answer.update_available is False
    assert answer.checked_at is None

    stored = await session.get(User, user)
    assert stored is not None
    assert stored.last_update_check_at is None
    assert stored.last_known_latest_version is None


async def test_an_empty_url_answers_no_update(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession, user: UUID
) -> None:
    monkeypatch.setenv("NARRE_UPDATE_CHECK_URL", "")

    answer = await UpdateService(session, user).read(force=True)

    assert answer.update_available is False
    assert answer.checked_at is None


async def test_the_interval_skips_the_fetch_until_due(
    session: AsyncSession, user: UUID, vendor: ReleaseVendor
) -> None:
    stored = await session.get(User, user)
    assert stored is not None
    stored.last_update_check_at = datetime.now(UTC) - timedelta(days=1)
    await session.commit()
    service = UpdateService(session, user)

    skipped = await service.read(force=False)

    assert vendor.received == []
    assert skipped.latest_version is None

    stored.last_update_check_at = datetime.now(UTC) - timedelta(days=8)
    await session.commit()

    fetched = await service.read(force=False)

    assert vendor.received != []
    assert fetched.latest_version == "v999.0.0"
    assert fetched.update_available is True


async def test_the_cache_spares_the_source_a_second_fetch(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    user: UUID,
    vendor: ReleaseVendor,
) -> None:
    monkeypatch.setenv("NARRE_UPDATE_CHECK_CACHE_SECONDS", "3600")
    service = UpdateService(session, user)

    await service.read(force=True)
    await service.read(force=True)

    assert len(vendor.received) == 1
