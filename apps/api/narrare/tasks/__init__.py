"""Background task dispatch package.

Per ADR-080 the TaskIQ broker, the worker process, and the broker-registered
task stubs have been removed. Background work now runs in-process:

- Embedding generation — ``narrare.embeddings.tasks`` (dispatched by
  ``narrare.kb.embedding_hooks`` via ``asyncio.create_task``).
- Band-summary generation — ``narrare.series.tasks`` (dispatched by
  ``SeriesService`` via ``asyncio.create_task``).
- Wiki summary generation — ``narrare.wiki.tasks`` (invoked directly by
  ``narrare.wiki.listeners``).
- Feedback / preference memory (mem0) — removed (Phase-7 stubs, never wired).

This package is retained for import-path stability; it no longer owns a
shared broker.
"""

from __future__ import annotations
