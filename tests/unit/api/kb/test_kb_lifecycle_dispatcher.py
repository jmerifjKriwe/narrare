"""Unit tests for KBLifecycleDispatcher — the KB write-side observer hook.

The dispatcher is the thin collaborator KBService calls on
rename/deprecate/delete. It owns the observer list and the RULE-11
per-observer isolation: one failing consumer must not block the others
or roll back the KB operation (ADR-050 Option B rationale).
"""

from __future__ import annotations

from uuid import uuid4

from narrare.kb.lifecycle_dispatcher import KBLifecycleDispatcher
from narrare_core.context.integration_contracts import KBEntityLifecycleObserver


class _FakeObserver:
    """Records every notification it receives."""

    def __init__(self, name: str = "fake") -> None:
        self.consumer_feature = name
        self.renamed: list[tuple[str, str, str, str]] = []
        self.deprecated: list[tuple[str, str]] = []
        self.deleted: list[tuple[str, str]] = []

    async def on_kb_entity_renamed(self, *, novel_id, entity_id, old_name, new_name) -> None:
        self.renamed.append((str(novel_id), str(entity_id), old_name, new_name))

    async def on_kb_entity_deprecated(self, *, novel_id, entity_id) -> None:
        self.deprecated.append((str(novel_id), str(entity_id)))

    async def on_kb_entity_deleted(self, *, novel_id, entity_id) -> None:
        self.deleted.append((str(novel_id), str(entity_id)))


class _FailingObserver:
    """Always raises — used to verify RULE-11 isolation."""

    consumer_feature = "failing"

    async def on_kb_entity_renamed(self, **kwargs) -> None:
        raise RuntimeError("boom-renamed")

    async def on_kb_entity_deprecated(self, **kwargs) -> None:
        raise RuntimeError("boom-deprecated")

    async def on_kb_entity_deleted(self, **kwargs) -> None:
        raise RuntimeError("boom-deleted")


class TestNotifyRenamed:
    async def test_notifies_all_observers_with_typed_args(self) -> None:
        a, b = _FakeObserver("a"), _FakeObserver("b")
        dispatcher = KBLifecycleDispatcher(observers=[a, b])

        novel_id, entity_id = uuid4(), uuid4()
        await dispatcher.notify_renamed(
            novel_id=novel_id,
            entity_id=entity_id,
            old_name="John",
            new_name="Jonathan",
        )

        assert a.renamed == [(str(novel_id), str(entity_id), "John", "Jonathan")]
        assert b.renamed == [(str(novel_id), str(entity_id), "John", "Jonathan")]

    async def test_one_failing_observer_does_not_block_others(self) -> None:
        failing = _FailingObserver()
        ok = _FakeObserver("ok")
        dispatcher = KBLifecycleDispatcher(observers=[failing, ok])

        # Must not raise — the failure is logged, not propagated.
        await dispatcher.notify_renamed(
            novel_id=uuid4(),
            entity_id=uuid4(),
            old_name="x",
            new_name="y",
        )

        assert len(ok.renamed) == 1

    async def test_empty_observer_list_is_noop(self) -> None:
        dispatcher = KBLifecycleDispatcher(observers=[])
        await dispatcher.notify_renamed(
            novel_id=uuid4(), entity_id=uuid4(), old_name="a", new_name="b"
        )


class TestNotifyDeprecated:
    async def test_notifies_all_observers(self) -> None:
        a, b = _FakeObserver("a"), _FakeObserver("b")
        dispatcher = KBLifecycleDispatcher(observers=[a, b])

        novel_id, entity_id = uuid4(), uuid4()
        await dispatcher.notify_deprecated(novel_id=novel_id, entity_id=entity_id)

        assert a.deprecated == [(str(novel_id), str(entity_id))]
        assert b.deprecated == [(str(novel_id), str(entity_id))]

    async def test_failing_observer_isolated(self) -> None:
        ok = _FakeObserver("ok")
        dispatcher = KBLifecycleDispatcher(observers=[_FailingObserver(), ok])
        await dispatcher.notify_deprecated(novel_id=uuid4(), entity_id=uuid4())
        assert len(ok.deprecated) == 1


class TestNotifyDeleted:
    async def test_notifies_all_observers(self) -> None:
        a = _FakeObserver("a")
        dispatcher = KBLifecycleDispatcher(observers=[a])

        novel_id, entity_id = uuid4(), uuid4()
        await dispatcher.notify_deleted(novel_id=novel_id, entity_id=entity_id)

        assert a.deleted == [(str(novel_id), str(entity_id))]

    async def test_failing_observer_isolated(self) -> None:
        ok = _FakeObserver("ok")
        dispatcher = KBLifecycleDispatcher(observers=[_FailingObserver(), ok])
        await dispatcher.notify_deleted(novel_id=uuid4(), entity_id=uuid4())
        assert len(ok.deleted) == 1


class TestProtocolCompliance:
    def test_observers_satisfy_core_protocol(self) -> None:
        # The Core Protocol is runtime_checkable — our fakes must match,
        # proving the dispatcher works against the contract, not concrete types.
        assert isinstance(_FakeObserver(), KBEntityLifecycleObserver)
