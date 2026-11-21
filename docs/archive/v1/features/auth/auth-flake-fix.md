# Implementation Spec: Auth Flake Fix — Exception Handling & Test-Mode Hasher

> **Status:** draft
> **ADR:** ADR-009 Addendum (🔄 Proposed, 2026-08-08)
> **Scope:** `apps/api/narrare/auth/security.py`, `tests/unit/api/auth/test_security.py`
> **No contract change** — `verify_password` signature stays `(str, str) -> bool`

---

## Root Cause

`verify_password()` in `security.py:41–47` catches
`argon2.exceptions.VerificationError` (the **base class** of
`VerifyMismatchError` and `InvalidHashError`) in addition to
`VerifyMismatchError`. This catch-all masks transient argon2 internal
failures (memory/thread allocation under CI contention: 64 MB × 4 threads)
as `False` → 401 `"Invalid email or password"`. The flake in CI Run #494
occurred because a transient argon2 allocation failure during the UI-login
step was indistinguishable from a genuine password mismatch.

This is a RULE-11 violation (silent failure) and a divergence from the
ADR-009 spec (which specifies catching only `VerifyMismatchError`).

---

## Tasks (Layer-Ordered)

### Task 1 — Regression Tests (TDD: write first, must fail, then pass after Task 2)

**File:** `tests/unit/api/auth/test_security.py`

Add the following test class. All tests must **fail** against the current
code (before Task 2), then **pass** after Task 2.

#### 1a. Transient `VerificationError` is logged (RULE-11)

```python
class TestVerifyPasswordExceptionHandling:
    """Regression tests for ADR-009 Addendum: exception handling policy."""

    def test_transient_verification_error_logged_and_returns_false(
        self, monkeypatch, caplog
    ) -> None:
        """Transient VerificationError must be logged, not silently swallowed."""
        import argon2
        from narrare.auth.security import _get_hasher, verify_password, hash_password

        hashed = hash_password("testpassword")
        hasher = _get_hasher()
        monkeypatch.setattr(
            hasher, "verify",
            lambda h, p: (_ for _ in ()).throw(
                argon2.exceptions.VerificationError("transient")
            ),
        )
        with caplog.at_level("ERROR", logger="narrare.auth.security"):
            result = verify_password("testpassword", hashed)
        assert result is False
        assert any(
            "password_verification_transient_failure" in r.message
            for r in caplog.records
        ), "Transient VerificationError must be logged at ERROR level"
```

**Must fail against current code:** The current code catches
`VerificationError` and returns `False` without logging → the assertion
on `caplog.records` fails.

#### 1b. `InvalidHashError` is logged (data corruption)

```python
    def test_invalid_hash_error_logged_and_returns_false(
        self, monkeypatch, caplog
    ) -> None:
        """InvalidHashError (corrupt hash) must be logged."""
        import argon2
        from narrare.auth.security import _get_hasher, verify_password

        hasher = _get_hasher()
        monkeypatch.setattr(
            hasher, "verify",
            lambda h, p: (_ for _ in ()).throw(
                argon2.exceptions.InvalidHashError("corrupt")
            ),
        )
        with caplog.at_level("ERROR", logger="narrare.auth.security"):
            result = verify_password("testpassword", "$argon2id$corrupt")
        assert result is False
        assert any(
            "password_hash_invalid" in r.message
            for r in caplog.records
        ), "InvalidHashError must be logged at ERROR level"
```

#### 1c. `VerifyMismatchError` does NOT log (expected behavior)

```python
    def test_mismatch_returns_false_without_error_log(
        self, caplog
    ) -> None:
        """VerifyMismatchError (wrong password) returns False without ERROR log."""
        from narrare.auth.security import hash_password, verify_password

        hashed = hash_password("correct")
        with caplog.at_level("ERROR", logger="narrare.auth.security"):
            result = verify_password("wrong", hashed)
        assert result is False
        assert not any(
            r.levelname == "ERROR" for r in caplog.records
        ), "Expected mismatch must not log at ERROR level"
```

**Must pass against current code** (this is a guard test — ensures we don't
add logging for expected mismatches).

#### 1d. Production hasher uses OWASP params

```python
    def test_production_hasher_uses_owasp_params(
        self, monkeypatch
    ) -> None:
        """Production environment must use OWASP-recommended hasher params."""
        from narrare._app.config import get_settings
        from narrare.auth.security import _get_hasher

        monkeypatch.setenv("ENVIRONMENT", "production")
        get_settings.cache_clear()
        try:
            hasher = _get_hasher()
            assert hasher.memory_cost == 65536  # 64 MB
            assert hasher.time_cost == 3
            assert hasher.parallelism == 4
        finally:
            monkeypatch.delenv("ENVIRONMENT", raising=False)
            get_settings.cache_clear()
```

**Must fail against current code:** The current code has a single
module-level `_hasher` with no `_get_hasher()` function → `ImportError`.

#### 1e. Test hasher uses lighter params

```python
    def test_test_hasher_uses_lighter_params(
        self, monkeypatch
    ) -> None:
        """Test environment uses lighter hasher params to reduce flake surface."""
        from narrare._app.config import get_settings
        from narrare.auth.security import _get_hasher

        monkeypatch.setenv("ENVIRONMENT", "test")
        get_settings.cache_clear()
        try:
            hasher = _get_hasher()
            assert hasher.memory_cost == 8192  # 8 MB
            assert hasher.time_cost == 1
            assert hasher.parallelism == 1
        finally:
            monkeypatch.delenv("ENVIRONMENT", raising=False)
            get_settings.cache_clear()
```

