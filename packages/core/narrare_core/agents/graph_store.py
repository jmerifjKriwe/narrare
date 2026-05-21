"""Graph State Store — Protocol für WritingGraph State-Persistence.

Speichert WritingState zu Checkpoints während der Graph-Ausführung.
Protocol in Core, Implementierung in apps/api/ (PostgreSQL).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class GraphStateStore(Protocol):
    """Store für WritingState-Persistence.

    Implementierungen speichern WritingState zu Checkpoint-Zeitpunkten,
    sodass Graph-Runs unterbrochen und fortgesetzt werden können.
    """

    async def save(self, run_id: str, state: object) -> None:
        """Save a checkpoint of the graph state.

        Args:
            run_id: Unique identifier for this graph run.
            state: The WritingState at this checkpoint.
        """

    async def load(self, run_id: str) -> object | None:
        """Load the latest checkpoint for a graph run.

        Args:
            run_id: The graph run identifier.

        Returns:
            The deserialized WritingState, or None if not found.
        """

    async def delete(self, run_id: str) -> None:
        """Delete all checkpoints for a graph run.

        Args:
            run_id: The graph run to clean up.
        """
