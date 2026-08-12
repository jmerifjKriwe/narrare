"""Manuscript export pipeline — Core contracts (IO-001 / ADR-081).

This package holds the pure-Narrare layer of the export pipeline: the
``ManuscriptNormalizer`` Protocol and the data shapes it produces. It is
**non-LLM** (no ``agents``/``prompts`` imports) and **Pure Core** (RULE-05:
no ``apps/`` imports, no I/O, no subprocess).

Contracts live in :mod:`narrare_core.export.contracts`. The concrete
normalizer is a later slice; this package ships only the contract for now.
"""
