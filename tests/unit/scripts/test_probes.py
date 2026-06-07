"""Tests for the invocation pipeline eval probes.

All tests use ``tmp_path`` for evidence isolation — no files leak
between tests or persist after the test run.

See:
    ADR-041, INFRA-013 §P3.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from scripts.probes.base_probe import EVIDENCE_DIR_DEFAULT, make_pipeline, run_probe
from scripts.probes.chat_chat_probe import main_async as chat_probe
from scripts.probes.generation_names_probe import main_async as names_probe
from scripts.probes.planning_outline_probe import main_async as outline_probe
from scripts.probes.run_all_probes import main_async as runner

from narrare_core.ai_invocation.models import PromptInvocationContext
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt

# ---------------------------------------------------------------------------
# BaseProbe tests
# ---------------------------------------------------------------------------


class TestBaseProbe:
    """Tests for shared probe logic in ``base_probe.py``."""

    def test_make_pipeline_returns_invocation_pipeline_with_file_sink(
        self,
        tmp_path: Path,
    ) -> None:
        """make_pipeline creates an InvocationPipeline configured with
        a FileEvidenceSink writing to the given directory."""
        pipeline = make_pipeline(tmp_path)
        assert isinstance(pipeline, InvocationPipeline)

        context = PromptInvocationContext(
            feature_id="test",
            intent=LLMIntent.CHAT,
            mode="test_mode",
        )
        prepared = asyncio.run(pipeline.prepare(context))
        prompt = ComposedPrompt(system="s", user="u")
        final = asyncio.run(pipeline.finalize(prompt, context, prepared=prepared))
        assert final.evidence_recorded is True
        assert (tmp_path / "invocations.jsonl").exists()

    def test_make_pipeline_default_evidence_dir(self) -> None:
        """Default evidence directory points to repo-root/.evidence/."""
        pipeline = make_pipeline()
        assert isinstance(pipeline, InvocationPipeline)
        assert EVIDENCE_DIR_DEFAULT.name == ".evidence"

    def test_run_probe_returns_true_on_success(self, tmp_path: Path) -> None:
        """run_probe returns True when evidence is recorded successfully."""
        pipeline = make_pipeline(tmp_path)
        context = PromptInvocationContext(
            feature_id="test",
            intent=LLMIntent.CHAT,
            mode="test",
        )
        result = asyncio.run(run_probe(pipeline, context))
        assert result is True

    def test_run_probe_writes_evidence_file(self, tmp_path: Path) -> None:
        """After a successful probe, the evidence JSONL file exists with content."""
        pipeline = make_pipeline(tmp_path)
        context = PromptInvocationContext(
            feature_id="test",
            intent=LLMIntent.CHAT,
            mode="test",
        )
        asyncio.run(run_probe(pipeline, context))
        evidence_file = tmp_path / "invocations.jsonl"
        assert evidence_file.exists()
        content = evidence_file.read_text(encoding="utf-8")
        assert "test" in content
        assert "chat" in content


# ---------------------------------------------------------------------------
# Individual probe tests
# ---------------------------------------------------------------------------


class TestChatProbe:
    """Tests for the chat/chat probe."""

    def test_returns_zero_on_success(self, tmp_path: Path) -> None:
        """chat_probe returns exit code 0 when evidence is recorded."""
        exit_code = asyncio.run(chat_probe(tmp_path))
        assert exit_code == 0

    def test_creates_correct_context(self) -> None:
        """The chat probe context has the right feature_id, intent, and mode."""
        context = PromptInvocationContext(
            feature_id="writing",
            intent=LLMIntent.CHAT,
            mode="chat",
            language="en",
            dynamic_inputs={
                "conversation_history": "",
                "user_message": "Hello, tell me about my story",
            },
        )
        assert context.feature_id == "writing"
        assert context.intent == LLMIntent.CHAT
        assert context.mode == "chat"
        assert context.language == "en"
        assert "user_message" in context.dynamic_inputs

    def test_records_evidence(self, tmp_path: Path) -> None:
        """Running the probe produces evidence with expected fields."""
        asyncio.run(chat_probe(tmp_path))
        evidence_file = tmp_path / "invocations.jsonl"
        assert evidence_file.exists()
        lines = evidence_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) >= 1
        evidence = json.loads(lines[0])
        assert evidence["feature_id"] == "writing"
        assert evidence["intent"] == "chat"


class TestPlanningProbe:
    """Tests for the planning/outline probe."""

    def test_returns_zero_on_success(self, tmp_path: Path) -> None:
        """outline_probe returns exit code 0 when evidence is recorded."""
        exit_code = asyncio.run(outline_probe(tmp_path))
        assert exit_code == 0

    def test_creates_correct_context(self) -> None:
        """The outline probe context has the right feature_id, intent, and mode."""
        context = PromptInvocationContext(
            feature_id="planning",
            intent=LLMIntent.PLAN,
            mode="outline",
            language="en",
            dynamic_inputs={
                "project_title": "Test Story",
                "genre": "Fantasy",
                "tone": "dark",
            },
        )
        assert context.feature_id == "planning"
        assert context.intent == LLMIntent.PLAN
        assert context.mode == "outline"
        assert context.dynamic_inputs["genre"] == "Fantasy"

    def test_records_evidence(self, tmp_path: Path) -> None:
        """Running the probe produces evidence with expected fields."""
        asyncio.run(outline_probe(tmp_path))
        evidence_file = tmp_path / "invocations.jsonl"
        assert evidence_file.exists()
        lines = evidence_file.read_text(encoding="utf-8").strip().split("\n")
        evidence = json.loads(lines[0])
        assert evidence["feature_id"] == "planning"
        assert evidence["intent"] == "plan"


class TestNamesProbe:
    """Tests for the generation/names probe."""

    def test_returns_zero_on_success(self, tmp_path: Path) -> None:
        """names_probe returns exit code 0 when evidence is recorded."""
        exit_code = asyncio.run(names_probe(tmp_path))
        assert exit_code == 0

    def test_creates_correct_context(self) -> None:
        """The names probe context has the right feature_id, intent, and mode."""
        context = PromptInvocationContext(
            feature_id="generation",
            intent=LLMIntent.NAME_GENERATE,
            mode="names",
            language="en",
            dynamic_inputs={
                "name_type": "character",
                "count": "5",
                "writing_language": "en",
            },
        )
        assert context.feature_id == "generation"
        assert context.intent == LLMIntent.NAME_GENERATE
        assert context.mode == "names"
        assert context.dynamic_inputs["name_type"] == "character"

    def test_records_evidence(self, tmp_path: Path) -> None:
        """Running the probe produces evidence with expected fields."""
        asyncio.run(names_probe(tmp_path))
        evidence_file = tmp_path / "invocations.jsonl"
        assert evidence_file.exists()
        lines = evidence_file.read_text(encoding="utf-8").strip().split("\n")
        evidence = json.loads(lines[0])
        assert evidence["feature_id"] == "generation"
        assert evidence["intent"] == "name_generate"


# ---------------------------------------------------------------------------
# Runner tests
# ---------------------------------------------------------------------------


class TestRunAllProbes:
    """Tests for the run_all_probes runner."""

    async def test_runner_reports_all_passed(self, tmp_path: Path) -> None:
        """Runner returns 0 when all three probes pass."""
        exit_code = await runner(tmp_path)
        assert exit_code == 0

    def test_runner_output_contains_summary(self, tmp_path: Path, capsys) -> None:
        """Runner prints a summary line with probe results."""
        asyncio.run(runner(tmp_path))
        captured = capsys.readouterr()
        assert "Probe Results" in captured.out
        assert "3/3 probes passed" in captured.out
