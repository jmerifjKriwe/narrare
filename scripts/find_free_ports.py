#!/usr/bin/env python3
"""Print two free TCP ports for parallel E2E runs.

Usage:
    eval "$(python3 scripts/find_free_ports.py)"
    just test-e2e scope=setup
"""

from __future__ import annotations

import socket


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


if __name__ == "__main__":
    api = free_port()
    web = free_port()
    while web == api:
        web = free_port()
    print(f"export NARRE_E2E_API_PORT={api}")
    print(f"export NARRE_E2E_WEB_PORT={web}")
