"""Point the app at the writing suite's own database before anything imports it."""

import os

from app.kernel.db.testsupport import ensure_database, url_for

DATABASE = "narrare_v2_test"

ensure_database(DATABASE)
os.environ["NARRE_DATABASE_URL"] = url_for(DATABASE)
