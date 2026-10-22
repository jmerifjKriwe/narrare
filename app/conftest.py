"""One database for the whole suite, named before anything binds a session.

``app/kernel/db/session.py`` reads its URL once, at import. The first import
decides, and pytest collects ``app/api`` before ``app/capabilities``: without
this file the API tests bind the session to the *development* database, and
every capability conftest then resets a test database that nobody talks to. The
symptom stays quiet — the suite passes while truncating the developer's own data
— until a model change reaches the test database and not the development one.

This file is collected before every test module under ``app/``, so the decision
is made once, in one place. The E2E stacks pass their own URL to the API process
they start; this is only the pytest process's own connection.
"""

import os

from app.kernel.db.testsupport import ensure_database, url_for

DATABASE = "narrare_v2_test"
ensure_database(DATABASE)
os.environ["NARRE_DATABASE_URL"] = url_for(DATABASE)
