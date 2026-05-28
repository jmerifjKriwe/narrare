"""Analysis services — business logic orchestration.

Each service orchestrates a specific analysis feature:
- ``ChapterSentimentService`` — ANAL-002 sentiment analysis
"""

from __future__ import annotations

from narrare.analysis.services.sentiment_service import ChapterSentimentService

__all__ = [
    "ChapterSentimentService",
]
