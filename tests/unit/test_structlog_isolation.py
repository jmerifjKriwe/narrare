"""Unit tests for ``tests/_structlog_isolation`` — the class-root anti-flake fixture.

Covers the three load-bearing contracts of the isolator:

1. snapshot isolation (processors list is copied, not referenced),
2. drift detection (capture_logs round-trips are NOT drift; configure is),
3. the unpin sweep (module-level and class-attribute lazy proxies pinned via
   ``cache_logger_on_first_use=True`` get their instance ``bind`` shadow
   removed),
4. the fixture generator end-to-end: a leaked polluter configuration and
   root-logger mutation are restored on teardown — encoded as the
   order-independent regression for the systemic cross-test chain
   (polluter → proxy pinning → second configure → capture_logs victim).
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

import structlog
from structlog.testing import capture_logs

from tests._structlog_isolation import (
    _isolate_structlog_config_impl,
    _snapshot_structlog,
    _structlog_drifts,
    _unpin_cached_lazy_proxies,
)

# Module-level proxies so the sys.modules sweep in _unpin_cached_lazy_proxies
# can reach them exactly like production module loggers.
module_proxy = structlog.get_logger("test_structlog_isolation_module_proxy")


class _ProxyHolder:
    """Class-attribute proxy holder — the sweep's second scan level."""

    class_proxy = structlog.get_logger("test_structlog_isolation_class_proxy")


def _pollute_like_configure_logging() -> None:
    """Apply the exact call shape of ``configure_logging()`` (the polluter)."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def _drive_fixture_teardown(generator: Any) -> None:
    """Advance the fixture generator to teardown.

    Suppressing StopIteration is the generator protocol's expected exhaustion
    signal, not a swallowed error — teardown exceptions propagate unchanged.
    """
    with contextlib.suppress(StopIteration):
        next(generator)


# ---------------------------------------------------------------------------
# Snapshot + drift detection
# ---------------------------------------------------------------------------


def test_snapshot_structlog_copies_processors_list() -> None:
    """Snapshot holds a copy: a later configure cannot corrupt it."""
    snapshot = _snapshot_structlog()
    original_content = list(snapshot["processors"])

    structlog.configure(processors=[structlog.stdlib.add_log_level])

    assert snapshot["processors"] == original_content


def test_structlog_drifts_after_capture_logs_roundtrip_returns_false() -> None:
    """capture_logs mutates the current list in place and restores it — no drift."""
    snapshot = _snapshot_structlog()

    with capture_logs():
        pass

    assert _structlog_drifts(snapshot) is False


def test_structlog_drifts_after_configure_returns_true() -> None:
    """A configure that changes config content is detected as drift."""
    snapshot = _snapshot_structlog()
    assert _structlog_drifts(snapshot) is False

    _pollute_like_configure_logging()

    assert _structlog_drifts(snapshot) is True


# ---------------------------------------------------------------------------
# Unpin sweep
# ---------------------------------------------------------------------------


def test_unpin_sweep_unpins_module_level_proxy_after_cache_pinning() -> None:
    """A proxy pinned while cache=True loses its instance ``bind`` shadow."""
    _pollute_like_configure_logging()
    module_proxy.info("pinning_use")
    assert "bind" in vars(module_proxy), "proxy should be pinned under cache=True"

    _unpin_cached_lazy_proxies()

    assert "bind" not in vars(module_proxy)


def test_unpin_sweep_unpins_class_attribute_proxy_after_cache_pinning() -> None:
    """Proxies stored as class attributes are unpinned as well."""
    _pollute_like_configure_logging()
    _ProxyHolder.class_proxy.info("pinning_use")
    assert "bind" in vars(_ProxyHolder.class_proxy)

    _unpin_cached_lazy_proxies()

    assert "bind" not in vars(_ProxyHolder.class_proxy)


# ---------------------------------------------------------------------------
# Fixture generator end-to-end
# ---------------------------------------------------------------------------


def test_fixture_teardown_restores_leaked_structlog_config_and_unpins() -> None:
    """Polluter-style leak inside the fixture window is fully reverted."""
    snapshot_before = _snapshot_structlog()
    generator = _isolate_structlog_config_impl()
    next(generator)

    _pollute_like_configure_logging()
    module_proxy.info("pinning_use")

    _drive_fixture_teardown(generator)

    assert _structlog_drifts(snapshot_before) is False
    assert "bind" not in vars(module_proxy)


def test_fixture_teardown_restores_root_logger_handlers_and_level() -> None:
    """Leaked root-logger handlers/level (configure_logging side effect) revert."""
    root = logging.getLogger()
    level_before = root.level
    leaked = logging.StreamHandler()
    generator = _isolate_structlog_config_impl()
    next(generator)

    root.addHandler(leaked)
    root.setLevel(logging.DEBUG)

    _drive_fixture_teardown(generator)

    assert leaked not in root.handlers
    assert root.level == level_before


def test_cross_test_chain_regression_polluter_then_capture_logs_victim() -> None:
    """Order-independent encoding of the systemic flake chain.

    Simulates two consecutive tests via the fixture generator protocol:
    test A leaks configure_logging-shaped state and pins the module proxy;
    test B (running AFTER A's teardown) must still capture the proxy's
    events via capture_logs — the exact assertion class that flaked.
    """
    # --- test A: polluter ---
    generator = _isolate_structlog_config_impl()
    next(generator)
    _pollute_like_configure_logging()
    module_proxy.info("polluter_window_event")  # pins under cache=True
    _drive_fixture_teardown(generator)

    # --- test B: capture_logs victim ---
    with capture_logs() as logs:
        module_proxy.info("victim_event")

    assert any(entry["event"] == "victim_event" for entry in logs), (
        f"capture_logs missed the event after a polluting test — captured {logs!r}"
    )
