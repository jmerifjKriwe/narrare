"""Temporal consistency checking service (PLAN-004 Phase 2/3).

Orchestrates deterministic checks (core/analysis/temporal.py) and
optional LLM checks (TimelineAgent) to produce a combined consistency
report. Phase 3 delegates character age logic to CharacterAgeService.

Follows ADR-021: deterministic where possible, LLM where not.

Pattern: service → core/analysis (deterministic) + core/agents (LLM).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.planning._prompt_loader import load_temporal_consistency_prompt
from narrare.planning._timeline_event_utils import events_to_dicts
from narrare.planning.timeline_schemas import (
    CharacterAgeReport,
    TemporalConsistencyResponse,
    TemporalIssueResponse,
)
from narrare_core.ai_invocation import ManualInjectionDeclaration
from narrare_core.analysis.temporal import run_deterministic_checks
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.novels.repository import NovelRepository
    from narrare.planning.character_age_service import CharacterAgeService
    from narrare.planning.models import TimelineEvent
    from narrare.planning.timeline_repository import TimelineEventRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry

logger = structlog.get_logger(__name__)

# ADR-048 Mode 2 declaration: TimelineAgent composes its consistency-check
# prompt internally from TimelineDeps and the bundled temporal prompt.
_TEMPORAL_CONSISTENCY_INJECTION = ManualInjectionDeclaration(
    reason=(
        "TimelineAgent composes its consistency-check prompt internally from "
        "TimelineDeps (genre, language) and the bundled temporal prompt."
    ),
    variables=("genre", "language"),
    injection_mechanism="agent_deps",
)


class TimelineConsistencyService:
    """Service for temporal consistency checking.

    Runs deterministic checks (ordering, duplicates, duration, character
    ages) from ``core/analysis/temporal.py`` and optionally LLM-based
    checks via the TimelineAgent for contextual validation.

    Args:
        event_repo: Persistence layer for timeline events.
        novel_repo: For novel metadata and ownership verification.
        character_age_service: For character birth date data.
        model_registry: Shared LLM model registry (optional — LLM
            checks are skipped when not configured).
        model_config: Resolved model config for LLM checks.
    """

    def __init__(
        self,
        event_repo: TimelineEventRepository,
        novel_repo: NovelRepository,
        character_age_service: CharacterAgeService | None = None,
        model_registry: ModelRegistry | None = None,
        model_config: ResolvedModelConfig | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._event_repo = event_repo
        self._novel_repo = novel_repo
        self._character_age_service = character_age_service
        self._registry = model_registry
        self._config = model_config
        self._invocation_pipeline = invocation_pipeline

    async def check_consistency(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> TemporalConsistencyResponse:
        """Run all consistency checks (deterministic + optional LLM).

        1. Load all events for the novel from DB
        2. Convert to dicts for core/analysis/temporal.py
        3. Load character birth dates via CharacterAgeService
        4. Run deterministic checks (run_deterministic_checks)
        5. Optionally run LLM checks via TimelineAgent
        6. Merge results and return

        Args:
            novel_id: UUID of the novel.
            user_id: UUID of the requesting user.

        Returns:
            Combined consistency report with all issues found.

        Raises:
            NotFoundError: If the novel does not exist.
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        # Step 1: Load all events for the novel
        events = await self._event_repo.list_by_novel(novel_id)

        # Step 2: Convert to dicts for deterministic checks
        event_dicts = events_to_dicts(events)

        # Step 3: Load character birth dates from KB
        character_ages = await self._load_character_ages(novel_id)

        # Step 4: Run deterministic checks
        deterministic_result = run_deterministic_checks(event_dicts, character_ages=character_ages)

        # Convert core TemporalIssue objects to API TemporalIssueResponse
        issues: list[TemporalIssueResponse] = [
            TemporalIssueResponse(
                severity=issue.severity.value
                if hasattr(issue.severity, "value")
                else str(issue.severity),
                rule_id=issue.rule_id,
                event_ids=issue.event_ids,
                description=issue.description,
                suggestion=issue.suggestion,
                source=issue.source,
            )
            for issue in deterministic_result.issues
        ]

        # Step 5: Optionally run LLM checks
        llm_issues = await self._run_llm_checks(novel_id, events, novel)
        issues.extend(llm_issues)

        # Step 6: Build response
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]

        assessment = "No temporal issues detected."
        if errors:
            assessment = f"{len(errors)} error(s) and {len(warnings)} warning(s) found."
        elif warnings:
            assessment = f"{len(warnings)} warning(s) found. No critical errors."

        return TemporalConsistencyResponse(
            issues=issues,
            deterministic_pass=deterministic_result.deterministic_pass,
            overall_assessment=assessment,
        )

    async def get_character_ages(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CharacterAgeReport:
        """Delegate character age reporting to CharacterAgeService.

        Args:
            novel_id: UUID of the novel.
            user_id: UUID of the requesting user.

        Returns:
            Character age report.

        Raises:
            NotFoundError: If the novel does not exist.
        """
        if self._character_age_service is None:
            raise NotFoundError("CharacterAgeService", identifier="not_configured")
        return await self._character_age_service.get_character_ages(novel_id, user_id)

    async def _load_character_ages(self, novel_id: uuid.UUID) -> dict[str, str | None] | None:
        """Load character birth dates via CharacterAgeService.

        Returns None when CharacterAgeService is not available.
        """
        if self._character_age_service is None:
            return None
        try:
            return await self._character_age_service.load_birth_date_map(novel_id)
        except Exception:
            logger.warning("failed_to_load_character_ages", exc_info=True)
            return None

    async def _run_llm_checks(
        self,
        novel_id: uuid.UUID,
        events: list[TimelineEvent],
        novel: object,
    ) -> list[TemporalIssueResponse]:
        """Run LLM-based consistency checks via TimelineAgent.

        Loads the system prompt from the bundled prompt registry (RULE-02)
        in the novel's writing language. Falls back to English when the
        language-specific prompt is not available.

        Returns an empty list when LLM is not configured or when no
        events exist to check. LLM checks are supplementary — they
        find contextual issues that deterministic rules cannot detect.
        """
        if self._config is None or self._registry is None:
            logger.debug("llm_checks_skipped_no_provider", novel_id=str(novel_id))
            return []

        if not events:
            return []

        try:
            from narrare_core.agents.timeline_agent import TimelineAgent, TimelineDeps

            model = await self._registry.get_model(self._config)

            # Build a compact event context for the LLM (user prompt — data-driven)
            event_context = "\n".join(
                f"- {e.event_name} (order: {e.temporal_order}, timestamp: {e.timestamp_raw})"
                for e in events[:50]  # Limit context size
            )

            novel_title = getattr(novel, "title", "Unknown")
            genre = getattr(novel, "genre", "") or ""
            language = getattr(novel, "writing_language", "") or "en"

            # Load bundled prompt via importlib.resources (RULE-02 compliance)
            system_prompt_text = load_temporal_consistency_prompt(
                language=language,
                novel_title=novel_title,
                genre=genre,
                language_code=language,
            )

            deps = TimelineDeps(
                genre=genre,
                language=language,
            )

            agent = TimelineAgent(model=model)
            from narrare._app.invocation_context import safe_compose_invocation
            from narrare_core.llm.intents import LLMIntent

            await safe_compose_invocation(
                self._invocation_pipeline,
                feature_id="planning_timeline_consistency",
                intent=LLMIntent.PLAN,
                project_id=novel_id,
                manual_injection=_TEMPORAL_CONSISTENCY_INJECTION,
            )
            result = await agent.run(
                prompt=event_context,
                system_prompt=system_prompt_text,
                deps=deps,
            )

            # Convert LLM-identified conflicts to TemporalIssueResponse
            llm_issues: list[TemporalIssueResponse] = []
            for conflict in getattr(result, "temporal_conflicts", []):
                if isinstance(conflict, str):
                    llm_issues.append(
                        TemporalIssueResponse(
                            severity="warning",
                            rule_id="llm_temporal_conflict",
                            event_ids=[],
                            description=conflict,
                            suggestion="Review this temporal conflict manually.",
                            source="llm",
                        )
                    )
            return llm_issues

        except Exception:
            logger.warning("llm_consistency_checks_failed", exc_info=True)
            # LLM checks are supplementary — don't fail the whole request
            return []
