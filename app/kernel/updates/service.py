"""The update check: ask the release source when it is due, remember the answer.

The check is a convenience, never a gate (design 2026-11-24): the app works
offline, a failed fetch is silent, and the last known release stays readable.
The release source is configuration — ``NARRA_UPDATE_CHECK_URL``, with ``off``
or an empty value disabling the check — so the tests and the E2E stack name a
local server instead of GitHub. The module cache, one hour by default, spares
the unauthenticated GitHub quota a reload storm would spend; the answer also
lives on the user row, so it survives a restart.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from os import environ
from time import monotonic
from typing import Any, cast
from uuid import UUID  # noqa: TC003

import httpx
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.auth import SetupRequiredError
from app.kernel.contracts.user import User
from app.kernel.updates.schemas import UpdateRead
from app.kernel.updates.semver import is_newer
from app.kernel.version import __version__

DEFAULT_URL = "https://api.github.com/repos/jmerifjKriwe/narrare/releases/latest"
DEFAULT_CACHE_SECONDS = 3600.0


@dataclass(frozen=True)
class Release:
    """One release as the source names it; the tag is the version compared."""

    tag: str
    notes: str | None
    url: str | None


_CACHE: dict[str, tuple[float, Release | None]] = {}
"""The source URL -> (when it was fetched, the answer); a process-lifetime cache."""


def reset_cache() -> None:
    """Forget every cached answer; the tests call this between their sources."""
    _CACHE.clear()


def _check_url() -> str | None:
    """The release source, or ``None`` when the check is disabled."""
    url = environ.get("NARRA_UPDATE_CHECK_URL", DEFAULT_URL).strip()
    if not url or url.lower() == "off":
        return None
    return url


def _cache_seconds() -> float:
    """The in-memory cache's TTL; zero disables it, a bad value takes the default."""
    raw = environ.get("NARRA_UPDATE_CHECK_CACHE_SECONDS", str(DEFAULT_CACHE_SECONDS)).strip()
    try:
        return max(float(raw), 0.0)
    except ValueError:
        return DEFAULT_CACHE_SECONDS


async def _fetch(url: str) -> Release | None:
    """The release at ``url``, served from the cache while its TTL holds."""
    seconds = _cache_seconds()
    if seconds > 0:
        cached = _CACHE.get(url)
        if cached is not None and monotonic() - cached[0] < seconds:
            return cached[1]
    release = await _download(url)
    if seconds > 0:
        _CACHE[url] = (monotonic(), release)
    return release


async def _download(url: str) -> Release | None:
    """Ask the source; any failure is the silent "nothing new" answer."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"narrare/{__version__}",
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            payload: Any = response.json()
    except httpx.HTTPError, httpx.InvalidURL, ValueError:
        return None
    return _release(payload)


def _release(payload: Any) -> Release | None:
    """A GitHub release body as the fields the app keeps, or nothing usable."""
    if not isinstance(payload, dict):
        return None
    fields = cast("dict[str, object]", payload)
    tag = fields.get("tag_name")
    if not isinstance(tag, str) or not tag.strip():
        return None
    notes = fields.get("body")
    link = fields.get("html_url")
    return Release(
        tag=tag.strip(),
        notes=notes if isinstance(notes, str) else None,
        url=link if isinstance(link, str) and link.strip() else None,
    )


class UpdateService:
    """One user's update check: the due decision, the fetch and the answer."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id

    async def read(self, *, force: bool) -> UpdateRead:
        """The last known release; ask the source when it is due or forced.

        A disabled check answers without reading or writing the user row, so
        an instance that opts out touches nothing. A fetch that fails keeps the
        stored release fields and still stamps the attempt: the interval is
        honoured either way, and the answer is never an error.
        """
        url = _check_url()
        if url is None:
            return _no_update()

        user = await self.session.get(User, self.user_id)
        if user is None:
            raise SetupRequiredError

        if self._due(user, force):
            release = await _fetch(url)
            if release is not None:
                user.last_known_latest_version = release.tag
                user.last_known_release_notes = release.notes
                user.last_known_release_url = release.url
            user.last_update_check_at = datetime.now(UTC)
            await self.session.commit()

        return self._answer(user)

    async def dismiss(self, version: str) -> UpdateRead:
        """Stop announcing ``version``; a newer release announces again."""
        user = await self.session.get(User, self.user_id)
        if user is None:
            raise SetupRequiredError
        user.dismissed_update_version = version
        await self.session.commit()
        return self._answer(user)

    @staticmethod
    def _due(user: User, force: bool) -> bool:
        """Whether the interval has run out — or never started, or is forced."""
        if force or user.last_update_check_at is None:
            return True
        due_at = user.last_update_check_at + timedelta(days=user.update_check_interval_days)
        return due_at <= datetime.now(UTC)

    @staticmethod
    def _answer(user: User) -> UpdateRead:
        latest = user.last_known_latest_version
        dismissed = latest is not None and user.dismissed_update_version == latest
        return UpdateRead(
            current_version=__version__,
            latest_version=latest,
            update_available=(
                latest is not None and not dismissed and is_newer(latest, __version__)
            ),
            release_notes=user.last_known_release_notes,
            release_url=user.last_known_release_url,
            dismissed=dismissed,
            checked_at=user.last_update_check_at,
        )


def _no_update() -> UpdateRead:
    """The disabled check's answer: the version, nothing heard, nothing stored."""
    return UpdateRead(
        current_version=__version__,
        latest_version=None,
        update_available=False,
        release_notes=None,
        release_url=None,
        dismissed=False,
        checked_at=None,
    )
