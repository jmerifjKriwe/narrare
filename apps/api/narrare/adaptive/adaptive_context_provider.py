"""Backend AdaptiveContextProvider implementation.

Composes the existing ``PreferenceProvider`` (mem0-backed, ADR-033)
and ``ProfileProvider`` (Core Protocol from ``ai_invocation.contracts``)
into a single ``AdaptiveContext`` bundle for the Core
``AdaptiveContextEnricher``.

Mirrors the ADR-067 ``KBContextProvider`` pattern: Core Protocol +
Backend composer impl.

Phase 2 scaffold (ADR-069 Retrofit-Plan step 6):
- Loads ``PreferenceProfile`` via ``PreferenceProvider.get_preferences``.
- Loads ``ProjectWritingProfile`` via ``ProfileProvider.get_profile``.
- Derives ``style_constraints_text`` from ``PreferenceProfile.style`` dict
  (heuristic bullet list — tunable in Phase 3 via Eval).
- Derives ``avoidance_patterns_text`` from ``PreferenceProfile.constraints``
  list (heuristic bullet list — tunable in Phase 3 via Eval).
- Returns default ``AdaptiveSettings()`` (no persistence; Phase 3 reads
  from ``ProjectSettings.adaptive_settings`` JSONB).
- Does NOT write ``invocation_evidence.adaptive_*`` columns (Phase 3).

ADR-055/057 boundary: this impl copies ONLY the descriptive
``formatted_voice_profiles`` text into ``AdaptiveContext.voice_profiles_text``.
The numeric ``voice_metrics`` are never read, copied, or returned.

See:
    ADR-069 Decision 3 (Provider Pattern),
    ADR-067 (KBContextProvider precedent),
    ADR-033 (mem0 boundary via PreferenceProvider),
    ADR-055/057 (voice_metrics boundary),
    CONSTRAINTS.md RULE-07 / RULE-08 / RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.adaptive.repository import AdaptiveSettingsRepository
    from narrare_core.ai_invocation.adaptive_context import (
        AdaptiveContext,
        AdaptiveSettings,
    )
    from narrare_core.ai_invocation.contracts import ProfileProvider
    from narrare_core.memory.models import PreferenceProfile
    from narrare_core.memory.protocols import PreferenceProvider

logger = structlog.get_logger(__name__)


class AdaptiveContextProviderImpl:
    """Composes PreferenceProvider + ProfileProvider into AdaptiveContext.

    Args:
        preference_provider: mem0-backed provider (``None`` for graceful
            no-op — e.g., mem0 not installed).
        profile_provider: Core ``ProfileProvider`` for the
            ``ProjectWritingProfile`` (``None`` when not yet wired —
            Phase 4 will add the production Backend impl).
        settings_repo: AdaptiveSettingsRepository for loading persisted
            adaptive settings (Phase 3). ``None`` for Phase 2 callers /
            unit tests — defaults are returned.
    """

    def __init__(
        self,
        preference_provider: PreferenceProvider | None,
        profile_provider: ProfileProvider | None,
        settings_repo: AdaptiveSettingsRepository | None = None,
    ) -> None:
        self._preference_provider = preference_provider
        self._profile_provider = profile_provider
        self._settings_repo = settings_repo

    async def get_context(self, user_id: object, project_id: object) -> AdaptiveContext:
        """Assemble AdaptiveContext from preferences + writing profile.

        Graceful degradation: when a provider is None or raises, the
        corresponding text fields are empty. The method never raises
        for missing data — only for programmer errors.
        """
        # Late import to keep Core contracts under TYPE_CHECKING.
        from narrare_core.ai_invocation.adaptive_context import AdaptiveContext

        preference_text = ""
        style_constraints_text = ""
        avoidance_patterns_text = ""

        if self._preference_provider is not None:
            try:
                pref = await self._preference_provider.get_preferences(
                    user_id=user_id,
                    project_id=project_id,
                )
                preference_text = pref.to_prompt_text()
                style_constraints_text = _derive_style_constraints(pref)
                avoidance_patterns_text = _derive_avoidance_patterns(pref)
            except Exception:
                logger.warning(
                    "adaptive_provider_preference_failed",
                    user_id=str(user_id),
                    project_id=str(project_id),
                    exc_info=True,
                )

        voice_profiles_text = ""
        if self._profile_provider is not None:
            try:
                writing = await self._profile_provider.get_profile(project_id)
                if writing is not None:
                    # ADR-055/057 boundary: formatted_voice_profiles renders
                    # ONLY the descriptive speech_summary — never voice_metrics.
                    voice_profiles_text = writing.formatted_voice_profiles
            except Exception:
                logger.warning(
                    "adaptive_provider_profile_failed",
                    user_id=str(user_id),
                    project_id=str(project_id),
                    exc_info=True,
                )

        source_parts: list[str] = []
        if preference_text:
            source_parts.append("preferences")
        if voice_profiles_text:
            source_parts.append("voice profiles")
        source_summary = ", ".join(source_parts) if source_parts else "no signals"

        # Protocol accepts `object` for caller flexibility (matches
        # PromptInvocationContext.user_id: object | None + PreferenceProvider
        # precedent), but AdaptiveContext dataclass semantically types these
        # as UUID. Cast bridges the design tension without runtime cost.
        return AdaptiveContext(
            user_id=cast("UUID", user_id),
            project_id=cast("UUID", project_id),
            preference_text=preference_text,
            voice_profiles_text=voice_profiles_text,
            style_constraints_text=style_constraints_text,
            avoidance_patterns_text=avoidance_patterns_text,
            source_summary=source_summary,
        )

    async def get_settings(self, user_id: object, project_id: object) -> AdaptiveSettings:
        """Load AdaptiveSettings from DB (Phase 3) or return defaults.

        Phase 3: when a ``settings_repo`` is wired, load from
        ``ProjectSettings.adaptive_settings`` JSONB. When the repo is
        ``None`` (tests, Phase 2 callers) or no row exists, fall back to
        ``AdaptiveSettings()`` defaults (Phase 2 contract preserved).
        """
        from narrare_core.ai_invocation.adaptive_context import AdaptiveSettings

        if self._settings_repo is None:
            return AdaptiveSettings()
        try:
            loaded = await self._settings_repo.load(project_id)  # type: ignore[arg-type]
        except Exception:
            logger.warning(
                "adaptive_provider_settings_load_failed",
                user_id=str(user_id),
                project_id=str(project_id),
                exc_info=True,
            )
            return AdaptiveSettings()
        return loaded or AdaptiveSettings()

    async def record_snapshot(
        self,
        invocation_id: object,
        adaptive_context: AdaptiveContext,
        evidence_repo: object,
    ) -> None:
        """Write adaptive_source_summary + adaptive_weights to invocation_evidence.

        Called by an adaptive-consuming service (e.g. DialogueCoachService
        in Phase 4) after the invocation completes. The evidence row must
        already exist (correlated via ``invocation_id``); this method
        updates the two adaptive columns.

        Args:
            invocation_id: The invocation_id from compose_invocation().
            adaptive_context: The AdaptiveContext that shaped the invocation.
            evidence_repo: EvidenceRepositoryImpl (passed by the caller to
                avoid coupling the provider to a specific session).
        """
        if adaptive_context.source_summary == "" and not adaptive_context.has_any_signal:
            return  # nothing to record
        source_summary_dict: dict[str, str] = {
            "summary": adaptive_context.source_summary,
        }
        weights_dict: dict[str, float] = {
            "preference": adaptive_context.weights.preference,
            "voice_fidelity": adaptive_context.weights.voice_fidelity,
            "style_constraints": adaptive_context.weights.style_constraints,
            "avoidance": adaptive_context.weights.avoidance,
        }
        from narrare.evidence.repository import EvidenceRepositoryImpl

        if not isinstance(evidence_repo, EvidenceRepositoryImpl):
            logger.warning(
                "adaptive_provider_record_snapshot_bad_repo",
                repo_type=type(evidence_repo).__name__,
            )
            return
        try:
            await evidence_repo.update_adaptive_snapshot(
                invocation_id=invocation_id,  # type: ignore[arg-type]
                source_summary=source_summary_dict,
                weights=weights_dict,
            )
        except Exception:
            logger.warning(
                "adaptive_provider_record_snapshot_failed",
                invocation_id=str(invocation_id),
                exc_info=True,
            )


# ---------------------------------------------------------------------------
# Heuristic derivation helpers (Phase 2 — tunable in Phase 3 via Eval)
# ---------------------------------------------------------------------------


def _derive_style_constraints(pref: PreferenceProfile) -> str:
    """Derive style_constraints text from PreferenceProfile.style dict.

    Phase 2 heuristic: each entry becomes a bullet ``- {key}: {value}``.
    The exact format is tunable in Phase 3 via the Pydantic Eval suite
    (RULE-18b); the contract here is: non-empty iff the style dict has
    at least one entry.
    """
    if not pref.style:
        return ""
    return "\n".join(f"- {k}: {v}" for k, v in pref.style.items())


def _derive_avoidance_patterns(pref: PreferenceProfile) -> str:
    """Derive avoidance_patterns text from PreferenceProfile.constraints list.

    Phase 2 heuristic: each entry becomes a bullet ``- {entry}``.
    Tunable in Phase 3 via Eval.
    """
    if not pref.constraints:
        return ""
    return "\n".join(f"- {entry}" for entry in pref.constraints)
