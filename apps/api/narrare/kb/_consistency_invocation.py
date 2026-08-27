"""ADR-048 Mode 2 invocation declaration for the KB consistency LLM phases.

Extracted from ``consistency_service.py`` (IDOR fix S9, RULE-04) — the
declaration is a static, self-contained evidence concern, distinct from
the orchestration logic. One responsibility (RULE-06): describe HOW the
consistency LLM phases compose their prompts so the invocation pipeline
can record evidence for them.
"""

from __future__ import annotations

from narrare_core.ai_invocation import ManualInjectionDeclaration

# KBConsistencyAnalyzer and WorldbuildingAnalyzer compose their prompts
# internally from deps (entity summaries, template structures, existing
# relationships). Evidence is recorded at the parent service layer,
# covering both Phase 2 (entry-internal) and Phase 3 (cross-entity) LLM
# calls.
CONSISTENCY_MANUAL_INJECTION = ManualInjectionDeclaration(
    reason=(
        "KBConsistencyAnalyzer and WorldbuildingAnalyzer compose their prompts "
        "internally from deps (entity summaries, template structures, "
        "existing relationships). See ADR-044 staged consistency pipeline."
    ),
    variables=("entity_summaries", "template_structures", "existing_relationships"),
    injection_mechanism="agent_deps",
)
