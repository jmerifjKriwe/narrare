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

Shared test database, schema from the models.
"""

import os
from asyncio import run

import pytest
from sqlalchemy import text

from app.kernel.db.testsupport import ensure_database, url_for

os.environ["NARRE_DATABASE_URL"] = url_for("narrare_v2_test")
ensure_database("narrare_v2_test")


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    from app.kernel.db.init import reset_schema

    run(reset_schema(url_for("narrare_v2_test")))


@pytest.fixture(autouse=True)
async def empty_tables() -> None:
    from app.kernel.db.session import Session

    async with Session() as session:
        await session.execute(text("TRUNCATE users CASCADE"))
        await session.commit()
'''

E2E_FIXTURE = '''"""Full stack for the {name} E2E: own database, real API, real web app.

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

FACTS_FILE = """# Facts only (spec §4): every field is read by at least two generated views —
# app/generated/capabilities.py, web/lib/generated/capabilities.ts and
# docs/user/INDEX.md. Behaviour, schemas and prompts never go here.
id: {name}
title: {name}.heading # i18n key; add it to i18n/en.json, de.json and fr.json
path: /{name}
needs: []
nav: false
"""


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
    (root / "capability.yaml").write_text(FACTS_FILE.format(name=name), encoding="utf-8")
    (root / "tests" / "conftest.py").write_text(
        INTEGRATION_FIXTURE.format(name=name), encoding="utf-8"
    )
    (root / "e2e" / "conftest.py").write_text(E2E_FIXTURE.format(name=name), encoding="utf-8")

    print(f"created {root}")
    print("next: the title key in i18n/en.json, de.json and fr.json, then")
    print("      `just generate` (the registry must name the new capability before")
    print("      the app boots), router.py (auto-mounted), service.py, schemas.py,")
    print("      a test, an E2E spec")


if __name__ == "__main__":
    main()
