"""Tests for the ADR-086 prevention gate (factory-time model resolution).

ADR-086 Review Trigger #1 (J1 gate): ``await resolver.resolve(...)`` and
``await ....get_resolved_limits(...)`` must not run in DI-factory bodies of
``deps*.py`` / ``dependencies*.py`` / ``router*.py`` files under ``apps/api/``.
Sanctioned idiom: the call sits inside a nested closure whose enclosing
factory references ``LazyModelResolution`` (deferred first-use resolution).
Known sanctioned survivors live in the ratcheted baseline section
``adr086_factory_resolution`` (new entries = gate violation).
"""

from __future__ import annotations

import ast

from scripts.architecture._checkers.lazy_resolution import (
    RULE_ID,
    check_lazy_model_resolution,
)

DEPS_PATH = "apps/api/narrare/writing/deps_example.py"
ROUTER_PATH = "apps/api/narrare/writing/router_sessions.py"


def _parse(source: str) -> ast.AST:
    """Parse source code into an AST."""
    return ast.parse(source)


def _check(
    source: str,
    rel_path: str = DEPS_PATH,
    baseline_keys: frozenset[str] | None = None,
) -> list[str]:
    """Run the checker and return violation details (empty = pass)."""
    violations = check_lazy_model_resolution(
        rel_path,
        _parse(source),
        source.splitlines(),
        baseline_keys=baseline_keys,
    )
    return [v.detail for v in violations]


# =====================================================================
# Violations — eager resolution in factory bodies
# =====================================================================


class TestViolations:
    """Eager resolution in a provider body IS flagged (rule ADR-086)."""

    def test_eager_resolver_resolve_in_factory_body(self) -> None:
        """``await resolver.resolve(...)`` directly in the factory body → flagged."""
        source = """\
def get_example_service(session, user_id, novel_id):
    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(LLMIntent.SUMMARIZE, user_id, novel_id)
    return ExampleService(model_config=resolved.config)
"""
        details = _check(source)
        assert len(details) == 1
        assert RULE_ID in details[0] or "factory" in details[0]

    def test_eager_model_resolution_resolve_in_factory_body(self) -> None:
        """``await model_resolution.resolve(...)`` in the factory body → flagged.

        Guards the receiver-name matching: a LazyModelResolution wrapper
        must be awaited inside a sanctioned closure, never at wiring time.
        """
        source = """\
def get_example_service(session, user_id, novel_id):
    model_resolution = LazyModelResolution(lambda: resolver.resolve(LLMIntent.X, user_id, novel_id))
    resolved = await model_resolution.resolve()
    return ExampleService(model_config=resolved.config)
"""
        assert len(_check(source)) == 1

    def test_eager_get_resolved_limits_in_deps_factory_body(self) -> None:
        """``await ....get_resolved_limits(...)`` in a deps factory body → flagged."""
        source = """\
def get_example_service(session, user_id, project_id):
    limits = await token_limits_service.get_resolved_limits(
        user_id=user_id, project_id=project_id,
    )
    return ExampleService(limits=limits)
"""
        assert len(_check(source)) == 1

    def test_nested_closure_without_lazy_reference_flagged(self) -> None:
        """Nested closure WITHOUT a LazyModelResolution reference → flagged.

        This is the shape an unadjudicated deferred callback would hide
        behind (cf. the J1 adjudication of dependencies_adjudicator.py).
        """
        source = """\
def get_example_service(session):
    async def build_service(novel_id, user_id):
        resolved = await resolver.resolve(LLMIntent.KB_CONSISTENCY, user_id, novel_id)
        return ExampleService(model_config=resolved.config)
    return ExampleAdjudicator(factory=build_service)
"""
        assert len(_check(source)) == 1

    def test_router_file_eager_resolve_flagged(self) -> None:
        """``await resolver.resolve(...)`` in a router factory body → flagged."""
        source = """\
def _get_service(user_id, novel_id):
    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(LLMIntent.SUMMARIZE, user_id, novel_id)
    return ExampleService(model_config=resolved.config)
"""
        assert len(_check(source, rel_path=ROUTER_PATH)) == 1

    def test_baseline_key_suppresses_known_survivor_but_ratchets(self) -> None:
        """Baseline-listed key passes; a different unlisted function still flags."""
        source = """\
def resolve_accepted_residual(user_id, project_id):
    limits = await token_limits_service.get_resolved_limits(
        user_id=user_id, project_id=project_id,
    )
    return limits


def resolve_new_violation(user_id, project_id):
    limits = await token_limits_service.get_resolved_limits(
        user_id=user_id, project_id=project_id,
    )
    return limits
"""
        listed = _check(
            source,
            baseline_keys=frozenset({f"{DEPS_PATH}::resolve_accepted_residual"}),
        )
        assert len(listed) == 1
        assert "resolve_new_violation" in listed[0]

        unlisted = _check(source, baseline_keys=frozenset())
        assert len(unlisted) == 2


