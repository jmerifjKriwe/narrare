"""Unit tests for the stack-facts providers (plan Task 14/15 wiring).

``parse_image_digests`` parsing rules and ``StackManager.facts()`` —
compose-file SHA-256 + per-service repository digests from
``docker compose images --format json``. NO docker: subprocess I/O goes
through a canned ``CommandRunner`` (``test_stack`` precedent). Split
from ``test_stack.py`` per RULE-04.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest

from benchmark.config_schemas import (
    ApiConfig,
    AuthConfig,
    BenchmarkConfig,
    LlmConfig,
    RunConfig,
    StackConfig,
)
from benchmark.stack import (
    RELEASE_COMPOSE_FILE,
    CommandResult,
    StackError,
    StackManager,
    parse_image_digests,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

_IMAGES_JSON = (
    '[{"Service": "api", "Repository": "ghcr.io/narrare/narrare", "Digest": "sha256:aaa", '
    '"ID": "sha256:111"}, {"Service": "postgres", "Repository": "postgres", '
    '"Digest": "sha256:bbb", "ID": "sha256:222"}]'
)

_PREFIX = "narrare-benchmark"


class CannedRunner:
    """Canned ``CommandRunner``: matches argv tails to ``(rc, out, err)``."""

    def __init__(self, responses: dict[tuple[str, ...], tuple[int, str, str]]) -> None:
        self.responses = responses
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str]) -> CommandResult:
        call = list(args)
        self.calls.append(call)
        for tail, (rc, out, err) in self.responses.items():
            if len(call) >= len(tail) and tuple(call[-len(tail) :]) == tail:
                return CommandResult(tuple(call), rc, out, err)
        return CommandResult(tuple(call), 0, "", "")


class AlwaysHealthy:
    """No-op probe — ``facts()`` never waits for health."""

    def healthy(self, base_url: str) -> bool:
        return base_url != ""


def make_manager(runner: CannedRunner, override_dir: Path) -> StackManager:
    config = BenchmarkConfig(
        stack=StackConfig(_PREFIX, 18080, 18180),
        api=ApiConfig(None, 60.0),
        auth=AuthConfig("benchmark@example.com", "change-me-benchmark-password"),
        llm=LlmConfig("anthropic", "sk-test-dummy", "m", "http://localhost:11434", "general"),
        run=RunConfig(["clean"], ["incremental"], False, []),
    )
    return StackManager(
        config,
        runner=runner,
        probe=AlwaysHealthy(),
        port_selector=lambda low, high: 18080,
        override_dir=override_dir,
    )


class TestImageDigestParsing:
    def test_parses_service_keyed_digests_sorted(self) -> None:
        pairs = parse_image_digests(_IMAGES_JSON)

        assert pairs == (("api", "sha256:aaa"), ("postgres", "sha256:bbb"))

    def test_falls_back_to_repository_when_service_missing(self) -> None:
        pairs = parse_image_digests('[{"Repository": "postgres", "Digest": "sha256:bbb"}]')

        assert pairs == (("postgres", "sha256:bbb"),)

    def test_falls_back_to_image_id_when_digest_empty(self) -> None:
        pairs = parse_image_digests('[{"Service": "api", "Digest": "", "ID": "sha256:111"}]')

        assert pairs == (("api", "sha256:111"),)

    def test_skips_rows_without_any_identifier(self) -> None:
        pairs = parse_image_digests('[{"Repository": "", "Digest": ""}]')

        assert pairs == ()

    def test_deduplicates_shared_images(self) -> None:
        pairs = parse_image_digests(
            '[{"Service": "api", "Digest": "sha256:aaa"},'
            ' {"Service": "api", "Digest": "sha256:aaa"}]'
        )

        assert pairs == (("api", "sha256:aaa"),)

    def test_empty_output_yields_no_pairs(self) -> None:
        assert parse_image_digests("") == ()
        assert parse_image_digests("[]") == ()

    def test_invalid_json_raises_stack_error(self) -> None:
        with pytest.raises(StackError, match="images"):
            parse_image_digests("not-json")


class TestStackFacts:
    def test_facts_return_compose_hash_and_digests(self, tmp_path: Path) -> None:
        runner = CannedRunner({("images", "--format", "json"): (0, _IMAGES_JSON, "")})
        manager = make_manager(runner, tmp_path)

        compose_sha256, digests = manager.facts()

        assert len(compose_sha256) == 64
        assert compose_sha256 == hashlib.sha256(RELEASE_COMPOSE_FILE.read_bytes()).hexdigest()
        assert digests == (("api", "sha256:aaa"), ("postgres", "sha256:bbb"))
        tail = tuple(runner.calls[0][-3:])
        assert tail == ("images", "--format", "json")

    def test_facts_raise_when_compose_images_fails(self, tmp_path: Path) -> None:
        runner = CannedRunner({("images", "--format", "json"): (1, "", "boom")})
        manager = make_manager(runner, tmp_path)

        with pytest.raises(StackError, match="compose images failed"):
            manager.facts()
