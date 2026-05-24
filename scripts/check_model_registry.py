#!/usr/bin/env python3
"""
Check model registry against models.dev reference data.

Extracts model IDs from the ``_providers/*.py`` registry files and
compares them against models.dev data (from cache or live API).
Warns about:

* New models on models.dev that are not yet registered in Narrare.
* Models still in the registry that are marked as deprecated on models.dev.

Usage:
    python scripts/check_model_registry.py

Exit codes:
    0: OK (or models.dev unreachable — graceful degradation)
    1: Missing or deprecated models found

See also:
    docs/features/NTH-03-model-registry-validation.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, cast

# ---------------------------------------------------------------------------
# Ensure project root is importable so we can import narrare_core
# ---------------------------------------------------------------------------

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Imports that depend on the project
# ---------------------------------------------------------------------------

from narrare_core.llm.cost_rates import get_cached_data, refresh_models  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT_DIR = Path(__file__).resolve().parent.parent
_PROVIDERS_DIR = _PROJECT_DIR / "packages" / "core" / "narrare_core" / "llm" / "_providers"

# ---------------------------------------------------------------------------
# Provider -> registry file mapping
# ---------------------------------------------------------------------------
# Keys are models.dev provider names, values are the basename of the
# _providers/*.py file that holds their model registrations.

REGISTRY_PROVIDERS: dict[str, str] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "others",  # Google models live in others.py
    "groq": "others",  # Groq models live in others.py
}

# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def _extract_ids_from_registry_file(text: str) -> dict[str, set[str]]:
    """Extract ``{provider_name: {model_id, ...}}`` from a provider file.

    Handles the common Narrare pattern::

        for _mid in [
            "gpt-4o",
            "gpt-4o-mini",
        ]:
            register_model(_mid, "openai")

    Returns an empty dict if no registration blocks are found.
    """
    result: dict[str, set[str]] = {}

    # Match: for VAR in [ "a", "b" ]:\n    register_model(VAR, "provider")
    pattern = (
        r"for\s+(\w+)\s+in\s+\["
        r"(.*?)"
        r"\]:\s*\n\s+register_model\(\s*\1\s*,\s*\"([^\"]+)\"\s*\)"
    )

    for match in re.finditer(pattern, text, re.DOTALL):
        provider = match.group(3)
        list_content = match.group(2)

        ids: set[str] = set()
        ids.update(re.findall(r'"([^"]+)"', list_content))
        ids.update(re.findall(r"'([^']+)'", list_content))

        result.setdefault(provider, set()).update(ids)

    return result


def extract_registry_model_ids() -> dict[str, set[str]]:
    """Extract all registered model IDs from ``_providers/*.py`` files.

    Returns:
        ``{provider_name: {model_id, ...}}`` for each known provider.
    """
    all_models: dict[str, set[str]] = {}

    for modelsdev_provider, filename in REGISTRY_PROVIDERS.items():
        filepath = _PROVIDERS_DIR / f"{filename}.py"
        if not filepath.exists():
            all_models[modelsdev_provider] = set()
            continue

        text = filepath.read_text(encoding="utf-8")
        extracted = _extract_ids_from_registry_file(text)

        # If the file has a block for this provider, use it; otherwise empty set
        all_models[modelsdev_provider] = extracted.get(modelsdev_provider, set())

    return all_models


# ---------------------------------------------------------------------------
# Loading models.dev data (via cache, with graceful degradation)
# ---------------------------------------------------------------------------


def load_modelsdev_data() -> dict[str, Any] | None:
    """Load models.dev data from cache or by force-refreshing.

    Graceful degradation::

        1. Try ``get_cached_data()`` (fast, no network).
        2. If ``None``, call ``refresh_models()`` (network call).
        3. If both fail, return ``None``.

    Returns:
        The raw models.dev JSON dict, or ``None`` if unavailable.
    """
    data = get_cached_data()
    if data is not None:
        return data

    # Cache miss or expired — force refresh
    print("  (i) Cache empty/expired — fetching models.dev ...")
    data = refresh_models()
    if data:
        return data

    return None


def _get_provider_data(
    raw: Any,
    provider: str,
) -> dict[str, Any] | None:
    """Safely extract a provider's data entry from raw models.dev JSON.

    models.dev structure::

        {
            "<provider>": {
                "models": {
                    "<model_id>": {"cost": {...}, "deprecated": bool},
                    ...
                }
            },
            ...
        }

    Args:
        raw: Raw models.dev JSON (should be a dict).
        provider: Provider name to extract (e.g. ``"openai"``).

    Returns:
        The ``models`` sub-dict for the provider, or ``None`` if missing.
    """
    if not isinstance(raw, dict):
        return None
    data: dict[str, Any] = cast("dict[str, Any]", raw)
    provider_entry = data.get(provider)
    if not isinstance(provider_entry, dict):
        return None
    provider_dict: dict[str, Any] = cast("dict[str, Any]", provider_entry)
    models = provider_dict.get("models")
    if isinstance(models, dict):
        return cast("dict[str, Any]", models)
    return None


def extract_modelsdev_model_ids(
    data: Any,
) -> dict[str, set[str]]:
    """Extract model IDs per provider from raw models.dev data.

    Args:
        data: Raw models.dev JSON (dict of provider entries).

    Returns:
        ``{provider_name: {model_id, ...}}``
    """
    result: dict[str, set[str]] = {}
    for provider in REGISTRY_PROVIDERS:
        models = _get_provider_data(data, provider)
        result[provider] = set(models.keys()) if models else set()
    return result


def extract_deprecated_modelsdev(
    data: Any,
) -> dict[str, set[str]]:
    """Extract deprecated model IDs per provider from models.dev data.

    Returns:
        ``{provider_name: {deprecated_model_id, ...}}``
    """
    result: dict[str, set[str]] = {}
    for provider in REGISTRY_PROVIDERS:
        models = _get_provider_data(data, provider)
        if models is None:
            continue
        deprecated: set[str] = set()
        for model_id, info in models.items():
            if not isinstance(info, dict):
                continue
            info_dict: dict[str, Any] = cast("dict[str, Any]", info)
            if info_dict.get("deprecated", False):
                deprecated.add(model_id)
        if deprecated:
            result[provider] = deprecated
    return result


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------


def compare(
    registry: dict[str, set[str]],
    modelsdev: dict[str, set[str]],
    deprecated: dict[str, set[str]],
) -> dict[str, list[str]]:
    """Compare registry against models.dev and produce warnings.

    Returns:
        ``{"missing": [...], "deprecated_in_registry": [...]}``
        containing formatted warning strings.
    """
    warnings: dict[str, list[str]] = {
        "missing": [],
        "deprecated_in_registry": [],
    }

    for provider in REGISTRY_PROVIDERS:
        registered = registry.get(provider, set())
        dev_models = modelsdev.get(provider, set())
        dep_models = deprecated.get(provider, set())

        # --- Models in models.dev but missing from our registry ---
        missing = dev_models - registered
        if missing:
            sorted_missing = sorted(missing)
            warnings["missing"].append(
                f"⚠️  MODELS.DEV: {len(sorted_missing)} neue {provider.title()}-Modelle "
                f"nicht in Registry: {', '.join(sorted_missing)}"
            )

        # --- Models in our registry that are deprecated on models.dev ---
        deprecated_in_registry = registered & dep_models
        if deprecated_in_registry:
            sorted_dep = sorted(deprecated_in_registry)
            warnings["deprecated_in_registry"].append(
                f"⚠️  MODELS.DEV: {len(sorted_dep)} deprecated Modell(e) "
                f"in Registry: {', '.join(sorted_dep)}"
            )

    return warnings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("\n  ── Model Registry Check ──\n")

    # 1. Extract model IDs from our registry files
    registry = extract_registry_model_ids()
    registry_total = sum(len(v) for v in registry.values())
    print(f"  📋 Registry: {registry_total} Modelle in {len(registry)} Providern")
    for prov, ids in sorted(registry.items()):
        if ids:
            print(f"     {prov}: {', '.join(sorted(ids))}")
    print()

    # 2. Load models.dev reference data (graceful degradation)
    data = load_modelsdev_data()
    if data is None:
        print(
            "  ⚠️  models.dev nicht erreichbar (weder Cache noch API). Überspringe Registry-Check.\n"
        )
        return 0

    modelsdev = extract_modelsdev_model_ids(data)
    modelsdev_total = sum(len(v) for v in modelsdev.values())
    print(f"  📡 models.dev: {modelsdev_total} Modelle in Referenz")
    for prov, ids in sorted(modelsdev.items()):
        print(f"     {prov}: {len(ids)} Modelle")
    print()

    # 3. Extract deprecated models
    deprecated = extract_deprecated_modelsdev(data)

    # 4. Compare
    warnings = compare(registry, modelsdev, deprecated)

    # 5. Report results
    all_warnings = warnings["missing"] + warnings["deprecated_in_registry"]

    if not all_warnings:
        print("  ✅ Modell-Registry ist aktuell (alle Modelle in models.dev registriert).\n")
        return 0

    print("  ── Warnungen ──\n")
    for warning in all_warnings:
        print(f"  {warning}")
    print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
