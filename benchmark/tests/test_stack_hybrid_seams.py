"""Unit tests for the hybrid-mode seam implementations.

The real (non-fake) production seams: TCP-poll postgres readiness
(``wait_tcp``), point-in-time port probing (``tcp_accepts``), and
process-group termination (``terminate_process_group`` — the
already-exited branch; group signalling itself is OS glue exercised in
rehearsal). Split from ``test_stack_hybrid.py`` per RULE-04; these use
real localhost sockets, but NO docker and NO long waits.
"""

from __future__ import annotations

import socket

import pytest

from benchmark.stack import StackError, terminate_process_group
from benchmark.stack_hybrid import tcp_accepts, wait_tcp
from benchmark.tests.stack_hybrid_helpers import FakeProcess


class TestTcpHelpers:
    def test_wait_tcp_returns_once_a_listener_accepts(self) -> None:
        with socket.socket() as held:
            held.bind(("127.0.0.1", 0))
            held.listen(1)
            port = held.getsockname()[1]
            wait_tcp("127.0.0.1", port, timeout_s=2.0, interval_s=0.05)

    def test_wait_tcp_raises_at_deadline(self) -> None:
        with socket.socket() as held:
            held.bind(("127.0.0.1", 0))
            port = held.getsockname()[1]  # bound, NOT listening → connect refused
            with pytest.raises(StackError, match="postgres did not accept"):
                wait_tcp("127.0.0.1", port, timeout_s=0.2, interval_s=0.05)

    def test_tcp_accepts_mirrors_listener_presence(self) -> None:
        with socket.socket() as held:
            held.bind(("127.0.0.1", 0))
            port = held.getsockname()[1]
            assert tcp_accepts("127.0.0.1", port) is False
            held.listen(1)
            assert tcp_accepts("127.0.0.1", port) is True


class TestTerminateProcessGroup:
    def test_exited_process_is_left_alone(self) -> None:
        terminate_process_group(FakeProcess(4242, exit_code=0), grace_s=0.01)
