"""Narrare Agents — erste-Klasse-Bürger für alle Narrare-Agents.

Siehe ADR-015 für die vollständige Modul-Architektur.
"""

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.draft_agent import DraftAgent, DraftDeps
from narrare_core.agents.draft_types import DraftConfig, DraftOutput
from narrare_core.agents.kb_agent import KBAgent, KBDeps

__all__ = [
    "DraftAgent",
    "DraftConfig",
    "DraftDeps",
    "DraftOutput",
    "KBAgent",
    "KBDeps",
    "NarrareAgent",
]
