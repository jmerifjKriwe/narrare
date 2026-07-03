"""Import tests for writing contract Protocol modules.

Category A coverage: Contract Protocols (0% → 100%).
These are pure @runtime_checkable Protocol files at 0% because they're
only imported under TYPE_CHECKING.  An import test that loads each module
covers all lines — the ``class`` and ``def`` statements execute on import.
"""

from __future__ import annotations

import inspect
from typing import Protocol


def _assert_protocol_exists(mod_path: str, cls_name: str) -> None:
    """Helper: import *mod_path*, assert *cls_name* is a Protocol subclass."""
    import importlib

    mod = importlib.import_module(mod_path)
    cls = getattr(mod, cls_name)
    assert cls is not None
    assert inspect.isclass(cls)
    assert issubclass(cls, Protocol)


class TestCoAuthorServiceProtocol:
    """CoAuthorServiceProtocol import and structural checks."""

    def test_module_imports_and_protocol_exists(self) -> None:
        """Importing the module executes all class/def statements on import."""
        _assert_protocol_exists(
            "narrare.writing.contracts_coauthor",
            "CoAuthorServiceProtocol",
        )


class TestExtendServiceProtocol:
    """ExtendServiceProtocol import and structural checks."""

    def test_module_imports_and_protocol_exists(self) -> None:
        """Importing the module executes all class/def statements on import."""
        _assert_protocol_exists(
            "narrare.writing.contracts_extend",
            "ExtendServiceProtocol",
        )


class TestRewriteServiceProtocol:
    """RewriteServiceProtocol import and structural checks."""

    def test_module_imports_and_protocol_exists(self) -> None:
        """Importing the module executes all class/def statements on import."""
        _assert_protocol_exists(
            "narrare.writing.contracts_rewrite",
            "RewriteServiceProtocol",
        )


class TestStorySuggestServiceProtocol:
    """StorySuggestServiceProtocol import and structural checks."""

    def test_module_imports_and_protocol_exists(self) -> None:
        """Importing the module executes all class/def statements on import."""
        _assert_protocol_exists(
            "narrare.writing.contracts_story_suggest",
            "StorySuggestServiceProtocol",
        )
