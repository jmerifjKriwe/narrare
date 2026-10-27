"""The provider-profile service: the invariants, the gate, the two probes.

Everything the rows cannot say for themselves lives here (design D7 and the
settings surface): exactly one default per user with the flip in one
transaction, the delete guard that names the way out, the half-configuration
gate that refuses a profile which could never answer, and the masked-key
rules — the plaintext reaches exactly one response (the create's), the
column holds what :mod:`app.kernel.secrets` returned, the hint holds the
last four characters. The two probes run against the profile's own endpoint:
one cheap completion audited as ``settings.test``, and model discovery.

No side effect beyond the request's own transaction: each method commits
once, and the test probe's audit row rides the audit finalizer's own short
session the way every audited stream's does.
"""

from collections.abc import Sequence  # noqa: TC003
from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003  the service's parameter annotations name it

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.llm.audit import audited_stream
from app.kernel.llm.contract import CompletionRequest
from app.kernel.llm.models import ProviderProfile, TaskAssignment  # noqa: TC001
from app.kernel.llm.openai_chat import DEFAULT_BASE_URL, client_for, keyless_headers
from app.kernel.llm.profiles import AssignmentRepository, ProfileRepository
from app.kernel.llm.resolution import from_profile
from app.kernel.secrets import NoKeyStoreError, erase_key, save_key
from app.kernel.vendor import needs_api_key

if TYPE_CHECKING:
    from app.capabilities.settings.schemas import ProfileCreate, ProfileUpdate

PROBE_PROMPT = "Reply with a single word: ok."
"""The one cheap completion a connection test asks for."""

DISCOVERY_TIMEOUT = 30.0
"""Listing models is request/response: half a minute is generous."""


class ProfileNotFoundError(LookupError):
    """No profile of the user's carries the id."""


class ProfileRefusedError(ValueError):
    """The gate refuses this create or update; ``fields`` names the columns."""

    def __init__(self, fields: tuple[str, ...], message: str) -> None:
        super().__init__(message)
        self.fields = fields


class DefaultProfileError(RuntimeError):
    """The default profile cannot be deleted; the message names the way out."""


class NoEndpointError(RuntimeError):
    """The profile has no endpoint (a fake), so there is nothing to probe."""


@dataclass(frozen=True)
class TestResult:
    """What one connection test found: it ran, and it either answered or named why."""

    ok: bool
    error: str | None
    latency_ms: int


