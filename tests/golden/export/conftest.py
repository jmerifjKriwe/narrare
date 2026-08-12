"""Shared pytest fixtures for the narrare-roman Golden-Pages probes.

Home of the ``typst_workdir`` fixture used by every Slice-5 inline probe
(``test_geometric_spine.py``, ``test_running_heads.py``, …). Extracted
here so each sub-slice probe owns only its assertions, not the workspace
plumbing (RULE-06 / DRY). Promoted + hardened into
``tests/golden/export/harness/`` by Slice 7.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.golden.export._typst_probe_helpers import REPO_ROOT

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def typst_workdir() -> Iterator[Path]:
    """Per-test workspace INSIDE the repo root.

    Typst's ``--root`` flag requires the source file to live under it, so
    a pytest ``tmp_path`` under ``/tmp`` cannot import the in-repo
    package. This fixture carves a per-test scratch dir under
    ``<repo>/.typst-test-tmp/`` (gitignored) and tears it down on exit
    via :class:`tempfile.TemporaryDirectory`. The Slice-6 production
    renderer faces the same constraint and resolves it the same way
    (write the wrapper.typ next to the package, compile with
    ``--root <repo>``).
    """
    parent = REPO_ROOT / ".typst-test-tmp"
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(parent), prefix="probe-") as workdir:
        yield Path(workdir)
