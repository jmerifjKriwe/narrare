"""The stack's ports are configuration, and so are its URLs and worker pairs.

Every case runs a fresh interpreter through ``uv run python -c``: the module
reads the environment at import time, and importing it in-process would freeze
whatever this pytest run was started with.

The inherited environment is stripped of the E2E keys first: a developer's
``NARRE_E2E_*``, this suite running under xdist itself, or the container
gate's ``NARRE_E2E_ATTACH`` must not decide the answer.
"""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

READ = (
    "from app.kernel.testing.stack import API_PORT, API_URL, WEB_PORT, WEB_URL; "
    "print(API_PORT, WEB_PORT); print(API_URL); print(WEB_URL)"
)

READ_WEB_ENV = (
    "from app.kernel.testing.stack import _web_environment; "
    "env = _web_environment(); "
    "print(env['NARRE_E2E_API_PORT'], env['NARRE_E2E_WEB_PORT'])"
)

_INHERITED_E2E_KEYS = (
    "NARRE_E2E_API_PORT",
    "NARRE_E2E_WEB_PORT",
    "NARRE_E2E_ATTACH",
    "NARRE_DATABASE_URL",
    "PYTEST_XDIST_WORKER",
)


def _env(**values: str) -> dict[str, str]:
    inherited = {key: value for key, value in os.environ.items() if key not in _INHERITED_E2E_KEYS}
    return {**inherited, **values}


def _read(source: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603  fixed argument list, this interpreter
        ["uv", "run", "python", "-c", source],  # noqa: S607  resolved tool, uv is on PATH
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _stack_ports(
    env: dict[str, str],
) -> tuple[int, int, str, str]:
    process = _read(READ, env)
    assert process.returncode == 0, process.stderr
    port_line, api_url, web_url = process.stdout.splitlines()[-3:]
    api_port, web_port = (int(part) for part in port_line.split())
    return api_port, web_port, api_url, web_url


def test_env_set_overrides_both_urls() -> None:
    api_port, web_port, api_url, web_url = _stack_ports(
        _env(NARRE_E2E_API_PORT="8199", NARRE_E2E_WEB_PORT="3199")
    )
    assert (api_port, web_port) == (8199, 3199)
    assert (api_url, web_url) == (
        f"http://127.0.0.1:{api_port}",
        f"http://127.0.0.1:{web_port}",
    )


def test_unset_means_the_defaults() -> None:
    api_port, web_port, api_url, web_url = _stack_ports(_env())
    assert (api_port, web_port) == (8000, 3100)
    assert (api_url, web_url) == (
        f"http://127.0.0.1:{api_port}",
        f"http://127.0.0.1:{web_port}",
    )


def test_an_xdist_worker_moves_the_pair() -> None:
    """Worker n owns the pair ten ports above worker n-1: two suites, two stacks."""
    api_port, web_port, api_url, web_url = _stack_ports(_env(PYTEST_XDIST_WORKER="gw2"))
    assert (api_port, web_port) == (8020, 3120)
    assert (api_url, web_url) == (
        f"http://127.0.0.1:{api_port}",
        f"http://127.0.0.1:{web_port}",
    )


def test_an_xdist_worker_moves_a_configured_pair_too() -> None:
    """An explicit pair moves the whole ladder, so a second checkout keeps its door."""
    api_port, web_port, _, _ = _stack_ports(
        _env(
            NARRE_E2E_API_PORT="8199",
            NARRE_E2E_WEB_PORT="3199",
            PYTEST_XDIST_WORKER="gw1",
        )
    )
    assert (api_port, web_port) == (8209, 3209)


def test_the_dev_server_gets_the_workers_pair_not_the_runs() -> None:
    """The pair the run was started with must not reach Vite.

    ``os.environ`` still holds it; forwarding it would bind the port the
    neighbouring worker owns, and nothing at one worker would notice.
    """
    process = _read(
        READ_WEB_ENV,
        _env(
            NARRE_E2E_API_PORT="8000",
            NARRE_E2E_WEB_PORT="3100",
            PYTEST_XDIST_WORKER="gw1",
        ),
    )
    assert process.returncode == 0, process.stderr
    assert process.stdout.split()[-2:] == ["8010", "3110"]


def test_an_attached_run_accepts_its_first_worker() -> None:
    api_port, web_port, api_url, web_url = _stack_ports(
        _env(
            NARRE_E2E_ATTACH="http://127.0.0.1:8080",
            NARRE_DATABASE_URL="postgresql+asyncpg://narrare:narrare@127.0.0.1:5439/narrare",
            PYTEST_XDIST_WORKER="gw0",
        )
    )
    assert (api_port, web_port) == (8000, 3100)
    assert (api_url, web_url) == ("http://127.0.0.1:8080", "http://127.0.0.1:8080")


def test_an_attached_run_refuses_a_second_worker() -> None:
    """One instance has one database; a second worker would race in it."""
    process = _read(
        READ,
        _env(
            NARRE_E2E_ATTACH="http://127.0.0.1:8080",
            NARRE_DATABASE_URL="postgresql+asyncpg://narrare:narrare@127.0.0.1:5439/narrare",
            PYTEST_XDIST_WORKER="gw1",
        ),
    )
    assert process.returncode != 0
    assert "runs serially" in process.stderr
