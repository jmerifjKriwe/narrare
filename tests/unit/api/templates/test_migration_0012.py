"""Unit tests for migration 0012_drop_template_language.

Verifies the migration's upgrade and downgrade SQL logic by inspecting
the migration source code. Actual SQL execution is tested in integration
tests (requires a real PostgreSQL instance).
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path


def _load_migration_module():  # type: ignore[no-untyped-def]
    """Load the migration module directly from file path."""
    migration_file = (
        Path(__file__).resolve().parents[4]
        / "apps"
        / "api"
        / "alembic"
        / "versions"
        / "0012_drop_template_language.py"
    )
    if not migration_file.exists():
        import pytest

        pytest.skip(f"Migration file not found: {migration_file}")
    spec = importlib.util.spec_from_file_location(
        "migration_0012_drop_template_language", str(migration_file)
    )
    if spec is None or spec.loader is None:
        import pytest

        pytest.skip(f"Cannot load migration from {migration_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestMigration0012Metadata:
    """Tests for the migration's revision metadata."""

    def test_revision_id_is_set(self) -> None:
        """Migration has the correct revision ID."""
        mod = _load_migration_module()
        assert mod.revision == "0012_drop_template_language"
        assert mod.down_revision == "0011_add_concept_setting_types"

    def test_upgrade_and_downgrade_functions_exist(self) -> None:
        """Migration module has both upgrade() and downgrade() functions."""
        mod = _load_migration_module()
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)


class TestMigration0012UpgradeSQL:
    """Verify upgrade SQL by inspecting the migration source."""

    def test_upgrade_sql_contains_row_consolidation(self) -> None:
        """Upgrade SQL deletes duplicate rows keeping highest version."""
        mod = _load_migration_module()
        source = inspect.getsource(mod.upgrade)
        assert "DELETE FROM kb_templates" in source
        assert "ROW_NUMBER()" in source
        assert "PARTITION BY entity_type, scope, scope_id" in source
        assert "rn > 1" in source

    def test_upgrade_sql_uses_if_exists_patterns(self) -> None:
        """Upgrade SQL uses idempotent IF EXISTS patterns."""
        mod = _load_migration_module()
        source = inspect.getsource(mod.upgrade)
        assert "IF EXISTS" in source

    def test_upgrade_sql_drops_old_constraint(self) -> None:
        """Upgrade drops the old unique constraint including language."""
        mod = _load_migration_module()
        source = inspect.getsource(mod.upgrade)
        assert "DROP CONSTRAINT" in source
        assert "uq_kb_templates_unique" in source

    def test_upgrade_sql_drops_language_column(self) -> None:
        """Upgrade drops the language column."""
        mod = _load_migration_module()
        source = inspect.getsource(mod.upgrade)
        assert "DROP COLUMN" in source
        assert "language" in source

    def test_upgrade_sql_adds_new_constraint(self) -> None:
        """Upgrade adds new constraint on (entity_type, scope, scope_id)."""
        mod = _load_migration_module()
        source = inspect.getsource(mod.upgrade)
        assert "ADD CONSTRAINT" in source
        assert "entity_type, scope, scope_id" in source


class TestMigration0012DowngradeSQL:
    """Verify downgrade SQL by inspecting the migration source."""

    def test_downgrade_drops_new_constraint(self) -> None:
        """Downgrade drops the new unique constraint first."""
        mod = _load_migration_module()
        source = inspect.getsource(mod.downgrade)
        assert "DROP CONSTRAINT" in source

    def test_downgrade_re_adds_language_column(self) -> None:
        """Downgrade re-adds the language column with default 'en'."""
        mod = _load_migration_module()
        source = inspect.getsource(mod.downgrade)
        assert "ADD COLUMN" in source
        assert "language" in source
        assert "VARCHAR(10)" in source
        assert "DEFAULT 'en'" in source

    def test_downgrade_restores_old_constraint(self) -> None:
        """Downgrade restores the old unique constraint with language."""
        mod = _load_migration_module()
        source = inspect.getsource(mod.downgrade)
        assert "entity_type, language, scope, scope_id" in source
