"""KBAgent — stellt KB-Tools für andere Agents bereit.

Wird nicht selbst ausgeführt, sondern stellt nur Tools zur Verfügung,
die von anderen Agents (z.B. DraftAgent) genutzt werden können.
Alle Tools sind deferred-loaded (defer_loading=True) — sie werden
erst vom Modell entdeckt, wenn es via ToolSearch danach sucht.

Usage:
    kb_agent = KBAgent(model=model)
    # Tools via Toolset-Capability in anderen Agents einbinden
    capabilities.append(Toolset(kb_agent.get_toolset()))

Siehe ADR-015 Phase 3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import RunContext  # noqa: TC002 — needed at runtime by pydantic_ai internals
from pydantic_ai.tools import Tool
from pydantic_ai.toolsets import FunctionToolset

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.kb_formatters import (
    format_entity,
    format_entries,
    format_related,
)

if TYPE_CHECKING:
    from pydantic_ai.models import Model

    from narrare_core.kb.query_service import KBQueryService


class KBDeps:
    """Dependencies for KBAgent tools.

    Attributes:
        kb_service: Optional KB query service conforming to KBQueryService.
            When None, tools return fallback messages.
    """

    def __init__(self, kb_service: KBQueryService | None = None) -> None:
        self.kb_service = kb_service


class KBAgent(NarrareAgent[KBDeps, None]):
    """Agent, der KB-Tools für andere Agents bereitstellt.

    Alle Tools sind deferred-loaded — sie werden erst vom Modell
    entdeckt, wenn es via ToolSearch danach sucht.

    KBAgent wird nie selbst ausgeführt (output_type=None). Er dient
    ausschliesslich als Tool-Provider für andere Agents.
    """

    def __init__(self, model: Model) -> None:
        super().__init__(
            model=model,
            deps_type=KBDeps,
            output_type=None,
            system_prompt="",  # No system prompt — just provides tools
        )

        # FunctionToolset mit deferred-loaded KB-Tools
        self._toolset = FunctionToolset(
            [
                Tool(self.search_kb, takes_ctx=True, defer_loading=True),
                Tool(self.get_entity, takes_ctx=True, defer_loading=True),
                Tool(
                    self.get_related_entities,
                    takes_ctx=True,
                    defer_loading=True,
                ),
            ],
            defer_loading=True,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_toolset(self) -> FunctionToolset[KBDeps]:
        """Return the FunctionToolset for integration in other agents.

        Usage:
            capabilities.append(Toolset(kb_agent.get_toolset()))
        """
        return self._toolset

    # ------------------------------------------------------------------
    # KB Tools
    # ------------------------------------------------------------------

    async def search_kb(
        self,
        ctx: RunContext[KBDeps],
        query: str,
        entity_type: str | None = None,
    ) -> str:
        """Search the knowledge base for entries matching the query.

        Args:
            ctx: Run context.
            query: The search query string.
            entity_type: Optional filter — 'character', 'location', 'faction',
                'object', 'system', 'timeline', 'concept', or 'setting'.

        Returns:
            Formatted string of matching entries, or a message if none found.
        """
        kb_service = ctx.deps.kb_service
        if kb_service is not None:
            try:
                entries = await kb_service.search(query, entity_type=entity_type)
                if entries:
                    return format_entries(entries)
            except Exception as e:
                return f"KB search failed: {e}"
        return "KB search is not available. No KB service configured."

    async def get_entity(
        self,
        ctx: RunContext[KBDeps],
        name: str,
    ) -> str:
        """Get detailed information about a knowledge base entity by name.

        Args:
            ctx: Run context.
            name: The full name of the entity (e.g. 'Anna Mueller').

        Returns:
            Formatted entity details, or a message if not found.
        """
        kb_service = ctx.deps.kb_service
        if kb_service is not None:
            try:
                entity = await kb_service.get_by_name(name)
                if entity:
                    return format_entity(entity)
            except Exception as e:
                return f"KB lookup failed: {e}"
        return f"Entity '{name}' not found. KB service is not available."

    async def get_related_entities(
        self,
        ctx: RunContext[KBDeps],
        entity_name: str,
        relation_type: str | None = None,
    ) -> str:
        """Find entities related to a given entity.

        Args:
            ctx: Run context.
            entity_name: The name of the source entity.
            relation_type: Optional filter — e.g. 'ally', 'lives_in', 'member_of'.

        Returns:
            Formatted list of related entities, or a message if none found.
        """
        kb_service = ctx.deps.kb_service
        if kb_service is not None:
            try:
                entity = await kb_service.get_by_name(entity_name)
                if entity:
                    entity_id = getattr(entity, "id", None)
                    if entity_id:
                        relations = await kb_service.get_related(
                            entity_id, relation_type=relation_type
                        )
                        if relations:
                            return format_related(entity_name, relations)
            except Exception as e:
                return f"KB relationship lookup failed: {e}"
        return f"No related entities found for '{entity_name}'."

    # ------------------------------------------------------------------
    # Format helpers (delegiert an kb_formatters)
    # ------------------------------------------------------------------
