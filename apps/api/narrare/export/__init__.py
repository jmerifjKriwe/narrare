"""Manuscript export pipeline — Backend API layer (IO-001 / ADR-081).

Home of the RULE-12 public API (``ExportService``), the job/options models, the
RULE-08 renderer adapter contract, the Typst-package config contract, and the
typed error hierarchy. This package is **non-LLM** (no ``agents``/``prompts``
imports) — export is a deterministic render pipeline (see the non-LLM call-out
in the IO-001 implementation plan and in :mod:`narrare_core.export.contracts`).

Contracts live in :mod:`narrare.export.contracts`; renderer adapter skeletons
live in :mod:`narrare.export.renderers`. Slices 0 ships contracts + boundary
skeletons only — no render logic yet.
"""
