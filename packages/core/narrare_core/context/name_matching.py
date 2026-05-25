"""Entity name matching for proactive context.

Extracts which known entity names appear in chapter text using
case-insensitive word-boundary matching.
"""

from __future__ import annotations

import re


def match_entity_names(
    chapter_content: str,
    entity_names: list[str],
    *,
    min_name_length: int = 3,
) -> set[str]:
    """Find which entity names appear in the chapter text.

    Uses case-insensitive word-boundary regex matching. Names shorter
    than min_name_length are skipped to avoid false positives.

    Args:
        chapter_content: The chapter text to search.
        entity_names: Known entity names to look for.
        min_name_length: Minimum name length to consider (default 3).

    Returns:
        Set of entity names found in the text.
    """
    if not chapter_content or not entity_names:
        return set()

    found: set[str] = set()
    for name in entity_names:
        if len(name) < min_name_length:
            continue
        escaped = re.escape(name)
        # Use lookbehind/lookahead instead of \b to handle names
        # ending with non-word characters (e.g. "The Order (dark)")
        pattern = r"(?<!\w)" + escaped + r"(?!\w)"
        if re.search(pattern, chapter_content, re.IGNORECASE):
            found.add(name)
    return found