class ProfileService:
    """The profile invariants over the repositories; the commit is always here."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id

    def _profiles(self) -> ProfileRepository:
        return ProfileRepository(self.session, self.user_id)

    def _assignments(self) -> AssignmentRepository:
        return AssignmentRepository(self.session, self.user_id)

    async def list(self) -> Sequence[ProviderProfile]:
        """Every profile of the user's: the default first, then by name."""
        return await self._profiles().ordered()

    async def create(self, payload: ProfileCreate) -> tuple[ProviderProfile, str | None]:
        """Store one profile; the first of the user's becomes the default.

        Returns the row and the plaintext key exactly once — the one response
        that may carry it is the create's.
        """
        base_url = payload.base_url.rstrip("/") if payload.base_url else None
        self._gate(
            kind=payload.kind,
            base_url=base_url,
            model=payload.model,
            has_key=bool(payload.api_key),
            context_window=payload.context_window,
            max_output_tokens=payload.max_output_tokens,
        )
        profiles = self._profiles()
        # Before the flush: the first profile is what makes the new one the
        # default, and after the flush it would already be listed.
        is_default = not await profiles.ordered()
        profile = await profiles.create(
            name=payload.name,
            kind=payload.kind,
            base_url=base_url,
            model=payload.model,
            is_default=is_default,
            context_window=payload.context_window,
            max_output_tokens=payload.max_output_tokens,
            temperature=payload.temperature,
            request_timeout=payload.request_timeout,
        )
        column, hint = self._store_key(profile.id, payload.api_key or "")
        if hint is not None:
            await profiles.update(profile, api_key=column, api_key_hint=hint)
        await self.session.commit()
        return profile, payload.api_key or None

    async def update(self, profile_id: UUID, payload: ProfileUpdate) -> ProviderProfile:
        """Apply the patch; an absent or empty ``api_key`` keeps the stored one.

        ``is_default: true`` hands the default over from its holder in the
        same transaction; ``false`` is refused — "profiles exist with no
        default" is not a legal state.
        """
        profiles = self._profiles()
        profile = await profiles.get(profile_id)
        if profile is None:
            raise ProfileNotFoundError(f"no profile {profile_id}")
        set_fields = payload.model_fields_set
        if "name" in set_fields and payload.name is None:
            raise ProfileRefusedError(("name",), "a profile name cannot be cleared")

        base_url = (
            (payload.base_url.rstrip("/") if payload.base_url else None)
            if "base_url" in set_fields
            else profile.base_url
        )
        model = payload.model if "model" in set_fields else profile.model
        context_window = (
            payload.context_window if "context_window" in set_fields else profile.context_window
        )
        max_output_tokens = (
            payload.max_output_tokens
            if "max_output_tokens" in set_fields
            else profile.max_output_tokens
        )
        stored_a_key = bool(profile.api_key) or profile.api_key_hint is not None
        self._gate(
            kind=profile.kind,
            base_url=base_url,
            model=model,
            has_key=bool(payload.api_key) or stored_a_key,
            context_window=context_window,
            max_output_tokens=max_output_tokens,
        )
        if payload.is_default is False:
            raise ProfileRefusedError(
                ("is_default",),
                "a profile cannot stop being the default by patching;"
                " make another profile the default first",
            )

        updates: dict[str, object] = {}
        for field in (
            "name",
            "base_url",
            "model",
            "context_window",
            "max_output_tokens",
            "temperature",
            "request_timeout",
        ):
            if field in set_fields:
                updates[field] = getattr(payload, field)
        if payload.api_key:
            column, hint = self._store_key(profile.id, payload.api_key)
            updates["api_key"] = column
            updates["api_key_hint"] = hint
        if updates:
            await profiles.update(profile, **updates)
        if payload.is_default:
            await self._unset_other_defaults(profile)
            await profiles.update(profile, is_default=True)
        await self.session.commit()
        return profile

    async def delete(self, profile_id: UUID) -> None:
        """Remove a non-default profile; its assignments cascade at the database.

        The default profile is refused — including while it is the only one —
        with the error naming the way out (design D7).
        """
        profiles = self._profiles()
        profile = await profiles.get(profile_id)
        if profile is None:
            raise ProfileNotFoundError(f"no profile {profile_id}")
        if profile.is_default:
            raise DefaultProfileError(
                "the default profile cannot be deleted; create a second profile,"
                " make it the default, then delete this one"
            )
        try:
            erase_key(profile.id)
        except NoKeyStoreError:
            raise
        except Exception as failure:
            raise NoKeyStoreError(f"the key store failed while erasing: {failure}") from failure
        await profiles.delete(profile)
        await self.session.commit()

    async def set_default(self, profile_id: UUID) -> None:
        """Make this profile the default, unsetting the holder in one transaction."""
        profiles = self._profiles()
        profile = await profiles.get(profile_id)
        if profile is None:
            raise ProfileNotFoundError(f"no profile {profile_id}")
        await self._unset_other_defaults(profile)
        await profiles.update(profile, is_default=True)
        await self.session.commit()

    async def test(self, profile_id: UUID) -> TestResult:
        """One cheap completion against the profile's endpoint, audited as settings.test.

        The outcome is data, not a status: a dead endpoint, a refused key or a
        key its tier can no longer produce is a failed test that names why —
        one ``LlmCall`` row per provider call is the audit's identity, so the
        probe's call lands there however it ends.
        """
        profile = await self._profiles().get(profile_id)
        if profile is None:
            raise ProfileNotFoundError(f"no profile {profile_id}")
        started = monotonic()
        try:
            resolved = from_profile(profile)
            async for _ in audited_stream(
                resolved,
                CompletionRequest.user(PROBE_PROMPT),
                user_id=self.user_id,
                task_key="settings.test",
            ):
                pass
        except Exception as failure:
            return TestResult(
                ok=False, error=str(failure), latency_ms=round((monotonic() - started) * 1000)
            )
        return TestResult(ok=True, error=None, latency_ms=round((monotonic() - started) * 1000))

    async def discover(self, profile_id: UUID) -> list[str]:
        """The model ids the profile's endpoint offers, sorted.

        A fake profile has no endpoint to ask. Any transport or endpoint
        failure propagates for the router to name; a key its tier can no
        longer produce refuses by name before any request runs.
        """
        profile = await self._profiles().get(profile_id)
        if profile is None:
            raise ProfileNotFoundError(f"no profile {profile_id}")
        if profile.kind != "openai-chat":
            raise NoEndpointError("a fake profile has no endpoint to discover models on")
        resolved = from_profile(profile)
        endpoint, api_key = resolved.base_url or "", resolved.api_key or ""
        client = client_for(endpoint, api_key, timeout=DISCOVERY_TIMEOUT)
        try:
            page = await client.models.list(extra_headers=keyless_headers(api_key))
            ids = [model.id async for model in page]
            return sorted(ids)
        finally:
            await client.close()

    async def assignments(self) -> Sequence[TaskAssignment]:
        """Every assignment of the user's, ordered by task key."""
        return await self._assignments().list_all()

    async def assign(self, task_key: str, profile_id: UUID | None) -> TaskAssignment | None:
        """Point the task at one of the user's profiles, or clear it with ``None``.

        Any non-empty task key is accepted — the known keys are a kernel
        constant for readers, not a format; a new capability's key can be
        assigned before its list entry ships.
        """
        if not task_key:
            raise ProfileRefusedError(("task_key",), "a task key cannot be empty")
        assignments = self._assignments()
        if profile_id is None:
            await assignments.clear(task_key)
            await self.session.commit()
            return None
        profile = await self._profiles().get(profile_id)
        if profile is None:
            raise ProfileNotFoundError(f"no profile {profile_id}")
        assignment = await assignments.set(task_key, profile.id)
        await self.session.commit()
        return assignment

    def _gate(
        self,
        *,
        kind: str,
        base_url: str | None,
        model: str | None,
        has_key: bool,
        context_window: int | None,
        max_output_tokens: int | None,
    ) -> None:
        """Refuse a configuration that could never answer, naming the fields.

        ``openai-chat`` needs a ``model``, an ``api_key`` when the endpoint is
        remote (a local server may answer without one), an ``https://`` endpoint
        whenever the key would cross the network — a remote ``http://`` address
        would carry the bearer credential in cleartext — and an output
        reservation that leaves room for input (``max_output_tokens`` below
        ``context_window`` whenever both are known; the allocator still clamps
        for catalog-merged pairs). Broken config never reaches a model call
        (design, the settings surface).
        """
        if kind != "openai-chat":
            return
        fields: list[str] = []
        if not model:
            fields.append("model")
        endpoint = base_url or DEFAULT_BASE_URL
        if not has_key and needs_api_key(endpoint):
            fields.append("api_key")
        if needs_api_key(endpoint) and not endpoint.lower().startswith("https://"):
            fields.append("base_url")
        if (
            context_window is not None
            and max_output_tokens is not None
            and max_output_tokens >= context_window
        ):
            fields.append("max_output_tokens")
        if fields:
            raise ProfileRefusedError(
                tuple(fields),
                "a half-configured openai-chat profile is refused; "
                f"missing or unusable: {', '.join(fields)}",
            )

    def _store_key(self, profile_id: UUID, plaintext: str) -> tuple[str, str | None]:
        """Store the key in the best tier; return the column value and the hint.

        The raw exceptions a keyring backend can raise between its probe and
        its write are mapped into the closed vocabulary — the caller names a
        refusal, never a traceback.
        """
        if not plaintext:
            return "", None
        try:
            column = save_key(profile_id, plaintext)
        except NoKeyStoreError:
            raise
        except Exception as failure:
            raise NoKeyStoreError(f"the key store failed while saving: {failure}") from failure
        return column, plaintext[-4:]

    async def _unset_other_defaults(self, chosen: ProviderProfile) -> None:
        """Unset every other default, so the flip leaves exactly one holder."""
        profiles = self._profiles()
        for other in await profiles.ordered():
            if other.is_default and other.id != chosen.id:
                await profiles.update(other, is_default=False)
