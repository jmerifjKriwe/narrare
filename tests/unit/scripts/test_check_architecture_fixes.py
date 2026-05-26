"""Tests for architecture checker false-positive fixes.

Fix A: Import-aware .run() check — NarrareAgent imports suppress .run()/.run_sync() flags.
Fix B: TYPE_CHECKING scope tracking — imports inside if TYPE_CHECKING: are skipped.
"""

from __future__ import annotations

import ast

from scripts.architecture.agent_checks import (
    check_agent_imports,
    check_agent_instantiation,
)
from scripts.architecture.checkers import check_llm_imports, check_llm_urls
from scripts.architecture.helpers import compute_type_checking_lines


def _parse(source: str) -> ast.AST:
    """Parse source code into an AST."""
    return ast.parse(source)


def _lines(source: str) -> list[str]:
    """Split source into lines."""
    return source.splitlines()


# =====================================================================
# Fix A — Import-aware .run() / .run_sync() check
# =====================================================================


class TestImportAwareRunCheck:
    """NarrareAgent .run() calls are not flagged when imports are present."""

    def test_run_not_flagged_with_narrare_import(self) -> None:
        """agent.run() with narrare_core.agents import → NOT flagged."""
        source = """\
from narrare_core.agents.summary_agent import ChapterSummaryAgent

agent = ChapterSummaryAgent()
result = agent.run(prompt="Hello")
"""
        violations = check_agent_instantiation(
            "apps/api/narrare/writing/service.py",
            _parse(source),
            _lines(source),
            agent_allowed_modules=["packages/core/narrare_core/agents/"],
        )
        assert violations == []

    def test_run_flagged_without_narrare_import(self) -> None:
        """agent.run() WITHOUT narrare_core.agents import → IS flagged."""
        source = """\
agent = SomeOtherThing()
result = agent.run(prompt="Hello")
"""
        violations = check_agent_instantiation(
            "apps/api/narrare/writing/service.py",
            _parse(source),
            _lines(source),
            agent_allowed_modules=["packages/core/narrare_core/agents/"],
        )
        assert len(violations) == 1
        assert ".run()" in violations[0].detail

    def test_constructor_still_flagged_with_narrare_import(self) -> None:
        """Raw Agent() constructor → ALWAYS flagged, even with narrare imports."""
        source = """\
from narrare_core.agents.summary_agent import ChapterSummaryAgent

agent = Agent("my-agent")
"""
        violations = check_agent_instantiation(
            "apps/api/narrare/writing/service.py",
            _parse(source),
            _lines(source),
            agent_allowed_modules=["packages/core/narrare_core/agents/"],
        )
        assert len(violations) == 1
        assert "Agent(...) instantiation" in violations[0].detail

    def test_run_sync_not_flagged_with_narrare_import(self) -> None:
        """agent.run_sync() with narrare_core.agents import → NOT flagged."""
        source = """\
from narrare_core.agents.summary_agent import ChapterSummaryAgent

agent = ChapterSummaryAgent()
result = agent.run_sync(prompt="Hello")
"""
        violations = check_agent_instantiation(
            "apps/api/narrare/writing/service.py",
            _parse(source),
            _lines(source),
            agent_allowed_modules=["packages/core/narrare_core/agents/"],
        )
        assert violations == []

    def test_run_sync_flagged_without_narrare_import(self) -> None:
        """agent.run_sync() WITHOUT narrare import → IS flagged."""
        source = """\
agent = SomeOtherThing()
result = agent.run_sync(prompt="Hello")
"""
        violations = check_agent_instantiation(
            "apps/api/narrare/writing/service.py",
            _parse(source),
            _lines(source),
            agent_allowed_modules=["packages/core/narrare_core/agents/"],
        )
        assert len(violations) == 1
        assert ".run_sync()" in violations[0].detail

    def test_non_agent_run_still_works(self) -> None:
        """Variables not containing 'agent' in name → never flagged (existing behavior)."""
        source = """\
result = my_model.run(prompt="Hello")
"""
        violations = check_agent_instantiation(
            "apps/api/narrare/writing/service.py",
            _parse(source),
            _lines(source),
            agent_allowed_modules=["packages/core/narrare_core/agents/"],
        )
        assert violations == []

    def test_allowed_module_skips_all_checks(self) -> None:
        """Files in agent_allowed_modules are not checked at all."""
        source = """\
agent = Agent("test")
result = agent.run(prompt="Hello")
"""
        violations = check_agent_instantiation(
            "packages/core/narrare_core/agents/summary_agent.py",
            _parse(source),
            _lines(source),
            agent_allowed_modules=["packages/core/narrare_core/agents/"],
        )
        assert violations == []


# =====================================================================
# Fix B — TYPE_CHECKING scope tracking
# =====================================================================


class TestTypeCheckingLines:
    """compute_type_checking_lines identifies TYPE_CHECKING-guarded code."""

    def test_simple_type_checking(self) -> None:
        """if TYPE_CHECKING: block lines are detected."""
        source = """\
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai import Agent

x = 1
"""
        tc_lines = compute_type_checking_lines(_parse(source))
        # Lines inside TYPE_CHECKING should be detected
        assert 3 in tc_lines  # 'if TYPE_CHECKING:'
        assert 4 in tc_lines  # 'from pydantic_ai import Agent'

    def test_typing_prefix_type_checking(self) -> None:
        """if typing.TYPE_CHECKING: block lines are detected."""
        source = """\
import typing

if typing.TYPE_CHECKING:
    from pydantic_ai import Agent

x = 1
"""
        tc_lines = compute_type_checking_lines(_parse(source))
        assert 3 in tc_lines  # 'if typing.TYPE_CHECKING:'
        assert 4 in tc_lines  # 'from pydantic_ai import Agent'

    def test_no_type_checking(self) -> None:
        """No TYPE_CHECKING block → empty set."""
        source = """\
from pydantic_ai import Agent
x = 1
"""
        tc_lines = compute_type_checking_lines(_parse(source))
        assert tc_lines == set()


