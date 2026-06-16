"""JSON-response parsing for name generation.

Pure helper that converts an LLM JSON response into
:class:`~narrare.generation.schemas.GeneratedName` objects. Handles markdown
code fences, arrays, ``{"names": [...]}`` objects, and graceful degradation
on invalid JSON (returns an empty list, logged).

This module has one responsibility (RULE-06): parse generated-name responses.
Prompt building, deduplication, and registry invocation stay in
:mod:`narrare.generation.name_service`.

See:
    CONSTRAINTS.md RULE-06/RULE-11.
"""

from __future__ import annotations

import json
from typing import Any, cast

import structlog

from narrare.generation.schemas import GeneratedName, NameGenerateRequest

logger = structlog.get_logger(__name__)


def parse_generated_names(
    text: str,
    request: NameGenerateRequest,
) -> list[GeneratedName]:
    """Parse an LLM JSON response into GeneratedName objects.

    Args:
        text: Raw LLM response text.
        request: Original request for type/name_style metadata.

    Returns:
        List of GeneratedName objects. Empty when the response is not valid
        JSON or contains no parseable name items (logged at WARNING).
    """
    # Strip markdown code fences if present (```json ... ```)
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
        cleaned = cleaned[first_newline + 1 :]
        # Remove closing fence (```)
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        raw: Any = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning(
            "name_parse_failed_json",
            text_length=len(text),
            text_preview=text[:200],
        )
        return []

    # Collect raw items as fully typed dicts.
    # isinstance() on ``Any`` narrows to ``list[Unknown]`` / ``dict[str, Unknown]``,
    # so we use ``cast()`` to get properly typed containers.
    raw_items: list[dict[str, Any]] = []
    if isinstance(raw, list):
        raw_list: list[Any] = cast("list[Any]", raw)
        for item in raw_list:
            if isinstance(item, dict):
                raw_items.append(cast("dict[str, Any]", item))
    elif isinstance(raw, dict):
        raw_dict: dict[str, Any] = cast("dict[str, Any]", raw)
        names_key = raw_dict.get("names", [])
        if isinstance(names_key, list):
            names_list: list[Any] = cast("list[Any]", names_key)
            for item in names_list:
                if isinstance(item, dict):
                    raw_items.append(cast("dict[str, Any]", item))
        else:
            raw_items.append(raw_dict)
    # else: non-dict non-list JSON → empty result (no names to parse)

    names: list[GeneratedName] = []
    for item in raw_items:
        name_val: Any = item.get("name", "")
        pron_val: Any = item.get("pronunciation")
        mean_val: Any = item.get("meaning")
        names.append(
            GeneratedName(
                name=str(name_val) if name_val is not None else "",
                pronunciation=str(pron_val) if pron_val is not None else None,
                meaning=str(mean_val) if mean_val is not None else None,
                type=request.name_type.value,
                name_style=request.name_style,
            ),
        )
    return names