**Must fail against current code:** Same `ImportError` — no `_get_hasher()`.

---

### Task 2 — Fix `apps/api/narrare/auth/security.py` (makes Task 1 tests pass)

**File:** `apps/api/narrare/auth/security.py`

**Changes:**

1. **Add `structlog` import:**
   ```python
   import structlog
   logger = structlog.get_logger(__name__)
   ```

2. **Replace module-level `_hasher` with two hashers + `_get_hasher()`:**
   ```python
   # Production hasher — OWASP-recommended parameters (ADR-009)
   _production_hasher = argon2.PasswordHasher(
       time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16,
   )

   # Test hasher — lighter parameters for test/E2E environments (ADR-009 Addendum)
   _test_hasher = argon2.PasswordHasher(
       time_cost=1, memory_cost=8192, parallelism=1, hash_len=32, salt_len=16,
   )

   def _get_hasher() -> argon2.PasswordHasher:
       """Return the appropriate hasher based on current settings.

       Production/development: OWASP params (64 MB, 4 threads).
       Test/E2E: lighter params (8 MB, 1 thread) to reduce flake surface.

       See ADR-009 Addendum for rationale and enforcement.
       """
       from narrare._app.config import get_settings
       if get_settings().is_test:
           return _test_hasher
       return _production_hasher
   ```

3. **Update `hash_password`:**
   ```python
   def hash_password(plain: str) -> str:
       """Hash a plaintext password with argon2id."""
       return _get_hasher().hash(plain)
   ```

4. **Update `verify_password` — fix exception handling:**
   ```python
   def verify_password(plain: str, hashed: str) -> bool:
       if hashed.startswith("$argon2"):
           try:
               return _get_hasher().verify(hashed, plain)
           except argon2.exceptions.VerifyMismatchError:
               return False
           except argon2.exceptions.InvalidHashError:
               logger.error("password_hash_invalid", hash_prefix=hashed[:10])
               return False
           except argon2.exceptions.VerificationError:
               logger.error("password_verification_transient_failure", exc_info=True)
               return False
       # ... bcrypt and unknown-format paths unchanged
   ```

   **Key:** `VerifyMismatchError` is caught first (it's a subclass of
   `VerificationError`). `InvalidHashError` is caught separately (data
   corruption). The catch-all `VerificationError` now logs before returning
   `False`. The `hash_prefix` (first 10 chars) is logged for
   `InvalidHashError` to aid diagnosis without leaking the full hash.

5. **Update `needs_rehash`:**
   ```python
   def needs_rehash(hashed: str) -> bool:
       if hashed.startswith("$argon2"):
           return _get_hasher().check_needs_rehash(hashed)
       return True
   ```

**No other files need changes:**
- `apps/api/narrare/auth/service.py` — `verify_password` signature unchanged,
  no changes needed
- `apps/api/narrare/auth/contracts.py` — no Protocol changes
- `apps/api/narrare/auth/repository.py` — no changes
- `apps/api/narrare/auth/router.py` — no changes

---

### Task 3 — Verify Existing Tests Still Pass

Run the existing test suite to ensure no regressions:

```bash
# Unit tests for auth security
uv run pytest tests/unit/api/auth/test_security.py -v

# Unit tests for auth service
uv run pytest tests/unit/api/auth/test_auth_service.py -v

# Integration tests for auth
uv run pytest tests/integration/test_seed_dev_user.py -v

# Full unit + integration suite
uv run pytest tests/unit/ tests/integration/ -x -q
```

**Expected:** All existing tests pass. The test-mode hasher is active during
unit/integration tests (`ENVIRONMENT=test`), so hashes are created and
verified with lighter params — existing tests should be unaffected.

---

### Task 4 — E2E Harness (No Change Needed)

The E2E test `test_logout_redirects_to_login` is correct — it tests real
user flow. The flake was server-side (argon2 transient failure), not
test-side. The fix in Task 2 (test-mode hasher with lighter params) reduces
the flake surface. No E2E test changes needed.

**Verification:** After the fix, re-run the E2E suite multiple times to
confirm the flake is gone:
```bash
for i in $(seq 1 5); do
  uv run pytest tests/e2e/test_auth_flow.py::TestAuthFlow::test_logout_redirects_to_login -v
done
```

---

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-03 | ✅ | No contract change — `verify_password` signature unchanged |
| RULE-06 | ✅ | `apps/api/narrare/auth/security.py` keeps its role (password hashing utility); `structlog` is cross-cutting observability, not business I/O |
| RULE-11 | ✅ | Every `except` block either returns `False` (expected mismatch) or logs + returns `False` (unexpected error). No silent failures. |
| RULE-09 | ✅ | All new functions are type-annotated (`_get_hasher() -> argon2.PasswordHasher`) |

---

## Definition of Done

- [ ] Task 1: Regression tests written, all fail against current code
- [ ] Task 2: `apps/api/narrare/auth/security.py` fixed, all Task 1 tests pass
- [ ] Task 3: Existing tests pass (no regressions)
- [ ] Task 4: E2E flake confirmed gone (5 consecutive runs pass)
- [ ] ADR-009 Addendum approved by user
- [ ] No account-existence oracle opened (all auth failures return 401)
- [ ] Test hasher never activates in production (regression test passes)
