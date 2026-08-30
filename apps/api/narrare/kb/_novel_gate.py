"""Thin re-export of the canonical novel-ownership gate for the KB domain.

Historical note (IDOR remediation S9): this module held the KB read
services' ownership gate. Batch-review follow-up W3 (2026-08-29)
consolidated the five gate variants into the canonical home
``narrare.novels.ownership`` — the novels domain owns Novel ownership
semantics. This alias keeps the six KB services' import sites (and
their S9/S10 lineage) stable; the semantics documentation moved with
the implementation.
"""

from __future__ import annotations

from narrare.novels.ownership import verify_novel_owned

__all__ = ["verify_novel_owned"]
