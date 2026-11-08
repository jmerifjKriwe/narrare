"""The provider service: the saved endpoints their models hang off.

The row is the endpoint facts — base URL, models URL, vendor, key — that a
profile names instead of repeating them. Everything the rows cannot say for
themselves lives here: the half-configuration gate that refuses a provider
which could never answer, the masked-key rules — the plaintext reaches
exactly one response (the create's), the column holds what
:mod:`app.kernel.secrets` returned, the hint holds the last four characters —
and the delete guard that names the models still pointed at the provider
instead of a count. Discovery runs the SDK's model list against the
provider's own endpoint.

No side effect beyond the request's own transaction: each method commits once.
"""

from collections.abc import Sequence  # noqa: TC003
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003  the service's parameter annotations name it

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.settings.profiles_service import NoEndpointError
from app.kernel.llm.models import LLMProvider  # noqa: TC001
from app.kernel.llm.openai_chat import client_for, keyless_headers
from app.kernel.llm.repositories import ProfileRepository, ProviderRepository
from app.kernel.secrets import NoKeyStoreError, erase_key, load_key, save_key
from app.kernel.vendor import needs_api_key

if TYPE_CHECKING:
    from app.capabilities.settings.schemas import ProviderCreate, ProviderUpdate

DISCOVERY_TIMEOUT = 30.0
"""Listing models is request/response: half a minute is generous."""


class ProviderNotFoundError(LookupError):
    """No provider of the user's carries the id."""


class ProviderRefusedError(ValueError):
    """The gate refuses this create or update; ``fields`` names the columns."""

    def __init__(self, fields: tuple[str, ...], message: str) -> None:
        super().__init__(message)
        self.fields = fields


class ProviderHasModelsError(RuntimeError):
    """The provider still has models pointed at it; the message names them."""


