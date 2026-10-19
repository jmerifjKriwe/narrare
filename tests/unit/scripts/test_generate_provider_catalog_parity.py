"""Parity gate tests: one mutation per hand-written Core surface.

Each test copies only the four Core surface files into a temporary tree, then
rewrites exactly one fact. ``_mutate`` asserts that the replacement changed the
file, so a mutation string that no longer matches the surface cannot leave a
vacuous green test behind.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from scripts.generate_provider_catalog import CATALOG_PATH, load_catalog
from scripts.provider_catalog_parity import check_parity

REPO_ROOT = Path(__file__).resolve().parents[3]

PRICING = "packages/core/narrare_core/llm/model_pricing.py"
CACHE = "packages/core/narrare_core/llm/_providers/cache_settings.py"
MEM0 = "packages/core/narrare_core/memory/mem0_client.py"
REGISTRY = "packages/core/narrare_core/llm/_providers/registry.py"

MUTATED_FILES = (PRICING, CACHE, MEM0, REGISTRY)


def _sandbox(tmp_path: Path) -> Path:
    """Copy the Core surfaces into ``tmp_path`` so a mutation stays local."""
    for relative in MUTATED_FILES:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, destination)
    return tmp_path


def _mutate(root: Path, relative: str, old: str, new: str) -> None:
    """Apply one exact replacement, proving it matched and changed the file."""
    target = root / relative
    before = target.read_text(encoding="utf-8")
    assert old in before, f"mutation string not found in {relative}: {old!r}"
    after = before.replace(old, new)
    assert after != before, f"mutation did not change {relative}"
    target.write_text(after, encoding="utf-8")


def test_pristine_tree_has_no_violations(tmp_path: Path) -> None:
    assert check_parity(load_catalog(CATALOG_PATH), _sandbox(tmp_path)) == []


def test_missing_pricing_key_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        PRICING,
        '    "groq": {"input": 0.5, "output": 1.0},\n',
        "",
    )

    violations = check_parity(load_catalog(CATALOG_PATH), root)

    assert any(
        violation.surface == "pricing.keys" and "groq" in violation.detail
        for violation in violations
    )


def test_disagreeing_pricing_value_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        PRICING,
        '"groq": {"input": 0.5, "output": 1.0}',
        '"groq": {"input": 0.7, "output": 1.0}',
    )

    violations = check_parity(load_catalog(CATALOG_PATH), root)

    matches = [v for v in violations if v.surface == "pricing.values" and "groq" in v.detail]
    assert len(matches) == 1
    assert "0.5" in matches[0].detail
    assert "0.7" in matches[0].detail


def test_duplicate_cache_arm_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        CACHE,
        '        case "ollama":\n            return {}  # No caching support\n',
        '        case "groq":\n            return {}  # No caching support\n',
    )

    violations = check_parity(load_catalog(CATALOG_PATH), root)

    assert any(
        violation.surface == "cache.arms"
        and "groq" in violation.detail
        and "2 match arms" in violation.detail
        for violation in violations
    )


def test_wildcard_before_provider_arms_shadows_them(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        CACHE,
        "    match provider_name:\n",
        "    match provider_name:\n        case _:\n            return {}\n",
    )

    violations = check_parity(load_catalog(CATALOG_PATH), root)

    assert any(
        violation.surface == "cache.arms"
        and "anthropic" in violation.detail
        and "shadowed" in violation.detail
        for violation in violations
    )


def test_cache_body_disagreeing_with_policy_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        CACHE,
        '            return {"cache_control": True}',
        '            return {"cache_control": False}',
    )

    violations = check_parity(load_catalog(CATALOG_PATH), root)

    matches = [v for v in violations if v.surface == "cache.bodies" and "anthropic" in v.detail]
    assert len(matches) == 1
    assert "cache_control" in matches[0].detail
    assert "True" in matches[0].detail
    assert "False" in matches[0].detail


def test_unknown_mem0_key_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        MEM0,
        '"ollama": "llama3.2:3b",',
        '"ollamax": "llama3.2:3b",',
    )

    violations = check_parity(load_catalog(CATALOG_PATH), root)

    assert any(
        violation.surface == "mem0.keys" and "ollamax" in violation.detail
        for violation in violations
    )


def test_empty_mem0_map_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        MEM0,
        '    "anthropic": "claude-haiku-4-20250414",\n'
        '    "openai": "gpt-4.1-nano",\n'
        '    "ollama": "llama3.2:3b",\n'
        '    "zai": "glm-4-flash",\n',
        "",
    )

    violations = check_parity(load_catalog(CATALOG_PATH), root)

    assert any(
        violation.surface == "mem0.keys" and "empty" in violation.detail for violation in violations
    )


def test_provider_without_prefix_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        REGISTRY,
        '    ("ollama/", "ollama"),\n',
        '    ("ollama/", "ollama_local"),\n',
    )
    _mutate(
        root,
        REGISTRY,
        '    ("llama", "ollama"),\n',
        '    ("llama", "ollama_local"),\n',
    )

    violations = check_parity(load_catalog(CATALOG_PATH), root)

    assert any(
        violation.surface == "prefixes.cover" and "ollama" in violation.detail
        for violation in violations
    )
