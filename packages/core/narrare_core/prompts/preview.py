"""Provider-free prompt preview service (PROMPT-003).

The service resolves prompt content through the existing ``PromptComposer`` and
``PromptRegistry`` path, enriches the resolved result with variable metadata,
and converts prompt-resolution failures into typed preview diagnostics. It never
calls an LLM, instantiates an agent, or imports provider SDKs.
"""

from __future__ import annotations

from dataclasses import fields
from typing import TYPE_CHECKING

from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.contracts import ContextSnapshot, PromptPreviewProtocol
from narrare_core.prompts.preview_types import (
    PreviewDiagnostic,
    PreviewDiagnosticKind,
    PromptPreview,
    PromptVariableMetadata,
)
from narrare_core.prompts.route_table import (
    INTENT_TO_CATEGORY,
    INTENT_TO_MODE,
    ROUTE_CONFIGS,
)
from narrare_core.prompts.variable_engine import VariableInfo, extract_variables
from narrare_core.prompts.variable_metadata import get_variable_info
from narrare_core.prompts.variable_registry import get_variable_classification
from narrare_core.prompts.variable_taxonomy import (
    VariableClassification,
    VariableProvenance,
    VariableSecurity,
)
from narrare_core.shared.errors import (
    PromptNotFoundError,
    PromptRouteNotConfiguredError,
    PromptVariableError,
)

if TYPE_CHECKING:
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.prompts.registry import PromptRegistry, ResolvedPrompt
    from narrare_core.prompts.route_types import PromptRoute


class PromptPreviewService(PromptPreviewProtocol):
    """Resolve prompt previews without invoking any model provider.

    Args:
        composer: Existing prompt composer; performs cascade substitution.
        registry: Existing prompt registry; exposes the winning cascade source
            and unresolved template for metadata/provenance extraction.
    """

    def __init__(self, *, composer: PromptComposer, registry: PromptRegistry) -> None:
        self._composer = composer
        self._registry = registry

    async def preview(
        self,
        *,
        prompt_id: str,
        snapshot: ContextSnapshot,
        edited_override: str | None = None,
    ) -> PromptPreview:
        """Resolve a prompt preview without invoking any model provider."""
        category, language, mode = _parse_prompt_id(prompt_id)
        intent = _intent_for(category, mode)
        route = _route_for(intent, mode)
        context = _build_prompt_context(snapshot, mode)
        resolved = await self._resolve_prompt_template(
            category=category,
            language=language,
            mode=mode,
            genre=snapshot.genre,
            edited_override=edited_override,
        )
        template_vars = extract_variables(resolved.system_prompt)
        metadata = _build_variable_metadata(template_vars, route)

        try:
            composed = await self._composer.build(
                intent=intent,
                context=context,
                db_content=edited_override,
                user_prompt=snapshot.variables.get("user_prompt", ""),
            )
        except PromptVariableError as exc:
            diagnostics = _build_missing_variable_diagnostics(
                template_vars,
                route,
                provided=context.as_variables(),
                primary_missing=exc.variable,
            )
            return PromptPreview(
                system_prompt="",
                user_prompt="",
                first_message=resolved.first_message,
                cascade_source=resolved.source,
                variables=metadata,
                diagnostics=diagnostics,
            )

        diagnostics = _build_missing_variable_diagnostics(
            template_vars,
            route,
            provided=context.as_variables(),
            primary_missing=None,
        )
        return PromptPreview(
            system_prompt=composed.system,
            user_prompt=composed.user,
            first_message=composed.first_message,
            cascade_source=resolved.source,
            variables=metadata,
            diagnostics=diagnostics,
        )

    async def _resolve_prompt_template(
        self,
        *,
        category: str,
        language: str,
        mode: str,
        genre: str | None,
        edited_override: str | None,
    ) -> ResolvedPrompt:
        """Resolve the winning template through the prompt registry."""
        try:
            return await self._registry.resolve(
                category=category,
                language=language,
                mode=mode,
                genre=genre,
                db_content=edited_override,
            )
        except PromptNotFoundError:
            raise


def _parse_prompt_id(prompt_id: str) -> tuple[str, str, str]:
    """Parse ``category/language/mode`` while preserving slash-containing modes."""
    parts = prompt_id.split("/", 2)
    if len(parts) != 3 or not all(parts):
        raise PromptRouteNotConfiguredError(prompt_id, "Expected category/language/mode.")
    return parts[0], parts[1], parts[2]


def _intent_for(category: str, mode: str) -> LLMIntent:
    """Find the governed LLM intent for a preview prompt route."""
    for intent, configured_category in INTENT_TO_CATEGORY.items():
        config = ROUTE_CONFIGS.get(intent)
        if configured_category != category or config is None:
            continue
        if INTENT_TO_MODE.get(intent) == mode or mode in config.allowed_context_modes:
            return intent
    raise PromptRouteNotConfiguredError(
        f"{category}/{mode}",
        "No routeable LLMIntent matches this prompt id.",
    )


def _route_for(intent: LLMIntent, mode: str) -> PromptRoute:
    """Resolve the prompt route for metadata diagnostics."""
    from narrare_core.prompts.routes import resolve_prompt_route

    return resolve_prompt_route(intent, mode)


def _build_prompt_context(snapshot: ContextSnapshot, mode: str) -> PromptContext:
    """Build a PromptContext from adapter-supplied string variables."""
    prompt_fields = {field.name for field in fields(PromptContext)} - {"extra"}
    context = PromptContext(
        language=snapshot.language,
        genre=snapshot.genre or snapshot.variables.get("genre", ""),
        mode=snapshot.mode or mode,
        extra=dict(snapshot.variables),
    )
    for name, value in snapshot.variables.items():
        if name in prompt_fields and name not in {"language", "genre", "mode"}:
            setattr(context, name, value)
    return context


def _build_variable_metadata(
    variables: list[VariableInfo],
    route: PromptRoute,
) -> list[PromptVariableMetadata]:
    """Create provenance/security metadata for template variables."""
    return [_metadata_for_variable(variable.name, route) for variable in variables]


def _metadata_for_variable(name: str, route: PromptRoute) -> PromptVariableMetadata:
    """Create one variable metadata row with safe defaults for unknown variables."""
    info = get_variable_info(name)
    classification = get_variable_classification(name) or VariableClassification(
        name=name,
        provenance=VariableProvenance.FEATURE_DYNAMIC,
        security=VariableSecurity.SYSTEM_ONLY,
    )
    required = name in route.required_variables or (
        name not in route.optional_variables and (info.required if info else True)
    )
    return PromptVariableMetadata(
        name=name,
        description=info.description if info else "",
        variable_type=info.variable_type if info else "text",
        required=required,
        provenance=classification.provenance,
        security=classification.security,
    )


def _build_missing_variable_diagnostics(
    variables: list[VariableInfo],
    route: PromptRoute,
    provided: dict[str, str],
    primary_missing: str | None,
) -> list[PreviewDiagnostic]:
    """Build typed diagnostics for required variables that lack values."""
    names = {variable.name for variable in variables}
    if primary_missing:
        names.add(primary_missing)

    diagnostics: list[PreviewDiagnostic] = []
    for name in sorted(names):
        metadata = _metadata_for_variable(name, route)
        if metadata.required and not provided.get(name):
            diagnostics.append(
                PreviewDiagnostic(
                    kind=PreviewDiagnosticKind.MISSING_VARIABLE,
                    variable_name=name,
                    message=f"missing_required_variable:{name}",
                )
            )
    return diagnostics
