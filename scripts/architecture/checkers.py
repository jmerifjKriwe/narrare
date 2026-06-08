"""Narrare Architecture Constraint Checker — backward-compatible re-export facade.

All checker implementations live in :mod:`scripts.architecture._checkers`.
This module re-exports the public API so existing imports continue to work::

    from scripts.architecture.checkers import scan_file
    from scripts.architecture.checkers import check_llm_imports
"""

from scripts.architecture._checkers import (
    check_bare_async_session,
    check_bare_except,
    check_bare_magic_mock,
    check_file_size,
    check_hardcoded_constants,
    check_hardcoded_model_config,
    check_inline_prompts,
    check_llm_imports,
    check_llm_urls,
    check_prompt_building,
    scan_file,
)

__all__ = [
    "check_bare_async_session",
    "check_bare_except",
    "check_bare_magic_mock",
    "check_file_size",
    "check_hardcoded_constants",
    "check_hardcoded_model_config",
    "check_inline_prompts",
    "check_llm_imports",
    "check_llm_urls",
    "check_prompt_building",
    "scan_file",
]
