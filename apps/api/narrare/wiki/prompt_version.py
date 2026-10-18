"""Wiki generation prompt version — staleness-detection constant.

Stamped into every generated summary at persist time so per-novel
staleness marking can version-gate (``WikiRepository.mark_all_stale``
compares ``depends_on->>'wiki_prompt_version'`` against the caller's
current version). Chapters persist the same value as
``wiki_prompt_version`` (``ChapterWikiService``).

Bump when the wiki generation prompt changes semantically; the bump
makes existing summaries markable stale program-matically (the FE's
Mark-All-Stale sends no version, which marks everything whose stored
version differs).
"""

from __future__ import annotations

WIKI_PROMPT_VERSION = "1.0.0"
