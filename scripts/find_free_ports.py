#!/usr/bin/env python3
"""Print two free TCP ports for parallel E2E runs.

Usage:
    eval "$(python3 scripts/find_free_ports.py)"
    just test-e2e scope=setup

The sockets are bound (and held open) for a short grace window so the ports
are still free when the services start binding them. Callers that see
EADDRINUSE should retry with a fresh invocation.
"""

from __future__ import annotations

import socket
import time


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


if __name__ == "__main__":
    api_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    web_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    api_sock.bind(("127.0.0.1", 0))
    web_sock.bind(("127.0.0.1", 0))
    api = int(api_sock.getsockname()[1])
    web = int(web_sock.getsockname()[1])
    # Hold the ports briefly so they are still free when the services bind.
    time.sleep(2)
    api_sock.close()
    web_sock.close()
    print(f"export NARRE_E2E_API_PORT={api}")
    print(f"export NARRE_E2E_WEB_PORT={web}")
