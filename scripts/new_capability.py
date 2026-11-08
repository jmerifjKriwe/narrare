#!/usr/bin/env python3
"""Create a capability folder with the two fixtures that are easy to get wrong.

The folder itself is a mkdir. What a new capability reliably gets wrong is its
test databases: the integration suite names its own database for the run
(worktree token plus a per-run token), the E2E suite gets a database of its own
and a module-scoped stack so two suites never hold the same ports. Those two
conftest files are what this writes; the code is yours.
"""

import json
import sys
from pathlib import Path

CAPABILITIES = Path("app/capabilities")

INTEGRATION_FIXTURE = '''"""Fixtures for the {name} suite.

Per-run test database, schema from the models.
"""

import os
from asyncio import run

import pytest
from sqlalchemy import text

from app.kernel.db.testsupport import ensure_database, test_database, url_for

DATABASE = test_database()
ensure_database(DATABASE)
os.environ["NARRE_DATABASE_URL"] = url_for(DATABASE)


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    from app.kernel.db.init import reset_schema

    run(reset_schema(url_for(DATABASE)))


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
title: {name}.heading # i18n key; add it to web/i18n/<locale>.json for every catalog
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
    # Every catalog the generator discovers must carry the capability's title:
    # the scaffold writes one file per language the central catalog declares,
    # with the English label as the placeholder, so the first `just generate`
    # is green and translation is the next edit.
    locales = sorted(path.stem for path in Path("i18n").glob("*.json"))
    if not locales:
        raise SystemExit("i18n/*.json is missing: no catalog to scaffold against")
    catalog = {f"{name}.heading": name.replace("_", " ").title()}
    for locale in locales:
        source = root / "web" / "i18n" / f"{locale}.json"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            json.dumps(dict(sorted(catalog.items())), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"created {root}")
    print(f"next: translate web/i18n/{{{', '.join(locales)}}}.json, then")
    print("      `just generate` (the registry must name the new capability before")
    print("      the app boots), router.py (auto-mounted), service.py, schemas.py,")
    print("      a test, an E2E spec")


if __name__ == "__main__":
    main()
