"""Scripted capability records, the tiny real corpus, and the Wiring assembly.

The DATA half of the runner test fixtures (plan Task 15): real driver/
scorer record types with scripted values, the on-disk test corpus
(exercising ``load_corpus`` through the true loader), and the ``Wiring``
bundle that assembles ``RunnerDeps`` + ``RunRequest`` from the fakes in
``runner_helpers``. Split from ``runner_helpers.py`` per RULE-04.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from benchmark.corpus_loader import load_corpus
from benchmark.drivers.base import CapabilityResult
from benchmark.drivers.check_records import FlaggedLine, VoiceCheckFinding, VoiceCheckRecord
from benchmark.drivers.out_records import EntryBrowseRecord, TimelineReadRecord
from benchmark.runner import RunnerDeps, RunRequest
from benchmark.tests.artifacts_helpers import make_config
from benchmark.tests.runner_helpers import (
    FILTER,
    FakeClock,
    FakeDrivers,
    FakeStack,
    RecordingArtifacts,
    RecordingFailures,
    RunLog,
    fake_git_commit,
    fake_ingest,
    fake_provision,
    make_client_factory,
)

if TYPE_CHECKING:
    from pathlib import Path

    from benchmark.config_schemas import BenchmarkConfig

__all__ = [
    "CORPUS_YAML",
    "DEFAULT_RESULTS",
    "ENTITIES_YAML",
    "ERRORS_YAML",
    "FILTER",
    "Wiring",
    "browse_record",
    "detail_result",
    "timeline_record",
    "voice_check_record",
    "write_corpus",
]


# ---------------------------------------------------------------------------
# Scripted capability records (real driver/scorer record types)
# ---------------------------------------------------------------------------


def browse_record() -> EntryBrowseRecord:
    from benchmark.tests.scoring_helpers import summary

    return EntryBrowseRecord(
        entries=(summary("entry-1", "Anna Meyer"),), total=1, pages_fetched=1, autocomplete=()
    )


def voice_check_record(chapter_ref: str) -> VoiceCheckRecord:
    """One flagged line naming the L01 ground-truth topic (Anna/HafenCity)."""
    return VoiceCheckRecord(
        chapter_id=chapter_ref,
        characters=(
            VoiceCheckFinding(
                character_name="Anna Meyer",
                match_score=0.4,
                band="low",
                match_judgment=None,
                qualitative_sub_score=None,
                metric_delta_subscore=None,
                flagged_lines=(
                    FlaggedLine(
                        quote="Anna Meyer wohnt in der HafenCity.",
                        reason="abweichend vom Profil",
                    ),
                ),
                has_profile=True,
                n_comparable_metrics=3,
            ),
        ),
        progress_messages=(),
    )


def timeline_record() -> TimelineReadRecord:
    return TimelineReadRecord(
        events=(), single=None, ages=(), characters_with_age=0, characters_without_age=0
    )


DEFAULT_RESULTS: Final[dict[str, CapabilityResult]] = {
    "CAP-OUT-01": CapabilityResult.ok("CAP-OUT-01", parsed=browse_record(), elapsed_seconds=1.0),
    "CAP-OUT-07": CapabilityResult.ok("CAP-OUT-07", parsed=timeline_record(), elapsed_seconds=1.0),
    "CAP-CHK-05": CapabilityResult.ok(
        "CAP-CHK-05", parsed=voice_check_record("chapter-1"), elapsed_seconds=2.0
    ),
}


def detail_result() -> CapabilityResult:
    from benchmark.drivers.out_records import EntityDetailRecord
    from benchmark.tests.scoring_helpers import detail

    record: EntityDetailRecord = detail(
        "entry-1", name="Anna Meyer", metadata={"wohnt_in": "HafenCity"}
    )
    return CapabilityResult.ok("CAP-OUT-03", parsed=record, elapsed_seconds=1.0)


# ---------------------------------------------------------------------------
# Tiny REAL corpus (1 chapter, 1 entity/fact, light variant)
# ---------------------------------------------------------------------------

CORPUS_YAML: Final[str] = (
    "name: runner-test-corpus\n"
    "version: 1\n"
    "language: de\n"
    "chapters: [ch-01]\n"
    "variants:\n"
    "  - name: light\n"
    "    registry: variants/light/errors.yaml\n"
    "reference:\n"
    "  entities: reference/entities.yaml\n"
    "  relations: reference/relations.yaml\n"
    "  events: reference/events.yaml\n"
)

ENTITIES_YAML: Final[str] = (
    "persons:\n"
    "  - id: p1\n"
    "    name: Anna Meyer\n"
    "    aliases: []\n"
    "    facts:\n"
    "      - id: F001\n"
    "        predicate: wohnt_in\n"
    "        value: HafenCity\n"
    "        source_chapters: [1]\n"
    "places: []\n"
    "objects: []\n"
)

ERRORS_YAML: Final[str] = (
    "base: clean\n"
    "errors:\n"
    "  - id: L01\n"
    "    class: L\n"
    "    chapter: ch-01\n"
    "    anchor: 'kam aus der HafenCity'\n"
    "    replacement: 'zog in die HafenCity'\n"
    "    ground_truth_ref: F001\n"
    "    description: 'Wohnort-Widerspruch'\n"
)


def write_corpus(root: Path) -> Path:
    """Materialize the tiny corpus (1 chapter, 1 entity/fact, light variant)."""
    (root / "clean" / "chapters").mkdir(parents=True)
    (root / "clean" / "chapters" / "ch-01.md").write_text(
        "# Kapitel Eins\n\nAnna Meyer kam aus der HafenCity.\n", encoding="utf-8"
    )
    (root / "reference").mkdir()
    (root / "reference" / "entities.yaml").write_text(ENTITIES_YAML, encoding="utf-8")
    (root / "reference" / "relations.yaml").write_text("[]\n", encoding="utf-8")
    (root / "reference" / "events.yaml").write_text("[]\n", encoding="utf-8")
    (root / "variants" / "light").mkdir(parents=True)
    (root / "variants" / "light" / "errors.yaml").write_text(ERRORS_YAML, encoding="utf-8")
    (root / "variants" / "light" / "manifest.yaml").write_text(
        "chapters_touched: [ch-01]\n", encoding="utf-8"
    )
    (root / "corpus.yaml").write_text(CORPUS_YAML, encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# Wiring: one assembled run (log, recorders, fakes, deps, request)
# ---------------------------------------------------------------------------


class Wiring:
    """One wired run: log, recorders, fakes, deps, and request."""

    def __init__(
        self,
        tmp_path: Path,
        *,
        results: dict[str, CapabilityResult] | None = None,
        ingest_error: Exception | None = None,
        capabilities: tuple[str, ...] = FILTER,
        variant: str = "light",
        keep_stack: bool = False,
    ) -> None:
        self.log = RunLog()
        self.artifacts = RecordingArtifacts(self.log)
        self.failures = RecordingFailures(self.log)
        self.drivers = FakeDrivers(
            self.log, {**DEFAULT_RESULTS, "CAP-OUT-03": detail_result(), **(results or {})}
        )
        self.deps = RunnerDeps(
            stack_factory=lambda _config: FakeStack(self.log),
            client_factory=make_client_factory(self.log),
            provision_fn=fake_provision(self.log),
            load_corpus_fn=load_corpus,
            ingest_fn=fake_ingest(self.log, error=ingest_error),
            driver_for_fn=self.drivers.driver_for,
            write_artifacts_fn=self.artifacts.write,
            write_failure_fn=self.failures.write,
            git_commit_fn=fake_git_commit(self.log),
            clock=FakeClock(),
            ingest_sleeper=lambda _seconds: None,
            corpus_root=write_corpus(tmp_path / "corpus"),
        )
        config: BenchmarkConfig = make_config()
        self.request = RunRequest(
            variant=variant,
            mode="incremental",
            out_dir=tmp_path / "out",
            config=config,
            keep_stack=keep_stack,
            capabilities=capabilities,
        )
