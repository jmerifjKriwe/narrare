"""The stack's ports are configuration, and so are its URLs (#621).

Every case runs a fresh interpreter through ``uv run python -c``: the module
reads the environment at import time, and importing it in-process would freeze
whatever this pytest run was started with.
"""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

READ = (
    "from app.kernel.testing.stack import API_PORT, API_URL, WEB_PORT, WEB_URL; "
    "print(API_PORT, WEB_PORT); print(API_URL); print(WEB_URL)"
)


def _stack_ports(
    env: dict[str, str],
) -> tuple[int, int, str, str]:
    process = subprocess.run(  # noqa: S603  fixed argument list, this interpreter
        ["uv", "run", "python", "-c", READ],  # noqa: S607  resolved tool, uv is on PATH
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert process.returncode == 0, process.stderr
    port_line, api_url, web_url = process.stdout.splitlines()[-3:]
    api_port, web_port = (int(part) for part in port_line.split())
    return api_port, web_port, api_url, web_url


def test_env_set_overrides_both_urls() -> None:
    env = {**os.environ, "NARRE_E2E_API_PORT": "8199", "NARRE_E2E_WEB_PORT": "3199"}
    api_port, web_port, api_url, web_url = _stack_ports(env)
    assert (api_port, web_port) == (8199, 3199)
    assert (api_url, web_url) == (
        f"http://127.0.0.1:{api_port}",
        f"http://127.0.0.1:{web_port}",
    )


def test_unset_means_the_defaults() -> None:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("NARRE_E2E_API_PORT", "NARRE_E2E_WEB_PORT")
    }
    api_port, web_port, api_url, web_url = _stack_ports(env)
    assert (api_port, web_port) == (8000, 3100)
    assert (api_url, web_url) == (
        f"http://127.0.0.1:{api_port}",
        f"http://127.0.0.1:{web_port}",
    )