class ProviderService:
    """The provider invariants over the repositories; the commit is always here."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id

    def _providers(self) -> ProviderRepository:
        return ProviderRepository(self.session, self.user_id)

    def _profiles(self) -> ProfileRepository:
        return ProfileRepository(self.session, self.user_id)

    async def list(self) -> Sequence[LLMProvider]:
        """Every provider of the user's, by name."""
        return await self._providers().ordered()

    async def create(self, payload: ProviderCreate) -> tuple[LLMProvider, str | None]:
        """Store one provider endpoint.

        Returns the row and the plaintext key exactly once — the one response
        that may carry it is the create's.

        The keyring write precedes the commit: ``_store_key`` runs on the
        flushed row, so a key tier that fails there aborts before anything a
        reader could see is committed. The reverse order would let a visible
        row point at a key that was never written. The cost of this order is
        the orphaned secret: a commit that fails after the write leaves a
        stored key no row names, until the next save for that provider id
        overwrites it. The profile create documents the same ordering (F-10).
        """
        base_url = payload.base_url.rstrip("/") if payload.base_url else None
        self._gate(kind=payload.kind, base_url=base_url, has_key=bool(payload.api_key))
        providers = self._providers()
        provider = await providers.create(
            name=payload.name,
            kind=payload.kind,
            base_url=base_url,
            models_url=payload.models_url,
            vendor=payload.vendor,
        )
        column, hint = self._store_key(provider.id, payload.api_key or "")
        if hint is not None:
            await providers.update(provider, api_key=column, api_key_hint=hint)
        await self.session.commit()
        return provider, payload.api_key or None

    async def update(self, provider_id: UUID, payload: ProviderUpdate) -> LLMProvider:
        """Apply the patch; an absent or empty ``api_key`` keeps the stored one.

        The kind is what the provider is, so it is not editable; the gate runs
        on the patched endpoint with the stored key taken into account, the
        way the profile patch does — redirecting a stored credential to a
        cleartext endpoint is refused here too. The stored ``base_url`` is
        the normalized form the gate computed, not the payload's raw
        spelling: the create strips, and so must the update, or a
        trailing-slash patch would store an endpoint the keys and the
        locality tier read differently than the gate vetted.
        """
        providers = self._providers()
        provider = await providers.get(provider_id)
        if provider is None:
            raise ProviderNotFoundError(f"no provider {provider_id}")
        set_fields = payload.model_fields_set
        if "name" in set_fields and payload.name is None:
            raise ProviderRefusedError(("name",), "a provider name cannot be cleared")

        base_url = (
            (payload.base_url.rstrip("/") if payload.base_url else None)
            if "base_url" in set_fields
            else provider.base_url
        )
        stored_a_key = bool(provider.api_key) or provider.api_key_hint is not None
        self._gate(
            kind=provider.kind,
            base_url=base_url,
            has_key=bool(payload.api_key) or stored_a_key,
        )
        updates: dict[str, object] = {}
        for field in ("name", "models_url", "vendor"):
            if field in set_fields:
                updates[field] = getattr(payload, field)
        if "base_url" in set_fields:
            # The normalized spelling, never the payload's raw one.
            updates["base_url"] = base_url
        if payload.api_key:
            column, hint = self._store_key(provider.id, payload.api_key)
            updates["api_key"] = column
            updates["api_key_hint"] = hint
        if updates:
            await providers.update(provider, **updates)
        await self.session.commit()
        return provider

    async def delete(self, provider_id: UUID) -> None:
        """Remove a provider no model points at; its key goes with it.

        The guard refuses while a profile of the user's still points here,
        naming the models — the way out, not a count. The database would
        cascade such profiles away silently, which is exactly what the guard
        exists to prevent.
        """
        providers = self._providers()
        provider = await providers.get(provider_id)
        if provider is None:
            raise ProviderNotFoundError(f"no provider {provider_id}")
        profiles = self._profiles()
        if await profiles.count_for_provider(provider.id):
            names = ", ".join(await profiles.models_for_provider(provider.id))
            raise ProviderHasModelsError(
                "the provider still has models pointed at it"
                f" ({names}); point them at another provider or delete them first"
            )
        try:
            erase_key(provider.id)
        except NoKeyStoreError:
            raise
        except Exception as failure:
            raise NoKeyStoreError(f"the key store failed while erasing: {failure}") from failure
        await providers.delete(provider)
        await self.session.commit()

    async def discover(self, provider_id: UUID) -> list[str]:
        """The model ids the provider's endpoint offers, sorted.

        A fake provider has no endpoint to ask. Any transport or endpoint
        failure propagates for the router to name; a key its tier can no
        longer produce refuses by name before any request runs.
        """
        provider = await self._providers().get(provider_id)
        if provider is None:
            raise ProviderNotFoundError(f"no provider {provider_id}")
        if provider.kind != "openai-chat":
            raise NoEndpointError("a fake provider has no endpoint to discover models on")
        endpoint = provider.base_url
        if not endpoint:
            raise NoEndpointError("the provider has no endpoint to discover models on")
        api_key = (
            load_key(provider.id, provider.api_key)
            if provider.api_key or provider.api_key_hint is not None or needs_api_key(endpoint)
            else ""
        )
        client = client_for(endpoint, api_key, timeout=DISCOVERY_TIMEOUT)
        try:
            page = await client.models.list(extra_headers=keyless_headers(api_key))
            ids = [model.id async for model in page]
            return sorted(ids)
        finally:
            await client.close()

    def _gate(self, *, kind: str, base_url: str | None, has_key: bool) -> None:
        """Refuse a configuration that could never answer, naming the fields.

        An ``openai-chat`` provider is the remote kind: it needs a ``base_url``
        — the row *is* the endpoint, there is no vendor default to fall back
        to — an ``api_key`` when the endpoint is remote (a local server may
        answer without one), and an ``https://`` endpoint whenever the key
        would cross the network — a remote ``http://`` address would carry the
        bearer credential in cleartext. A fake has no endpoint and needs
        nothing. Broken config never reaches a model call.
        """
        if kind != "openai-chat":
            return
        fields: list[str] = []
        if not base_url:
            fields.append("base_url")
        elif needs_api_key(base_url):
            if not has_key:
                fields.append("api_key")
            if not base_url.lower().startswith("https://"):
                fields.append("base_url")
        if fields:
            raise ProviderRefusedError(
                tuple(fields),
                "a half-configured openai-chat provider is refused; "
                f"missing or unusable: {', '.join(fields)}",
            )

    def _store_key(self, provider_id: UUID, plaintext: str) -> tuple[str, str | None]:
        """Store the key in the best tier; return the column value and the hint.

        The raw exceptions a keyring backend can raise between its probe and
        its write are mapped into the closed vocabulary — the caller names a
        refusal, never a traceback.
        """
        if not plaintext:
            return "", None
        try:
            column = save_key(provider_id, plaintext)
        except NoKeyStoreError:
            raise
        except Exception as failure:
            raise NoKeyStoreError(f"the key store failed while saving: {failure}") from failure
        return column, plaintext[-4:]
