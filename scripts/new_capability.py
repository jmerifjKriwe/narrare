#!/usr/bin/env python3
"""Create a capability folder with the two fixtures that are easy to get wrong.

The folder itself is a mkdir. What a new capability reliably gets wrong is its
test databases: the integration suite shares narrare_v2_test, the E2E suite gets
a database of its own and a module-scoped stack so two suites never hold the
same ports. Those two conftest files are what this writes; the code is yours.
"""

import sys
from pathlib import Path

CAPABILITIES = Path("app/capabilities")

INTEGRATION_FIXTURE = '''"""Fixtures for the {name} suite.

Shared test database, schema from the migrations.
"""

import os

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.kernel.db.testsupport import ensure_database, url_for

os.environ["NARRE_DATABASE_URL"] = url_for("narrare_v2_test")
ensure_database("narrare_v2_test")


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    config = Config("app/kernel/db/alembic.ini")
    config.set_main_option("script_location", "app/kernel/db/migrations")
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
async def empty_tables() -> None:
    from app.kernel.db.session import Session

    async with Session() as session:
        await session.execute(text("TRUNCATE users CASCADE"))
        await session.commit()
'''

E2E_FIXTURE = '''"""Full stack for the {name} E2E: own database, real API, real Next.js.

Module scope: the stack must be gone before the next capability's stack binds the
same ports.
"""

from collections.abc import Iterator  # noqa: TC003

import pytest
from app.kernel.testing.stack import run_stack


@pytest.fixture(scope="module")
def stack() -> Iterator[None]:
    with run_stack(database="narrare_v2_{name}_e2e", seed_user=True):
        yield
'''


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: just new-capability <name>")
    name = sys.argv[1].strip().lower()
    if not name.isidentifier():
        raise SystemExit(f"{name!r} is not a valid capability name")

    root = CAPABILITIES / name
    if root.exists():
        raise SystemExit(f"{root} already exists")

    (root / "tests").mkdir(parents=True)
    (root / "e2e").mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "tests" / "conftest.py").write_text(
        INTEGRATION_FIXTURE.format(name=name), encoding="utf-8"
    )
    (root / "e2e" / "conftest.py").write_text(E2E_FIXTURE.format(name=name), encoding="utf-8")

    print(f"created {root}")
    print("next: router.py (auto-mounted by app/api/main.py), service.py,")
    print("      schemas.py, a test, an E2E spec")


if __name__ == "__main__":
    main()
