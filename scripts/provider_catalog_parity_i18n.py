"""Resolve catalog ``label_key`` values against the i18n message files (RULE-16).

This is the i18n half of ``scripts/provider_catalog_parity.py``, extracted for
the RULE-04 ``scripts/`` size limit. :func:`check_labels` returns
``(surface, detail)`` pairs; the parity module wraps them in its own
``ParityViolation``, so this module never imports back into the parity gate at
run time.

Every catalog label is a translatable ``<file>.<path>`` key and must resolve in
every supported locale. A missing file, invalid JSON and a leaf that is not a
non-empty string are all reported, never treated as a pass.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from scripts.generate_provider_catalog import ProviderSpec

_I18N_DIR = Path("packages/i18n/messages")
"""Where the message-file trees live; the file stem is the key's first segment."""

_LOCALES: tuple[str, ...] = ("en", "de", "fr")
"""Every locale a catalog ``label_key`` must resolve in (RULE-16)."""

LABELS_SURFACE = "labels.locales"
"""The parity surface every violation from this module belongs to."""


def _load_messages(path: Path) -> tuple[dict[str, object] | None, str]:
    """Parse a message file; the reason is ``""`` when it parsed.

    A missing file, a decode error and a non-object document each come back as a
    reason, never as an empty-but-valid mapping: the caller turns every reason
    into a violation.
    """
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        return None, f"cannot be read ({error.strerror or error})"
    except ValueError as error:
        return None, f"is not valid UTF-8 JSON ({error})"
    if not isinstance(raw, dict):
        return None, "is not a JSON object"
    return cast("dict[str, object]", raw), ""


def _contains(messages: dict[str, object], path: list[str]) -> bool:
    """Whether the nested ``path`` holds a non-empty string in a message file.

    Only the segments before the last must be mappings. The leaf must be a
    **non-empty string**: these are translatable labels (RULE-16), so a
    ``null``, an object, a number, a boolean or ``""`` does not resolve. Each
    step re-checks the runtime shape and hands the walk on through an
    ``object``, so a non-mapping document cannot be mistaken for a hit.
    """
    node: object = messages
    for part in path:
        if not isinstance(node, dict):
            return False
        child: object = dict(node).get(part)
        if child is None:
            return False
        node = child
    return isinstance(node, str) and bool(node)


def check_labels(specs: list[ProviderSpec], repo_root: Path) -> list[tuple[str, str]]:
    """Every catalog ``label_key`` resolves in every locale (RULE-16)."""
    violations: list[tuple[str, str]] = []
    loaded: dict[Path, tuple[dict[str, object] | None, str]] = {}
    for spec in specs:
        stem, separator, nested = spec.label_key.partition(".")
        if not stem or not separator or not nested:
            violations.append(
                (
                    LABELS_SURFACE,
                    f"{spec.id}: label_key {spec.label_key} is not a <file>.<path> key",
                )
            )
            continue
        for locale in _LOCALES:
            relative = _I18N_DIR / locale / f"{stem}.json"
            if relative not in loaded:
                loaded[relative] = _load_messages(repo_root / relative)
            messages, reason = loaded[relative]
            if messages is None:
                violations.append((LABELS_SURFACE, f"{spec.id}: {relative} {reason}"))
            elif not _contains(messages, nested.split(".")):
                violations.append(
                    (LABELS_SURFACE, f"{spec.id}: {spec.label_key} missing in {relative}")
                )
    return violations
