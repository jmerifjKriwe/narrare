"""Multilingual patterns for PROMPT-QUALITY content checks.

Extracted from ``prompts.py`` to keep the checker under RULE-04's
200-line limit.  All patterns match what is actually used in the
bundled prompts (EN/DE/FR).
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Role assignment patterns
# ---------------------------------------------------------------------------

ROLE_PATTERNS: tuple[str, ...] = (
    # English
    "you are",
    "your role",
    "your job is",
    "your task is",
    # German
    "du bist",
    "deine aufgabe",
    "deine rolle",
    # French
    "tu es",
    "ton rôle",
    "votre rôle",
)


def has_second_person_role_sentence(content: str) -> bool:
    """Check for second-person role-defining sentences (German/French).

    Lines starting with ``Du `` or ``Tu `` that exceed 20 chars define
    the AI's role by behaviour rather than identity — e.g.
    "Du führst eine Tiefenanalyse…" / "Tu fournis une analyse…".
    """
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("{{"):
            continue
        if stripped.startswith("Du ") and len(stripped) > 20:
            return True
        if stripped.startswith("Tu ") and len(stripped) > 20:
            return True
    return False


# ---------------------------------------------------------------------------
# Output format patterns
# ---------------------------------------------------------------------------

OUTPUT_FORMAT_PATTERNS: tuple[str, ...] = (
    # English
    "output format",
    "json object",
    "return a json",
    "return a structured",
    "only output",
    "output only",
    "provide the complete",
    "respond with a structured",
    # German
    "ausgabeformat",
    "json-objekt",
    "gib ein json",
    "gib ein strukturiertes",
    "antworte mit einem strukturierten",
    "nur ausgabe",
    # French
    "format de sortie",
    "objet json",
    "renvoie un objet json",
    "réponds avec un",
    "retourne un objet json",
)


# ---------------------------------------------------------------------------
# Do-NOT / NICHT / Ne…PAS counting
# ---------------------------------------------------------------------------


def count_do_not_rules(content: str, content_lower: str) -> int:
    """Count imperative negative rules across EN/DE/FR.

    Recognises:
    - English: ``do not``
    - German: uppercase ``NICHT`` (imperative, not prose "nicht")
    - French: ``n'…pas``, ``ne … pas``, ``ne jamais``
    - Imperative: ``avoid`` / ``vermeide`` at line start
    """
    count = 0

    # English "do not"
    count += content_lower.count("do not")

    # German NICHT (uppercase = imperative rule)
    for line in content.splitlines():
        if "NICHT" in line:
            count += line.count("NICHT")

    # French N'…PAS / Ne…PAS / Ne jamais
    count += len(re.findall(r"n'\w+\s+pas", content_lower))
    count += len(re.findall(r"ne\s+\w+\s+pas", content_lower))
    count += content_lower.count("ne jamais")

    # Imperative "avoid" / "vermeide" at line start (after optional list marker)
    for line in content.splitlines():
        stripped_l = line.strip().lower()
        # Strip leading list marker ("- ", "* ", "1. ")
        if stripped_l.startswith(("- ", "* ")) or (
            len(stripped_l) > 2 and stripped_l[0].isdigit() and stripped_l[1] == "."
        ):
            stripped_l = stripped_l[2:].lstrip()
        if stripped_l.startswith("avoid ") or stripped_l.startswith("vermeide "):
            count += 1

    return count
