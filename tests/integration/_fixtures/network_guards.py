"""Session-scoped network guards for the integration suite.

Both fixtures prevent the integration session from opening real external
connections (embedding API sockets, mem0/Qdrant clients). They are
``session``-scoped and ``autouse`` and are registered for the whole
integration tree by re-export from ``tests/integration/conftest.py``.

Keeping them in a dedicated module (and re-exporting the fixtures from the
integration conftest, rather than loading via ``pytest_plugins`` — which
pytest >= 8 hard-errors on in non-top-level conftests) keeps conftest.py
under the RULE-04 line limit while preserving BOTH:

1. ``autouse`` semantics — fixtures imported into a conftest apply
   automatically to its whole subtree, exactly like fixtures defined inline.
2. By-name fixture resolution — the mem0 guard is requested by name as
   ``_prewarm_composer(_no_real_mem0_clients: None)`` in
   ``tests/integration/writing/conftest.py`` to pin session-setup ordering
   (ADR-068 Decision 2). Re-exported fixtures remain requestable by name
   from every conftest/test in the subtree.

Both fixtures use ``pytest.MonkeyPatch()`` instantiated directly rather than
the function-scoped ``monkeypatch`` fixture, because they are session-scoped
and the ``monkeypatch`` fixture is function-scoped by design.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True, scope="session")
def _no_real_embedding_calls() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction] — autouse fixture, invoked via decorator reflection.
    """Prevent real embedding API calls during the integration session (testing-standards).

    ADR-080 moved KB embedding generation **in-process**: KB-entry
    create/update now dispatches ``run_embed_source_inprocess`` via
    ``asyncio.create_task`` inside the API process. Integration tests that
    create KB entries — directly or through the HTTP client — therefore
    trigger ``embed_texts`` in-process. Without this guard the call resolves
    to the real ``OpenAIEmbeddingProvider`` and opens an HTTPS socket to the
    embedding API; that socket leaks until ``gc.collect()`` in the
    ``gc_after_test`` fixture finalises it, surfacing as a
    ``ResourceWarning`` that ``filterwarnings=["error"]`` escalates to a test
    ERROR (the ADR-080 CI regression: a single teardown ERROR while all 781
    tests passed). Integration tests must not make real LLM/embedding calls
    (``docs/development/testing-standards.md`` — "real DB + mocked LLM").

    This seam patches every app-level ``embed_texts`` import site —
    ``narrare.embeddings.tasks`` (the ADR-080 in-process hook) and
    ``narrare.embeddings.service`` (the on-demand EmbeddingService used by the
    admin reprocess / search paths) — routing both through
    ``TestEmbeddingProvider``, the repo's network-free, deterministic provider
    (the same instance the ``NARRARE_E2E_TEST`` switch injects in E2E mode).
    Both sites must be patched because ``from narrare_core.llm.embeddings
    import embed_texts`` binds the name in each importing module's namespace,
    so patching the canonical source alone would not intercept already-bound
    references. The embedding path still runs end-to-end (content hash →
    upsert) but with stable dummy vectors and no network.

    SESSION-SCOPED (not function-scoped ``monkeypatch``): the embedding hook
    dispatches fire-and-forget via ``asyncio.create_task``. A task dispatched
    near the end of one test could reach ``embed_texts`` only after a
    function-scoped patch had been undone — leaking a real socket in the gap.
    Session scope closes that window for the whole integration run. Uses
    ``pytest.MonkeyPatch()`` directly (the ``monkeypatch`` fixture is
    function-scoped by design) — the same pattern as the
    ``_no_real_mem0_clients`` guard below.
    """
    from narrare_core.llm.embedding_providers import TestEmbeddingProvider

    _provider = TestEmbeddingProvider()

    async def _fake_embed_texts(
        texts: list[str],
        *,
        model: str | None = None,
        provider: str | None = None,  # kept for signature parity with embed_texts
    ) -> list[list[float]]:
        return await _provider.embed_texts(texts, model=model)

    mp = pytest.MonkeyPatch()
    # Every app-level import site of embed_texts (see docstring rationale).
    mp.setattr("narrare.embeddings.tasks.embed_texts", _fake_embed_texts)
    mp.setattr("narrare.embeddings.service.embed_texts", _fake_embed_texts)
    yield
    mp.undo()


@pytest.fixture(autouse=True, scope="session")
def _no_real_mem0_clients() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction] — autouse fixture, invoked via decorator reflection.
    """Prevent real mem0/QdrantClient creation during the integration session (RULE-20).

    SESSION-SCOPED (ADR-068 Decision 2): the integration suite has a
    session-scoped ``_prewarm_composer`` fixture (in
    ``tests/integration/writing/conftest.py``) that calls ``get_composer()``
    → ``_get_preference_service_instance()``. A function-scoped guard would
    activate only at the first test function, AFTER ``_prewarm_composer``
    has already run at session start — creating a real ``mem0.AsyncMemory``
    client once per integration session before any guard could prevent it.
    Session-scoping the guard ensures it runs before ``_prewarm_composer``;
    the explicit fixture dependency declared in
    ``_prewarm_composer(_no_real_mem0_clients: None)`` pins the ordering
    (autouse session fixtures otherwise have non-deterministic order).

    Uses ``pytest.MonkeyPatch()`` instantiated directly — the ``monkeypatch``
    fixture is function-scoped by design and cannot be used at session
    scope. Teardown via ``mp.undo()`` runs at session end.

    Integration counterpart of the unit-test guard in
    ``tests/unit/conftest.py`` (which stays function-scoped — unit tests
    do not use session-scoped prewarm fixtures). Patches the re-imported
    ``is_mem0_available`` reference in each mem0-backed singleton module
    so the singletons short-circuit before reaching
    ``create_memory_client_sync()``.

    Without this guard, mem0-backed singletons create real
    ``mem0.AsyncMemory`` clients (mem0 IS installed in the test env and
    ``tests/conftest.py`` sets dummy ``OPENAI_API_KEY`` /
    ``ANTHROPIC_API_KEY``). The clients' Qdrant/sqlite resources bind to
    the event loop active at creation time, then leak across loops under
    pytest-asyncio + pytest-xdist (each worker process has its own
    session loop; TestClient-based tests additionally use a portal-thread
    loop). At teardown this surfaces as
    ``RuntimeError: Task got Future attached to a different loop`` — the
    proximate cause of the PR #126 regression in
    ``test_session_stop_and_recovery.py``.

    Targets the same module set as the unit-test guard:
    - ``narrare._app.dependencies_prompts`` — preference-service singleton
    - ``narrare.kb._feedback_memory_deps`` — consistency-feedback singleton
    - ``narrare.writing._session_memory_deps`` — session-memory singleton
      (extracted from ``deps_writing.py`` per RULE-04; the singleton
      state and module-level availability imports move together)

    Integration tests that specifically exercise the mem0-available path
    override ``is_mem0_available`` via their own ``monkeypatch.setattr``
    (function-scoped — those overrides are tighter than this session
    guard and compose correctly because they patch the same module
    attribute after the session guard has).
    """
    mp = pytest.MonkeyPatch()
    mp.setattr(
        "narrare._app.dependencies_prompts.is_mem0_available",
        lambda: False,
    )
    mp.setattr(
        "narrare.kb._feedback_memory_deps.is_mem0_available",
        lambda: False,
    )
    mp.setattr(
        "narrare.writing._session_memory_deps.is_mem0_available",
        lambda: False,
    )
    yield
    mp.undo()
