"""Regression test for the schema_mutating collection guard.

Pins the safety property: a test whose source contains schema-mutating
patterns (alembic downgrade, create_all/drop_all, SQL DDL) is detected by
``scan_for_schema_mutation``, while clean code and docstrings-only mentions
are not.

The guard itself lives in ``tests/_schema_guard.py`` and is invoked by the
``pytest_collection_modifyitems`` hook in ``tests/conftest.py``. This test
calls the scanner directly so the detection logic cannot silently regress.
"""

from __future__ import annotations

from tests._schema_guard import scan_for_schema_mutation

# ---------------------------------------------------------------------------
# Positive cases — schema-mutating patterns MUST be detected
# ---------------------------------------------------------------------------


class TestDetectsSchemaMutation:
    """Each schema-mutating pattern triggers a non-empty match."""

    def test_alembic_downgrade_string_arg(self) -> None:
        """``_run_alembic("downgrade", rev)`` — the CLI arg as a string literal."""
        source = """
async def test_round_trip():
    _run_alembic("downgrade", _PARENT_REVISION)
"""
        matches = scan_for_schema_mutation(source)
        assert any("downgrade" in m for m in matches)

    def test_command_downgrade_attribute(self) -> None:
        """``command.downgrade()`` — the attribute access form."""
        source = "await command.downgrade(rev)"
        assert scan_for_schema_mutation(source)

    def test_metadata_create_all(self) -> None:
        source = "Base.metadata.create_all(engine)"
        assert any("create_all" in m for m in scan_for_schema_mutation(source))

    def test_metadata_drop_all(self) -> None:
        source = "Base.metadata.drop_all(engine)"
        assert any("drop_all" in m for m in scan_for_schema_mutation(source))

    def test_create_table_sql(self) -> None:
        source = 'await conn.execute(text("CREATE TABLE novels (id INT)"))'
        assert any(
            "create" in m.lower() and "table" in m.lower() for m in scan_for_schema_mutation(source)
        )

    def test_create_table_if_not_exists_sql(self) -> None:
        """Committed CREATE TABLE IF NOT EXISTS is still schema-mutating."""
        source = 'await conn.execute(text("CREATE TABLE IF NOT EXISTS novels (id INT)"))'
        assert scan_for_schema_mutation(source)

    def test_drop_table_sql(self) -> None:
        source = 'await conn.execute(text("DROP TABLE old_widgets"))'
        assert any(
            "drop" in m.lower() and "table" in m.lower() for m in scan_for_schema_mutation(source)
        )

    def test_alter_table_sql(self) -> None:
        source = 'await conn.execute(text("ALTER TABLE novels ADD COLUMN foo TEXT"))'
        assert scan_for_schema_mutation(source)

    def test_create_index_sql(self) -> None:
        source = 'await conn.execute(text("CREATE INDEX ix_foo ON novels(foo)"))'
        assert scan_for_schema_mutation(source)

    def test_drop_index_sql(self) -> None:
        source = 'await conn.execute(text("DROP INDEX ix_old"))'
        assert scan_for_schema_mutation(source)

    def test_create_schema_sql(self) -> None:
        source = 'await conn.execute(text("CREATE SCHEMA test_isolation"))'
        assert scan_for_schema_mutation(source)

    def test_drop_schema_sql(self) -> None:
        source = 'await conn.execute(text("DROP SCHEMA test_isolation"))'
        assert scan_for_schema_mutation(source)

    def test_lowercase_sql_detected(self) -> None:
        """SQL keywords are case-insensitive in practice."""
        source = 'await conn.execute(text("create table foo (id int)"))'
        assert scan_for_schema_mutation(source)


# ---------------------------------------------------------------------------
# Negative cases — clean code and docstring-only mentions MUST NOT trigger
# ---------------------------------------------------------------------------


class TestCleanCodeNotFlagged:
    """Non-mutating code returns an empty match list."""

    def test_plain_select(self) -> None:
        source = 'await conn.execute(text("SELECT 1"))'
        assert scan_for_schema_mutation(source) == []

    def test_insert_into(self) -> None:
        """INSERT/UPDATE/DELETE (DML) are NOT schema mutations."""
        source = 'await conn.execute(text("INSERT INTO novels (id) VALUES (1)"))'
        assert scan_for_schema_mutation(source) == []

    def test_truncate_not_detected(self) -> None:
        """TRUNCATE is destructive DML, not schema DDL — the guard is scope-limited
        to schema patterns per the review (Task C handles TRUNCATE manually)."""
        source = 'await conn.execute(text("TRUNCATE users CASCADE"))'
        assert scan_for_schema_mutation(source) == []

    def test_information_schema_query(self) -> None:
        """Read-only catalog introspection (test_migration_0037.py pattern)."""
        source = (
            "await conn.execute(text("
            '"SELECT is_nullable FROM information_schema.columns '
            'WHERE table_name = :t"))'
        )
        assert scan_for_schema_mutation(source) == []

    def test_docstring_with_downgrade_not_flagged(self) -> None:
        """A docstring mentioning 'downgrade' must not false-positive."""
        source = '''"""Round-trip safety test.

        The upgrade head → downgrade -1 → upgrade head round-trip is run
        manually as the release verification step.
        """

async def test_clean():
    await conn.execute(text("SELECT 1"))
'''
        assert scan_for_schema_mutation(source) == []

    def test_empty_source(self) -> None:
        assert scan_for_schema_mutation("") == []

    def test_syntax_error_returns_empty(self) -> None:
        """Unparseable source must never block collection."""
        assert scan_for_schema_mutation("def broken(:") == []