# =====================================================================
# Passing — sanctioned idioms and out-of-scope shapes
# =====================================================================


class TestPassing:
    """Sanctioned lazy idioms and out-of-scope code pass clean."""

    def test_lazy_closure_idiom_passes(self) -> None:
        """resolve + get_resolved_limits inside a LazyModelResolution closure → pass."""
        source = """\
def get_example_service(session, user_id, novel_id):
    resolver = get_model_routing_resolver(session)
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.SUMMARIZE, user_id, novel_id)
    )

    async def compose_runtime():
        resolved = await model_resolution.resolve()
        limits = await token_limits_service.get_resolved_limits(
            user_id=user_id, project_id=str(novel_id),
        )
        return ExampleRuntime(config=resolved.config, limits=limits)

    return ExampleService(compose_runtime=compose_runtime)
"""
        assert _check(source) == []

    def test_sync_lambda_call_passes(self) -> None:
        """The deferred ``lambda: resolver.resolve(...)`` idiom is NOT awaited → pass.

        Mutation guard: flagging plain (non-awaited) calls would break the
        sanctioned wiring idiom itself.
        """
        source = """\
def get_example_service(session, user_id, novel_id):
    resolver = get_model_routing_resolver(session)
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.SUMMARIZE, user_id, novel_id)
    )
    return ExampleService(model_resolution=model_resolution)
"""
        assert _check(source) == []

    def test_out_of_scope_file_not_scanned(self) -> None:
        """Eager resolve in a service file is service-layer, not factory wiring."""
        source = """\
async def run(self, user_id, novel_id):
    resolved = await resolver.resolve(LLMIntent.SUMMARIZE, user_id, novel_id)
    return resolved.config
"""
        assert _check(source, rel_path="apps/api/narrare/writing/example_service.py") == []

    def test_get_resolved_limits_in_router_is_service_delegation(self) -> None:
        """Routers delegating ``service.get_resolved_limits`` at request time → pass.

        The settings endpoint's product IS the resolved limits (ADR-086
        Implementation Notes) — delegation, not factory-time resolution.
        """
        source = """\
@router.get("/limits")
async def get_resolved_limits(user_id: str, service: TokenLimitsServiceDep) -> LimitsResponse:
    limits = await service.get_resolved_limits(user_id=user_id, project_id=None)
    return LimitsResponse.model_validate(limits)
"""
        assert _check(source, rel_path="apps/api/narrare/settings/token_limits/router.py") == []

    def test_unrelated_resolve_receiver_not_flagged(self) -> None:
        """Non-resolver receivers (e.g. ``path.resolve()`` lookalikes) → pass."""
        source = """\
def get_example_service(tmp_path):
    base = await tmp_path.resolve()
    return ExampleService(base=base)
"""
        assert _check(source) == []

    def test_baseline_default_section_contains_current_survivor(self) -> None:
        """The shipped baseline lists exactly the adjudicated survivor.

        ``ws_session_config.py`` deliberately sits outside the gate's
        basename scope (deps*/dependencies*/router*); its accepted
        bootstrap residual is documented in the ADR sweep note instead.
        """
        from scripts.architecture._checkers.lazy_resolution import (
            load_factory_resolution_baseline,
        )

        keys = load_factory_resolution_baseline()
        assert keys == frozenset(
            {
                "apps/api/narrare/kb/entity_resolution/dependencies_adjudicator.py::get_merge_adjudicator",
            }
        )

    def test_ws_session_config_out_of_basename_scope(self) -> None:
        """Non-deps-named factory files are outside the plan's gate scope.

        Scope follows the plan letter (deps*/dependencies*/router*); this
        pins that the WS handshake factory is not silently scanned, so its
        bootstrap residual needs no baseline key.
        """
        source = """\
def resolve_ws_session_config(user_id, project_id, chapter_id):
    limits = await token_limits_service.get_resolved_limits(
        user_id=user_id, project_id=project_id,
    )
    return limits
"""
        assert (
            _check(
                source,
                rel_path="apps/api/narrare/writing/ws_session_config.py",
            )
            == []
        )
