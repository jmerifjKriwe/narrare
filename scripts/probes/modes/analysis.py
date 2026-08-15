"""Analysis-category mode definitions for invocation probes.

One tuple per mode: (feature_id, mode, intent, dynamic_inputs).
Split from mode_data.py for RULE-04 compliance (file-size limit).

RULE-06: One responsibility — analysis mode definitions only.
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent

#: Analysis modes with their required dynamic inputs.
ANALYSIS_MODES: list[tuple[str, str, LLMIntent, dict[str, str]]] = [
    (
        "analysis",
        "beta_reader",
        LLMIntent.BETA_READ,
        {
            "chapter_text": "The chapter needed work.",
        },
    ),
    (
        "analysis",
        "beta_reader_deepdive",
        LLMIntent.BETA_READ,
        {
            "chapter_text": "Deep dive analysis text.",
        },
    ),
    (
        "analysis",
        "review",
        LLMIntent.ANALYSE,
        {
            "chapter_text": "The chapter needed work.",
        },
    ),
    (
        "analysis",
        "preferences",
        LLMIntent.VOICE,
        {
            "chapter_text": "Voice analysis sample text.",
        },
    ),
    (
        "analysis",
        "character_voice",
        LLMIntent.VOICE,
        {
            "chapter_text": "Character voice analysis sample text.",
        },
    ),
    # ADR-057 D3 / WRITE-010: voice_check is the second VOICE context_mode
    # (a flag+score checker, distinct from the character_voice profiler). It
    # shares LLMIntent.VOICE; the runtime path resolves the governed
    # analysis/voice_check template via Mode 1 + CharacterVoiceCheckerAgent.
    (
        "analysis",
        "voice_check",
        LLMIntent.VOICE,
        {
            "chapter_text": "Voice check dialogue sample text.",
        },
    ),
    # ADR-073 D3 / ANAL-009: voice_drift is the third VOICE context_mode
    # (a longitudinal trend classifier, distinct from the character_voice
    # profiler and the voice_check checker). It shares LLMIntent.VOICE; the
    # runtime path resolves the governed analysis/voice_drift template via
    # Mode 1 + CharacterVoiceDriftAgent.
    (
        "analysis",
        "voice_drift",
        LLMIntent.VOICE,
        {
            "chapter_text": "Voice drift longitudinal sample text.",
        },
    ),
    # ADR-074 / ANAL-007: author_voice is the fourth VOICE context_mode
    # (an author-voice profiler, distinct from the character_voice profiler,
    # the voice_check checker, and the voice_drift classifier). It shares
    # LLMIntent.VOICE; the runtime path resolves the governed
    # analysis/author_voice template via Mode 1 + AuthorVoiceAgent.
    (
        "analysis",
        "author_voice",
        LLMIntent.VOICE,
        {
            "chapter_text": "Author voice profiling sample text.",
        },
    ),
    # ANAL-009 Phase 2B: author_voice_drift is the fifth VOICE context_mode
    # (a longitudinal narrator-voice trend classifier, distinct from the
    # character_voice profiler, the voice_check checker, the voice_drift
    # character classifier, and the author_voice profiler). It shares
    # LLMIntent.VOICE; the runtime path resolves the governed
    # analysis/author_voice_drift template via Mode 1 + AuthorVoiceDriftAgent.
    (
        "analysis",
        "author_voice_drift",
        LLMIntent.VOICE,
        {
            "chapter_text": "Author voice drift longitudinal sample text.",
        },
    ),
    (
        "analysis",
        "summarize",
        LLMIntent.SUMMARIZE,
        {
            "chapter_text": "Summary sample text.",
        },
    ),
    (
        "analysis",
        "remap",
        LLMIntent.ANALYSE,
        {
            "chapter_text": "Remap analysis text.",
        },
    ),
    (
        "analysis",
        "consistency",
        LLMIntent.CONSISTENCY,
        {
            "chapter_text": "Consistency check text.",
        },
    ),
    (
        "analysis",
        "fact_extraction",
        LLMIntent.FACT_EXTRACT,
        {
            "chapter_text": "Fact extraction sample text.",
        },
    ),
    (
        "analysis",
        "readability",
        LLMIntent.ANALYSE,
        {
            "chapter_text": "Readability analysis sample passage with complex sentence structures.",
        },
    ),
    (
        "analysis",
        "pov",
        LLMIntent.ANALYSE,
        {
            "chapter_text": "POV detection analysis sample passage.",
        },
    ),
    (
        "analysis",
        "coreference",
        LLMIntent.ANALYSE,
        {
            "chapter_text": "Coreference resolution sample passage with pronouns.",
        },
    ),
    # SERIES-002: band_summary is the series-band summarizer (BandSummaryAgent).
    # It shares LLMIntent.SUMMARIZE; the runtime path resolves the governed
    # analysis/band_summary template via Mode 1, with the numbered chapter
    # summaries flowing as user-channel runtime content.
    (
        "analysis",
        "band_summary",
        LLMIntent.SUMMARIZE,
        {
            "chapter_summaries": "1. The band discovered the hidden valley.",
        },
    ),
    # SERIES-004: series_consistency is the cross-novel canon-contradiction
    # detector (SeriesConsistencyAgent). It shares LLMIntent.ANALYSE; the
    # runtime path resolves the governed analysis/series_consistency template
    # via Mode 1, with Canon entries + chapter prose as user-channel content.
    (
        "analysis",
        "series_consistency",
        LLMIntent.ANALYSE,
        {
            "canon_entries": "[world-capital] Thornhaven — The capital of the realm.",
            "chapter_texts": "Chapter 1: The capital city gleamed.",
        },
    ),
]