class TestCheckLlmImportsTypeChecking:
    """check_llm_imports skips imports inside TYPE_CHECKING blocks."""

    def test_import_inside_type_checking_not_flagged(self) -> None:
        """Import inside if TYPE_CHECKING: → NOT flagged."""
        source = """\
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai import Agent
"""
        violations = check_llm_imports(
            "apps/api/narrare/writing/service.py",
            _parse(source),
            _lines(source),
            allowed_modules=["packages/core/narrare_core/llm/"],
            forbidden_imports=["pydantic_ai"],
        )
        assert violations == []

    def test_import_outside_type_checking_flagged(self) -> None:
        """Import outside TYPE_CHECKING → IS flagged."""
        source = """\
from pydantic_ai import Agent
"""
        violations = check_llm_imports(
            "apps/api/narrare/writing/service.py",
            _parse(source),
            _lines(source),
            allowed_modules=["packages/core/narrare_core/llm/"],
            forbidden_imports=["pydantic_ai"],
        )
        assert len(violations) == 1
        assert "pydantic_ai" in violations[0].detail

    def test_mixed_imports_only_non_tc_flagged(self) -> None:
        """Mix: only non-TYPE_CHECKING imports are flagged."""
        source = """\
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai import Agent

import openai
"""
        violations = check_llm_imports(
            "apps/api/narrare/writing/service.py",
            _parse(source),
            _lines(source),
            allowed_modules=["packages/core/narrare_core/llm/"],
            forbidden_imports=["pydantic_ai", "openai"],
        )
        # Only the bare openai import at line 6 should be flagged
        assert len(violations) == 1
        assert violations[0].line == 6
        assert "openai" in violations[0].detail


class TestCheckAgentImportsTypeChecking:
    """check_agent_imports skips imports inside TYPE_CHECKING blocks."""

    def test_agent_import_inside_type_checking_not_flagged(self) -> None:
        """Agent import inside if TYPE_CHECKING: → NOT flagged."""
        source = """\
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai import Agent
"""
        violations = check_agent_imports(
            "apps/api/narrare/writing/service.py",
            _parse(source),
            _lines(source),
            agent_allowed_modules=["packages/core/narrare_core/agents/"],
        )
        assert violations == []

    def test_agent_import_outside_type_checking_flagged(self) -> None:
        """Agent import outside TYPE_CHECKING → IS flagged."""
        source = """\
from pydantic_ai import Agent
"""
        violations = check_agent_imports(
            "apps/api/narrare/writing/service.py",
            _parse(source),
            _lines(source),
            agent_allowed_modules=["packages/core/narrare_core/agents/"],
        )
        assert len(violations) == 1

    def test_mixed_tc_and_non_tc_agent_imports(self) -> None:
        """TYPE_CHECKING import skipped, non-TC import flagged."""
        source = """\
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai import Agent

from pydantic_ai import Agent
"""
        violations = check_agent_imports(
            "apps/api/narrare/writing/service.py",
            _parse(source),
            _lines(source),
            agent_allowed_modules=["packages/core/narrare_core/agents/"],
        )
        assert len(violations) == 1
        assert violations[0].line == 6


class TestCheckLlmUrlsTypeChecking:
    """check_llm_urls skips URLs inside TYPE_CHECKING blocks."""

    def test_url_inside_type_checking_not_flagged(self) -> None:
        """URL inside if TYPE_CHECKING: → NOT flagged."""
        source = """\
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    BASE = "https://api.openai.com/v1"
"""
        violations = check_llm_urls(
            "apps/api/narrare/writing/service.py",
            _lines(source),
            allowed_modules=["packages/core/narrare_core/llm/"],
            forbidden_urls=["api.openai.com"],
            tree=_parse(source),
        )
        assert violations == []

    def test_url_outside_type_checking_flagged(self) -> None:
        """URL outside TYPE_CHECKING → IS flagged."""
        source = """\
BASE = "https://api.openai.com/v1"
"""
        violations = check_llm_urls(
            "apps/api/narrare/writing/service.py",
            _lines(source),
            allowed_modules=["packages/core/narrare_core/llm/"],
            forbidden_urls=["api.openai.com"],
            tree=_parse(source),
        )
        assert len(violations) == 1

    def test_mixed_url_positions(self) -> None:
        """Only non-TYPE_CHECKING URLs are flagged."""
        source = """\
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    TYPE_URL = "https://api.openai.com/v1"

REAL_URL = "https://api.anthropic.com/v1"
"""
        violations = check_llm_urls(
            "apps/api/narrare/writing/service.py",
            _lines(source),
            allowed_modules=["packages/core/narrare_core/llm/"],
            forbidden_urls=["api.openai.com", "api.anthropic.com"],
            tree=_parse(source),
        )
        assert len(violations) == 1
        assert violations[0].line == 6
        assert "api.anthropic.com" in violations[0].detail
