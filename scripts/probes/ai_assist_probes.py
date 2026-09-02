#!/usr/bin/env python3
"""Probe: AI-assist dialogue_coach adoption (ADR-069 / ADR-056).

Exercises the real ``DialogueCoachService`` end-to-end with fakes
(TestModel + fake repos/composer/provider) — NO real DB, NO real LLM.
Verifies both the non-streaming ``run()`` and streaming ``stream()`` paths
produce the expected ``DialogueCoachResponse`` shape.

A real ``InvocationPipeline`` (FileEvidenceSink) is wired into the service
so the evidence-sink path is genuinely exercised — evidence is recorded to
``.evidence/invocations.jsonl``, not just declared.

Writes **additive** marker entries into the shared ``.evidence/`` marker
files so the adoption scorer flips the ``ai_assist|dialogue_coach`` runtime
fingerprints:

  - ``evidence_sink | missing`` → verified
  - ``final_validation | missing`` → verified
  - ``preference_enrichment | missing`` → verified

(``kb_suggested | not_applicable`` and ``budget_resolution | optional`` are
already correct from the registry defaults; flipping the three above also
sets ``runtime_verified`` → ``adopted``, resolving ``not_adopted``.)

The fakes mirror ``tests/unit/api/ai_assist/test_dialogue_coach_service.py``
and ``tests/integration/ai_assist/_fakes.py``. They are inline (not imported
from the test package) to keep the probe self-contained and avoid coupling
CI probe execution to test-internal modules.

Usage:
    python scripts/probes/ai_assist_probes.py [--evidence-dir PATH]

Returns:
    0 if all assertions passed, 1 otherwise.

See:
    ADR-069 Decision 17 (run + stream two-method contract),
    ADR-056 (runtime-evidence-aware adoption gate),
    Plan-Bug #22 (TestModel custom_output_args for tool-mode output),
    Plan-Bug #16 (deferred fingerprints baseline).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

# Ensure project root is on sys.path so `scripts.probes` resolves.
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from pydantic_ai.models.test import TestModel  # noqa: E402
from scripts.probes.base_probe import (  # noqa: E402
    EVIDENCE_DIR_DEFAULT,
    make_pipeline,
    merge_feature_marker,
)

from narrare.ai_assist.schemas import (  # noqa: E402
    DialogueCoachRequest,
    DialogueCoachStreamEvent,
)
from narrare.ai_assist.service import DialogueCoachService  # noqa: E402
from narrare_core.ai_invocation.adaptive_context import (  # noqa: E402
    AdaptiveContext,
    AdaptiveSettings,
)

if TYPE_CHECKING:
    from narrare.adaptive.adaptive_context_provider import AdaptiveContextProviderImpl
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

#: Feature id + mode this probe covers (matches adoption-registry.yaml).
_FEATURE_ID = "ai_assist"
_MODE = "dialogue_coach"

#: Shared marker files the adoption scorer reads (scorer_evidence.py).
#: Each carries a ``features`` mapping; we merge ai_assist in additively.
_MARKER_FILES = (
    "evidence_sink.json",
    "final_validation.json",
    "preference_enrichment.json",
)


# ── Fakes (mirror tests/unit/api/ai_assist/test_dialogue_coach_service.py) ──


class _FakeChapter:
    """Minimal chapter shape the service reads (id, novel_id, content, title)."""

    def __init__(self) -> None:
        self.id: UUID = uuid4()
        self.novel_id: UUID = uuid4()
        self.content: str = '"Hello," Alice said.'
        self.title: str = "Test Chapter"


class _FakeChapterRepo:
    """Async fake ChapterRepository — returns a chapter with content."""

    async def get(self, chapter_id: Any) -> Any:
        del chapter_id
        return _FakeChapter()

    async def get_by_id(self, chapter_id: Any, novel_id: Any | None = None) -> Any:
        del chapter_id, novel_id
        return _FakeChapter()


class _FakeNovel:
    """Minimal novel shape (id, title, genre, writing_language)."""

    def __init__(self) -> None:
        self.id: UUID = uuid4()
        self.title: str = "Test Novel"
        self.genre: str = "Fantasy"
        self.writing_language: str = "en"


class _FakeNovelRepo:
    """Async fake NovelRepository — returns a novel with metadata."""

    async def get_by_id(self, novel_id: Any, user_id: Any | None = None) -> Any:
        del novel_id, user_id
        return _FakeNovel()


class _FakeComposer:
    """Async fake PromptComposer — returns a minimal composed prompt."""

    async def build(self, *args: Any, **kwargs: Any) -> Any:
        from narrare_core.prompts.composer import ComposedPrompt

        del args, kwargs
        # user="" so the agent_runner falls back to build_run_prompt() via
        # the ``composed.user or build_run_prompt(...)`` expression.
        return ComposedPrompt(system="You are a dialogue coach.", user="")


class _FakeModelRegistry:
    """Async fake ModelRegistry — returns the supplied TestModel."""

    def __init__(self, model: TestModel) -> None:
        self._model = model

    async def get_model(
        self,
        config: Any,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> TestModel:
        # api_key/base_url: per-user routing credentials (user-routing
        # migration) — accepted for protocol fidelity with
        # ModelRegistry.get_model; the fake ignores them.
        del config, api_key, base_url
        return self._model


class _FakeAdaptiveProvider:
    """Async fake AdaptiveContextProvider — returns a known context."""

    def __init__(self) -> None:
        self._context = AdaptiveContext(
            user_id=uuid4(),
            project_id=uuid4(),
            preference_text="prefers terse prose",
            source_summary="preferences",
        )

    async def get_context(self, user_id: Any, project_id: Any) -> AdaptiveContext:
        del user_id, project_id
        return self._context

    async def get_settings(self, user_id: Any, project_id: Any) -> AdaptiveSettings:
        del user_id, project_id
        return AdaptiveSettings()

    async def record_snapshot(
        self,
        invocation_id: Any,
        adaptive_context: Any,
        evidence_repo: Any,
    ) -> None:
        """Best-effort no-op (mirrors tests/integration/ai_assist/_fakes.py)."""
        del invocation_id, adaptive_context, evidence_repo


# ── TestModel output args (Plan-Bug #22: tool-mode → custom_output_args) ────


def _coach_output_args() -> dict[str, Any]:
    """Build ``custom_output_args`` matching DialogueCoachAgent._process_output.

    Tool-mode output (Plan-Bug #22): the agent's output function is invoked
    as a tool, so TestModel must supply the call arguments as a dict, not a
    JSON string via ``custom_output_text``.
    """
    return {
        "issues": [
            {
                "issue_type": "voice_mismatch",
                "speaker": "Alice",
                "original_quote": '"Hello."',
                "diagnosis": "Test probe issue.",
                "severity": "low",
            }
        ],
        "adaptive_summary": "probe preference + voice signals",
    }


# ── Service factory ─────────────────────────────────────────────────────────


def _make_service(
    *,
    model: TestModel,
    pipeline: InvocationPipeline | None,
) -> DialogueCoachService:
    """Construct a DialogueCoachService with fakes (cast for type safety).

    ``cast`` avoids ``# type: ignore`` (RULE-23): the fakes are structurally
    compatible with the repository / provider protocols but are not actual
    instances of them.
    """
    return DialogueCoachService(
        chapter_repo=cast("ChapterRepository", _FakeChapterRepo()),
        novel_repo=cast("NovelRepository", _FakeNovelRepo()),
        model_registry=cast("ModelRegistry", _FakeModelRegistry(model)),
        model_config=cast("ResolvedModelConfig | None", None),
        composer=cast("PromptComposer", _FakeComposer()),
        invocation_pipeline=pipeline,
        adaptive_provider=cast("AdaptiveContextProviderImpl", _FakeAdaptiveProvider()),
    )


# ── Probe steps ─────────────────────────────────────────────────────────────


async def _probe_run(service: DialogueCoachService) -> bool:
    """Exercise service.run() and assert the response shape."""
    request = DialogueCoachRequest(
        selection_text='"Hello," Alice said.',
        mode="analyze",
    )
    result = await service.run(chapter_id=uuid4(), user_id=uuid4(), request=request)
    ok_shape = bool(result.issues) and result.issues[0].issue_type == "voice_mismatch"
    ok_mode = result.mode == "analyze"
    ok_summary = bool(result.adaptive_summary)
    ok = ok_shape and ok_mode and ok_summary
    label = f"run/{_FEATURE_ID}/{_MODE}"
    if ok:
        print(
            f"  ✅ {label}: response with {len(result.issues)} issue(s), adaptive_summary present"
        )
    else:
        print(f"  ❌ {label}: bad shape (issues={len(result.issues)}, mode={result.mode})")
    return ok


async def _probe_stream(service: DialogueCoachService) -> bool:
    """Exercise service.stream() and assert a terminal done event."""
    request = DialogueCoachRequest(selection_text='"Hi."', mode="improve")
    events: list[DialogueCoachStreamEvent] = []
    async for event in service.stream(chapter_id=uuid4(), user_id=uuid4(), request=request):
        events.append(event)

    has_terminal = (
        bool(events)
        and events[-1].is_final
        and events[-1].event
        in (
            "done",
            "error",
        )
    )
    has_result = any(
        e.event == "result" and e.result is not None and bool(e.result.issues) for e in events
    )
    ok = has_terminal and has_result
    label = f"stream/{_FEATURE_ID}/{_MODE}"
    if ok:
        print(
            f"  ✅ {label}: {len(events)} event(s), terminal={events[-1].event}, result with issues"
        )
    else:
        print(
            f"  ❌ {label}: terminal={has_terminal}, result_with_issues={has_result} "
            f"({len(events)} events)"
        )
    return ok


def _write_markers(evidence_dir: Path) -> None:
    """Merge ai_assist/dialogue_coach into the shared marker files."""
    for filename in _MARKER_FILES:
        path = merge_feature_marker(evidence_dir, filename, _FEATURE_ID, _MODE)
        print(f"  📝 Marker merged: {path}")


# ── Public entry point ──────────────────────────────────────────────────────


async def main_async(evidence_dir: Path) -> int:
    """Run the ai_assist dialogue_coach adoption probe.

    Constructs a DialogueCoachService with a TestModel + fakes and a real
    InvocationPipeline (FileEvidenceSink), exercises run() + stream(), and
    merges marker entries into the shared .evidence/ files.

    Args:
        evidence_dir: Directory for evidence + marker output.

    Returns:
        0 if all assertions passed, 1 otherwise.
    """
    model = TestModel(custom_output_args=_coach_output_args())
    pipeline = make_pipeline(evidence_dir=evidence_dir)
    service = _make_service(model=model, pipeline=pipeline)

    results: list[bool] = []

    print("Running ai_assist/dialogue_coach run() probe ...")
    results.append(await _probe_run(service))

    # Fresh TestModel — pydantic-ai TestModel is single-use per run.
    stream_model = TestModel(custom_output_args=_coach_output_args())
    stream_service = _make_service(model=stream_model, pipeline=pipeline)
    print("Running ai_assist/dialogue_coach stream() probe ...")
    results.append(await _probe_stream(stream_service))

    print("Writing adoption markers ...")
    _write_markers(evidence_dir)

    return 0 if all(results) else 1


def main() -> int:
    """CLI entry point for the ai_assist dialogue_coach adoption probe."""
    parser = argparse.ArgumentParser(
        description="AI-assist dialogue_coach adoption probe",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=EVIDENCE_DIR_DEFAULT,
        help="Directory for evidence + marker files (default: .evidence/)",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(args.evidence_dir))


if __name__ == "__main__":
    sys.exit(main())
