#!/usr/bin/env python3
"""Rotate the NARRARE_ENCRYPTION_KEY by re-encrypting all user API keys.

This script re-encrypts every ``user_providers.api_key_encrypted`` entry
from the old Fernet key to the new one.  It is **transactional**: either
all rows are re-encrypted or none (the session is rolled back on error).

Keys are read from the ``OLD_ENCRYPTION_KEY`` and ``NEW_ENCRYPTION_KEY``
environment variables, or prompted interactively via ``getpass`` if the
env vars are not set.  Keys are **never** accepted as CLI arguments to
avoid plaintext leakage in shell history.

Usage::

    # Dry run — see what would change
    python scripts/rotate_encryption_key.py --dry-run

    # Real rotation
    python scripts/rotate_encryption_key.py

Environment variables::

    OLD_ENCRYPTION_KEY  — current Fernet key (or prompted interactively)
    NEW_ENCRYPTION_KEY  — new Fernet key (or prompted interactively)
    DATABASE_URL        — async SQLAlchemy URL (default: dev DB)

See: docs/development/deployment-guide.md § Key Rotation
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet, InvalidToken

# Add workspace packages to path (same pattern as seed_dev_user.py)
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core"))
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ── Result type ──────────────────────────────────────────────────


@dataclass(frozen=True)
class RotationResult:
    """Outcome of an encryption key rotation operation.

    Attributes:
        total_rows: Total number of ``user_providers`` rows found.
        rotated: Number of rows re-encrypted (or that would be, in dry-run).
        skipped: Number of rows skipped (empty ``api_key_encrypted``).
        dry_run: Whether this was a dry run (no changes applied).
        sample_provider_names: Provider names from the first few rotated
            rows, useful for dry-run reporting.
    """

    total_rows: int
    rotated: int
    skipped: int
    dry_run: bool
    sample_provider_names: tuple[str, ...] = ()


# ── Core logic (testable — no CLI/DB setup) ─────────────────────


async def rotate_keys(
    old_key: str,
    new_key: str,
    session: AsyncSession,
    dry_run: bool = False,
) -> RotationResult:
    """Re-encrypt all ``user_providers.api_key_encrypted`` from old key to new.

    Iterates over every ``UserProvider`` row.  For each row with a non-empty
    ``api_key_encrypted``, decrypts with the old Fernet key and re-encrypts
    with the new key.  Rows with empty keys (e.g. Ollama providers) are
    skipped.

    This function does **not** commit — the caller is responsible for
    committing on success or rolling back on failure, ensuring atomicity.

    Args:
        old_key: The current Fernet encryption key (base64-encoded string).
        new_key: The new Fernet encryption key (base64-encoded string).
        session: An async SQLAlchemy session.  The caller must commit on
            success or rollback on failure.
        dry_run: If True, decrypt and count but do not modify any rows.

    Returns:
        A :class:`RotationResult` with counts and sample provider names.

    Raises:
        ValueError: If ``old_key`` or ``new_key`` is not a valid Fernet key.
        InvalidToken: If a row cannot be decrypted with ``old_key`` (wrong
            key or corrupted data).  The caller MUST rollback the session.
    """
    from sqlalchemy import select

    from narrare.settings.models import UserProvider

    # Validate keys early — fail before touching any data
    old_fernet = Fernet(old_key.encode())
    new_fernet = Fernet(new_key.encode())

    result = await session.execute(select(UserProvider))
    rows = list(result.scalars().all())

    rotated = 0
    skipped = 0
    sample_names: list[str] = []

    for row in rows:
        if not row.api_key_encrypted:
            skipped += 1
            continue

        plaintext = old_fernet.decrypt(row.api_key_encrypted.encode()).decode()
        if not dry_run:
            row.api_key_encrypted = new_fernet.encrypt(plaintext.encode()).decode()
        rotated += 1

        if len(sample_names) < 5:
            sample_names.append(row.provider_name)

    return RotationResult(
        total_rows=len(rows),
        rotated=rotated,
        skipped=skipped,
        dry_run=dry_run,
        sample_provider_names=tuple(sample_names),
    )


# ── CLI / DB setup ───────────────────────────────────────────────


async def main(argv: list[str] | None = None) -> None:
    """CLI entry point for encryption key rotation.

    Parses ``--dry-run``, reads keys from env or ``getpass``, connects to
    the database, calls :func:`rotate_keys`, and commits or rolls back.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).
    """
    parser = argparse.ArgumentParser(
        description=(
            "Rotate the NARRARE_ENCRYPTION_KEY by re-encrypting all "
            "user_providers.api_key_encrypted entries."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without committing any updates.",
    )
    args = parser.parse_args(argv)

    # Read keys from env or interactive prompt — never from CLI args
    old_key = os.environ.get("OLD_ENCRYPTION_KEY") or getpass.getpass(
        "Enter the OLD encryption key: "
    )
    new_key = os.environ.get("NEW_ENCRYPTION_KEY") or getpass.getpass(
        "Enter the NEW encryption key: "
    )

    if not old_key or not new_key:
        print(
            "Error: Both OLD_ENCRYPTION_KEY and NEW_ENCRYPTION_KEY are required.",
            file=sys.stderr,
        )
        sys.exit(1)

    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://narrare:narrare@localhost:5432/narrare_dev",
    )

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(database_url, echo=False, poolclass=NullPool)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

    print("Starting encryption key rotation...")
    if args.dry_run:
        print("(DRY RUN — no changes will be committed)")

    try:
        async with async_session_maker() as session:
            try:
                result = await rotate_keys(old_key, new_key, session, dry_run=args.dry_run)
            except (InvalidToken, ValueError) as exc:
                await session.rollback()
                print(f"Error: Rotation failed - {exc}", file=sys.stderr)
                print(
                    "All changes have been rolled back. No rows were modified.",
                    file=sys.stderr,
                )
                sys.exit(1)

            if result.dry_run:
                print(
                    f"Dry run complete: {result.rotated} row(s) would be "
                    f"re-encrypted, {result.skipped} skipped (empty key), "
                    f"{result.total_rows} total."
                )
                if result.sample_provider_names:
                    print("Providers that would be affected:")
                    for name in result.sample_provider_names:
                        print(f"  - {name}")
            else:
                await session.commit()
                print(
                    f"Success: {result.rotated} row(s) re-encrypted, "
                    f"{result.skipped} skipped (empty key), "
                    f"{result.total_rows} total."
                )
                print(
                    "Next step: update NARRARE_ENCRYPTION_KEY in your "
                    "environment to the new key and restart the API."
                )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
