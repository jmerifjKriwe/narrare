"""RULE-08 export-binary-confinement checker — self-test (D6).

These are pure unit tests: no I/O, no network. They prove the AST alias
resolution is load-bearing — every aliased import form that could evade a
naive string-grep checker is resolved correctly.

All synthetic source fixtures live inside ``ast.parse()`` string literals
(never as real executable code in this module), so the checker scanning this
own test file finds no real subprocess calls.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest
from scripts.architecture._checkers.export_binary_confinement import (
    check_export_binary_confinement,
)

if TYPE_CHECKING:
    from scripts.architecture.types import Violation

# The four renderer-adapter files — the ONLY places typst/pandoc may spawn.
ALLOWED_MODULES = [
    "apps/api/narrare/export/renderers/typst.py",
    "apps/api/narrare/export/renderers/pandoc_base.py",
    "apps/api/narrare/export/renderers/pandoc_md.py",
    "apps/api/narrare/export/renderers/pandoc_epub.py",
]

# A path OUTSIDE the renderer adapters — every violation case uses this.
OUTSIDE_PATH = "apps/api/narrare/export/service.py"


def _violations(src: str, rel_path: str = OUTSIDE_PATH) -> list[Violation]:
    """Run the confinement checker on a synthetic source string.

    Returns the list of Violation objects (empty = clean).
    """
    tree = ast.parse(src)
    source_lines = src.splitlines()
    return check_export_binary_confinement(rel_path, tree, source_lines, ALLOWED_MODULES)


def _count_rule08(violations: list[Violation]) -> int:
    return sum(1 for v in violations if v.rule == "RULE-08")


# ===========================================================================
# (a) Every alias form — must be flagged when OUTSIDE the renderers.
# This is the load-bearing proof that alias resolution works.
# ===========================================================================


class TestAliasResolution:
    """Every import-alias form resolves and is caught."""

    def test_plain_subprocess_run_list_form(self):
        src = "import subprocess\nsubprocess.run(['typst', 'compile', 'in.typ'])\n"
        assert _count_rule08(_violations(src)) == 1

    def test_aliased_module_sp_run(self):
        src = "import subprocess as sp\nsp.run(['pandoc', '-o', 'out.pdf'])\n"
        assert _count_rule08(_violations(src)) == 1

    def test_from_import_run(self):
        src = "from subprocess import run\nrun(['typst', 'compile'])\n"
        assert _count_rule08(_violations(src)) == 1

    def test_from_import_run_aliased(self):
        src = "from subprocess import run as r\nr(['pandoc'])\n"
        assert _count_rule08(_violations(src)) == 1

    def test_subprocess_popen(self):
        src = "import subprocess\nsubprocess.Popen(['typst'])\n"
        assert _count_rule08(_violations(src)) == 1

    def test_subprocess_call(self):
        src = "import subprocess\nsubprocess.call(['pandoc'])\n"
        assert _count_rule08(_violations(src)) == 1

    def test_subprocess_check_call(self):
        src = "import subprocess\nsubprocess.check_call(['typst'])\n"
        assert _count_rule08(_violations(src)) == 1

    def test_subprocess_check_output(self):
        src = "import subprocess\nsubprocess.check_output(['pandoc'])\n"
        assert _count_rule08(_violations(src)) == 1

    def test_asyncio_create_subprocess_exec_plain(self):
        src = "import asyncio\nasyncio.create_subprocess_exec('typst', 'compile', 'in.typ')\n"
        assert _count_rule08(_violations(src)) == 1

    def test_asyncio_create_subprocess_exec_aliased_module(self):
        src = "import asyncio as aio\naio.create_subprocess_exec('pandoc', '--version')\n"
        assert _count_rule08(_violations(src)) == 1

    def test_from_import_create_subprocess_exec(self):
        src = "from asyncio import create_subprocess_exec\ncreate_subprocess_exec('typst')\n"
        assert _count_rule08(_violations(src)) == 1

    def test_from_import_create_subprocess_exec_aliased(self):
        src = "from asyncio import create_subprocess_exec as cspe\ncspe('pandoc')\n"
        assert _count_rule08(_violations(src)) == 1

    def test_asyncio_create_subprocess_shell(self):
        src = "import asyncio\nasyncio.create_subprocess_shell('typst compile in.typ out.pdf')\n"
        assert _count_rule08(_violations(src)) == 1

    def test_os_system_shell(self):
        src = "import os\nos.system('typst compile in.typ')\n"
        assert _count_rule08(_violations(src)) == 1

    def test_os_popen_aliased(self):
        src = "import os as o\no.popen('pandoc -o out.epub book.html')\n"
        assert _count_rule08(_violations(src)) == 1

    def test_from_os_import_system(self):
        src = "from os import system\nsystem('typst --version')\n"
        assert _count_rule08(_violations(src)) == 1


# ===========================================================================
# (b) Direct call OUTSIDE the allowed dir → flagged (covered above);
#     (c) the SAME call INSIDE an allowed renderer file → exempt.
# ===========================================================================


class TestExemptionByLocation:
    """A real spawn is exempt inside a renderer adapter, flagged outside."""

    @pytest.mark.parametrize("allowed_path", ALLOWED_MODULES)
    def test_spawn_exempt_inside_each_renderer(self, allowed_path):
        src = "import asyncio\nasyncio.create_subprocess_exec('typst', 'compile', 'in.typ')\n"
        assert _violations(src, rel_path=allowed_path) == []

    def test_spawn_flagged_outside_renderers(self):
        src = "import asyncio\nasyncio.create_subprocess_exec('typst', 'compile', 'in.typ')\n"
        # Same source, outside → flagged.
        assert _count_rule08(_violations(src, rel_path=OUTSIDE_PATH)) == 1

    def test_pandoc_exempt_inside_pandoc_base(self):
        src = "import subprocess\nsubprocess.run(['pandoc', '--version'])\n"
        assert _violations(src, rel_path="apps/api/narrare/export/renderers/pandoc_base.py") == []


# ===========================================================================
# Negative cases — must NOT be flagged.
# ===========================================================================


class TestNotFlagged:
    """Calls that are correctly out of scope or non-evasive."""

    def test_epubcheck_anywhere_is_out_of_scope(self):
        # EPUBCheck is CI-only (test harness); deliberately NOT confined.
        src = "import subprocess\nsubprocess.run(['epubcheck', 'book.epub'])\n"
        assert _violations(src) == []
        # ...even though the spawn mechanism is real:
        assert _count_rule08(_violations("import subprocess\nsubprocess.run(['typst'])\n")) == 1

    def test_non_render_binary_not_flagged(self):
        src = "import subprocess\nsubprocess.run(['ls', '-la'])\n"
        assert _violations(src) == []

    def test_echo_command_not_flagged(self):
        src = "import os\nos.system('echo hello')\n"
        assert _violations(src) == []

    def test_typst_as_argument_not_binary_not_flagged(self):
        # "typst" as a non-binary positional (exec form, exact match) inside a
        # list whose first element is NOT typst — exec-form match is on the
        # discrete token, but here 'typst' appears as a later element. The
        # plan says "first or any positional arg", so this IS flagged (safe
        # over-approximation; the renderer exemption covers legit use).
        # This test documents that the checker is conservative:
        src = "import subprocess\nsubprocess.run(['echo', 'typst'])\n"
        assert _count_rule08(_violations(src)) == 1

    def test_substring_in_exec_list_not_partial_match(self):
        # 'typst-output.pdf' is NOT the binary token → exec-form exact match
        # means it is NOT flagged on that element alone. But the list also
        # contains no 'typst'/'pandoc' token, so clean.
        src = "import subprocess\nsubprocess.run(['cp', 'a.pdf', 'typst-output.pdf'])\n"
        assert _violations(src) == []

    def test_shell_substring_pandoc_flagged(self):
        # Shell form: substring match catches the binary embedded in a command.
        src = "import os\nos.system('xargs pandoc < files.txt')\n"
        assert _count_rule08(_violations(src)) == 1


# ===========================================================================
# (d) Evasion attempts the AST cannot resolve — documented limitation.
# ===========================================================================


class TestEvasionLimitations:
    """Dynamic binary-name construction is NOT caught (documented honestly).

    The confinement is a guardrail against accidental drift, not a sandbox
    against deliberate evasion. These tests pin the limitation so a future
    "improvement" that silently regresses the honest contract is caught.
    """

    def test_concatenated_binary_name_not_caught(self):
        src = "import subprocess\nsubprocess.run(['typ' + 'st'])\n"
        # AST sees a BinOp, not a Constant — cannot resolve. Documented.
        assert _violations(src) == []

    def test_variable_binary_name_not_caught(self):
        src = "import subprocess\nbinary = 'typst'\nsubprocess.run([binary, 'compile'])\n"
        # Name, not Constant — cannot statically resolve. Documented.
        assert _violations(src) == []


# ===========================================================================
# (e) Clean file → no flags.
# ===========================================================================


class TestCleanFile:
    def test_clean_file_no_subprocess(self):
        src = (
            "from dataclasses import dataclass\n"
            "\n"
            "@dataclass\n"
            "class Foo:\n"
            "    x: int\n"
            "\n"
            "print(Foo(1))\n"
        )
        assert _violations(src) == []

    def test_subprocess_call_for_unrelated_binary_clean(self):
        src = (
            "import subprocess\n"
            "subprocess.run(['git', 'status'])\n"
            "subprocess.check_output(['date'])\n"
        )
        assert _violations(src) == []


# ===========================================================================
# type-checking guard — dead code under ``if TYPE_CHECKING:`` is skipped
# (consistent with the llm.py / RULE-01b checker).
# ===========================================================================


class TestTypeCheckingGuard:
    def test_call_under_type_checking_skipped(self):
        src = (
            "from typing import TYPE_CHECKING\n"
            "import subprocess\n"
            "if TYPE_CHECKING:\n"
            "    subprocess.run(['typst'])\n"
        )
        # Dead code — never executes at runtime. Not flagged.
        assert _violations(src) == []
