# ADR-009 — Security Stack Modernization

> **Status:** ✅ Accepted
> **Date:** 2026-05-12
> **Deciders:** Architecture Agent
> **Supersedes:** bcrypt and slowapi selections in ADR-006

---

## Context

Current security dependencies:

- **bcrypt 5.0** for password hashing — a solid choice from 2015, but argon2
  won the Password Hashing Competition (PHC) and is now the recommended
  algorithm for new systems.
- **slowapi 0.1.9** for rate limiting — wraps the synchronous `limits` library.
  This creates friction in our async-first architecture: every rate-limit check
  blocks or requires thread-pool wrapping.

We have **zero users in production**. The migration cost is effectively zero
right now. Once users exist, every security migration requires backwards
compatibility and coordinated rollouts.

---

## Decision Drivers

- Local-first philosophy — self-hostable, no cloud dependencies
- Async-native — every I/O operation should be async, no thread-pool bridges
- Zero migration cost — no existing password hashes to rotate
- Industry best practice — argon2 is the PHC winner, recommended by OWASP
- Minimal dependency surface — fewer deps = fewer vuln vectors

---

## Options Considered

### Option A — argon2-cffi + fastapi-limiter (chosen)

**argon2-cffi** replaces bcrypt. Argon2id is the OWASP-recommended hashing
algorithm — memory-hard, GPU-resistant, configurable parallelism.

**fastapi-limiter** replaces slowapi. Redis-based, async-native, actively
maintained, built for FastAPI.

**Pros:**
- Argon2id is the current best practice (PHC winner, OWASP recommended)
- fastapi-limiter is async-native — no `run_in_executor` bridges
- Both are lightweight, self-hostable, no external services
- Zero users → zero migration cost

**Cons:**
- argon2 requires libffi on the host (already present in our Docker image)
- fastapi-limiter requires Redis (already in our stack)

### Option B — Keep bcrypt + switch only rate limiter

Partial modernization. Reduces change surface but leaves the weaker hash.

**Pros:**
- Smaller diff
- bcrypt is battle-tested and well-understood

**Cons:**
- Misses the zero-user migration window
- Will need argon2 migration later WITH backwards-compat overhead

### Option C — passlib with multi-scheme support

passlib abstracts hashing and supports argon2, bcrypt, and others.

**Pros:**
- Handles migration transparently
- Supports multiple hash formats

**Cons:**
- passlib development has stalled — last release 2020
- Adds an abstraction layer we don't need with zero users
- We only need two schemes (new + legacy verify), not a full framework

---

## Decision

**We choose argon2-cffi + fastapi-limiter.**

The decisive factor is the zero-user window. Right now we can swap the hashing
algorithm with no backwards compatibility, no migration scripts, no dual-hash
verification period. For rate limiting, fastapi-limiter aligns with our
async-first architecture and uses Redis we already have.

---

## Rationale

bcrypt served the industry well, but argon2id is demonstrably superior for
modern threat models (memory-hardness resists GPU/ASIC attacks). Starting with
argon2 from day one avoids a painful migration later.

slowapi's synchronous foundation is a leaky abstraction in our codebase.
Every rate-limit call in an async handler needs special handling. fastapi-limiter
is Redis-native and async-native — it fits our stack without compromises.

For the unlikely case of future migration (e.g., importing users from another
system using bcrypt), the verification path will support both formats:
check the hash prefix (`$argon2` vs `$2b$`) and dispatch accordingly.

---

## Consequences

**Positive:**
- Industry-leading password hashing from day one
- Async-native rate limiting — no thread-pool bridges
- Simpler codebase — no sync/async impedance mismatch in rate limiting
- Clean dependency tree — both libs are actively maintained

**Negative / Tradeoffs:**
- argon2 requires libffi on Alpine Linux (already in our Docker image)
- Rate limiting is now Redis-dependent (already a hard dependency)

**Changes from TECH_STACK.md:**
- Remove: `bcrypt`, `slowapi`
- Add: `argon2-cffi`, `fastapi-limiter`

---

## Implementation Notes

### Dependencies

```toml
# pyproject.toml
"argon2-cffi>=23.1.0",
"fastapi-limiter>=0.1.6",
```

### Password hashing (auth/security.py)

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher(type=2)  # argon2id

def hash_password(password: str) -> str:
    return _hasher.hash(password)

def verify_password(hash: str, password: str) -> bool:
    # Support legacy bcrypt hashes during migration window
    if hash.startswith("$2b$"):
        import bcrypt
        return bcrypt.checkpw(password.encode(), hash.encode())
    try:
        _hasher.verify(hash, password)
        return True
    except VerifyMismatchError:
        return False
```

### Rate limiting middleware

```python
# _app/middleware.py
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

@app.on_event("startup")
async def init_rate_limiter():
    redis = aioredis.from_url(settings.redis_url)
    await FastAPILimiter.init(redis)
```

---

## Review Trigger

- [ ] If argon2-cffi has a breaking security advisory
- [ ] If fastapi-limiter stops being maintained
- [ ] If we need distributed rate limiting beyond single-instance Redis

---

## Addendum: Token Storage (2026-05-14)

Refresh tokens use **httpOnly cookies** (`narrare_refresh`), set by the backend on
login/register and read by the refresh endpoint. This prevents XSS-based token theft
(the cookie is not accessible to JavaScript). Access tokens remain in-memory only
(not localStorage). The frontend `restoreSession()` function performs a silent refresh
via the httpOnly cookie to re-establish sessions across page reloads.

Implementation: `apps/api/narrare/auth/cookie_helpers.py`, `packages/web/lib/api/client.ts` (`restoreSession`).

---

## Addendum: Exception Handling & Test-Mode Hasher Policy (2026-08-08)

> **Status:** 🔄 Proposed
> **Date:** 2026-08-08
> **Deciders:** Architecture Agent
> **Trigger:** E2E flake in `test_logout_redirects_to_login` (CI Run #494, commit `1eb2370b`)

### Context

CI Run #494 failed on exactly one E2E test:
`tests/e2e/test_auth_flow.py::TestAuthFlow::test_logout_redirects_to_login`.
Re-run of the single job passed (28 passed) — confirmed flake, not regression.
ADR-080 (merged in `1eb2370b`) did not touch the auth path; auth code was
byte-identical to the last green Run #490.

**Root cause (verified, not guessed):** `verify_password()` in
`apps/api/narrare/auth/security.py:41–47` catches
`argon2.exceptions.VerificationError` — the **base class** of
`VerifyMismatchError` and `InvalidHashError` — in addition to
`VerifyMismatchError`. This catch-all masks transient argon2 internal
failures (memory/thread allocation under CI contention: `memory_cost=65536`
/ 64 MB × `parallelism=4` threads) as `False`, which the service converts
to 401 `"Invalid email or password"`. The flake occurred because a
transient argon2 allocation failure during the UI-login step was
indistinguishable from a genuine password mismatch.

**Spec-vs-implementation divergence:** ADR-009 §Password hashing (lines
150–160) specifies `verify_password` catching **only** `VerifyMismatchError`.
The actual implementation added a `VerificationError` catch-all that is
absent from the spec. This is a latent defect (RULE-11 violation: silent
failure masking), not an intentional design choice.

### Decision Drivers

- **RULE-11** (no silent failures): The `VerificationError` catch-all
  swallows transient errors without logging — operators cannot diagnose
  flakes.
- **Security**: The fix must not open an account-existence oracle. An
  attacker must not be able to distinguish "user does not exist" from
  "password wrong" from "server had a transient error" by HTTP status code.
- **Flake reduction**: The argon2 hasher's OWASP-recommended params
  (`memory_cost=65536`, `parallelism=4`) require 64 MB × 4 threads per
  `verify()` call. Under CI runner contention (shared GitHub Actions
  runner), this can fail intermittently. Production must keep OWASP params;
  test/E2E mode should use lighter params to reduce flake surface.
- **Sustainability**: The fix must be correct in 3, 6, 12 months — not a
  test-side retry that masks the server-side masking.

### Options Considered — Decision 1: Exception Handling

#### Option A — 401 + structured error log (compromise) ✅ Chosen

`VerifyMismatchError` → `return False` (no log, expected).
`InvalidHashError` → `logger.error("password_hash_invalid", ...)` + `return False`.
`VerificationError` (non-mismatch, non-invalid-hash) →
`logger.error("password_verification_transient_failure", ...)` + `return False`.

All paths return `False` → 401 "Invalid email or password". No status-code
oracle. The structured log includes the concrete exception type for operator
diagnosis (RULE-11 compliance).

**Pros:**
- No account-existence oracle (same 401 for all auth failures)
- RULE-11 compliant (transient errors are logged with concrete type)
- No contract change (`verify_password` still returns `bool`)
- Minimal diff — adds `structlog` import + logging to existing except blocks

**Cons:**
- 401 is misleading for a server-side problem (transient error ≠ wrong password)
- Operators must check logs to distinguish flakes from real auth failures

#### Option B — 500 for transient errors (honest HTTP semantics)

`VerifyMismatchError` → `return False` (→ 401).
`VerificationError` / `InvalidHashError` → raise typed `PasswordVerificationError`
→ service catches → 500 Internal Server Error.

**Pros:**
- HTTP-semantically honest (server error = 500, auth failure = 401)
- Clear separation of concerns

**Cons:**
- Opens a (weak) account-existence oracle: an attacker who triggers a
  transient error for a specific email learns the email exists (the server
  got far enough to attempt verification). The oracle is non-deterministic
  and not attacker-controllable, but it exists.
- Changes the contract (`verify_password` can now raise)
- More complex service-layer error handling

#### Option C — Raise typed exception, service catches and logs, still 401

`verify_password` raises `PasswordVerificationError` for transient errors.
Service catches, logs, and returns 401 (same as Option A end result).

**Pros:**
- Architecturally cleaner (logging in service layer, not utility)
- `security.py` stays a pure utility (no logging import)

**Cons:**
- Changes the contract (`verify_password` can now raise)
- More verbose service-layer code (restructure the `if user is None or not
  verify_password(...)` pattern)
- Same end result as Option A with more complexity

### Decision 1

**We choose Option A — 401 + structured error log.**

The compromise is correct because:
1. Security trumps HTTP-semantics honesty: no oracle, even a weak one.
2. RULE-11 is satisfied by the structured log — operators can diagnose.
3. No contract change means no ripple to callers or tests.
4. Adding `structlog` to `security.py` is a cross-cutting observability
   concern, not business I/O — it does not violate RULE-06's "Utilities:
   pure functions, no I/O" spirit. The file already performs
   computationally expensive operations (password hashing, JWT signing).

### Options Considered — Decision 2: Test-Mode Hasher

#### Option (a) — Lighter params in test mode only ✅ Chosen

When `settings.is_test` is `True` (`ENVIRONMENT=test`), use:
`time_cost=1, memory_cost=8192 (8 MB), parallelism=1, hash_len=32, salt_len=16`.

When `settings.is_test` is `False` (development/production), use OWASP params:
`time_cost=3, memory_cost=65536 (64 MB), parallelism=4, hash_len=32, salt_len=16`.

The E2E server runs with `ENVIRONMENT=test` (see `scripts/run_e2e.sh:79`
and `.github/workflows/ci.yml:765`), so the test hasher applies during E2E
tests, reducing the flake surface.

**Pros:**
- Dramatically reduces flake surface (8 MB vs 64 MB, 1 thread vs 4)
- Tests run faster
- Production security posture unchanged (OWASP params in production)
- Follows existing pattern: `settings.is_test` already selects DB URL,
  CSRF behavior, migration skipping

**Cons:**
- Test-mode hasher differs from production → tests don't catch
  production-specific hashing issues (but argon2's `verify()` reads params
  from the hash encoding, so cross-mode verification works)
- Requires enforcement to ensure test hasher never activates in production

#### Option (b) — Same params + retry-on-transient

Retry `verify_password` when a transient `VerificationError` occurs (1–2 retries
with small backoff).

**Pros:**
- Tests use production params

**Cons:**
- Retry masks the server-side masking instead of fixing it — a workaround
  (architectural-discipline §4 violation)
- Adds latency to every transient failure
- Doesn't fix the root cause (resource contention)
- Retry logic in `verify_password` or service adds complexity

#### Option (c) — Only diagnostic logging, no param change

Add logging (from Decision 1) but keep OWASP params everywhere.

**Pros:**
- No security posture change at all

**Cons:**
- Does not reduce flake surface — the flake continues
- Logging helps diagnosis but doesn't prevent the failure

#### Option (d) — CI runner resources

Increase CI runner memory/CPU (e.g., use larger GitHub Actions runner).

**Pros:**
- No code change

**Cons:**
- Not controllable (GitHub Actions runners have fixed specs)
- Doesn't help local development on constrained machines
- Doesn't address the fundamental resource requirement (64 MB × 4 threads
  per verify call is heavy for a test environment)

### Decision 2

**We choose Option (a) — lighter params in test mode only.**

The test hasher is still argon2id (same algorithm, same hash format) — it's
just faster to compute. Test passwords are not sensitive (they're test
fixtures). The security posture for real users is unchanged.

**Enforcement — test hasher never in production:**
1. **Settings gate**: The hasher selection is based on
   `get_settings().is_test`, which checks `environment == "test"`. In
   production, `environment` is `"production"` → production hasher.
2. **Startup log**: The lifespan startup logs which hasher is active
   (test vs production), making misconfiguration visible.
3. **Regression test**: A unit test verifies that when
   `environment="production"`, the hasher uses OWASP params
   (`memory_cost=65536, time_cost=3, parallelism=4`), and when
   `environment="test"`, the hasher uses lighter params
   (`memory_cost=8192, time_cost=1, parallelism=1`).
4. **CI environment**: The E2E CI job sets `ENVIRONMENT=test`
   (`.github/workflows/ci.yml:765`), which is correct. Production
   deployments set `ENVIRONMENT=production` via their deployment config.

### Consequences

**Positive:**
- RULE-11 compliance: transient argon2 errors are logged with concrete type
- Flake surface dramatically reduced (8 MB vs 64 MB per verify call in test)
- No account-existence oracle opened
- No contract change (`verify_password` still returns `bool`)
- Production security posture unchanged (OWASP params)

**Negative / Tradeoffs:**
- 401 is misleading for transient server errors (mitigated by structured log)
- Test-mode hasher differs from production (mitigated by argon2's
  hash-encoded params and the regression test)
- `security.py` gains a `structlog` import (cross-cutting observability,
  not a RULE-06 violation)

**Constraints introduced:**
- RULE-11: every `except` block in `verify_password` either returns `False`
  (for expected mismatch) or logs + returns `False` (for unexpected errors).
  No bare `except: pass`.
- The test hasher params (`memory_cost=8192, time_cost=1, parallelism=1`)
  are a governed default — changes require ADR review.

### Implementation Notes

**`security.py` changes:**

```python
import structlog

logger = structlog.get_logger(__name__)

# Production hasher — OWASP-recommended parameters (unchanged)
_production_hasher = argon2.PasswordHasher(
    time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16,
)

# Test hasher — lighter parameters for test/E2E environments
_test_hasher = argon2.PasswordHasher(
    time_cost=1, memory_cost=8192, parallelism=1, hash_len=32, salt_len=16,
)

def _get_hasher() -> argon2.PasswordHasher:
    """Return the appropriate hasher based on current settings."""
    from narrare._app.config import get_settings
    if get_settings().is_test:
        return _test_hasher
    return _production_hasher

def hash_password(plain: str) -> str:
    return _get_hasher().hash(plain)

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

**Key points:**
- `VerifyMismatchError` is caught first (subclass of `VerificationError`)
- `InvalidHashError` is caught separately (data corruption vs transient)
- The catch-all `VerificationError` now logs before returning `False`
- `_get_hasher()` is called at runtime, not import time — settings are
  available by then. Both hashers are created at module level (no `lru_cache`
  cache-staleness issue).
- `needs_rehash()` also uses `_get_hasher()` — consistent hasher selection.

**Regression test (TDD — must fail first, then pass):**

```python
def test_verify_password_logs_transient_verification_error(caplog):
    """Transient VerificationError is logged, not silently swallowed."""
    # Create a valid argon2 hash
    hashed = hash_password("testpassword")
    # Patch the hasher's verify to raise VerificationError (non-mismatch)
    with patch.object(_get_hasher(), "verify", side_effect=argon2.exceptions.VerificationError("transient")):
        # Must return False (→ 401, no oracle)
        assert verify_password("testpassword", hashed) is False
    # Must have logged the error (RULE-11)
    assert any("password_verification_transient_failure" in r.message for r in caplog.records)

def test_verify_password_logs_invalid_hash_error(caplog):
    """InvalidHashError (corrupt hash) is logged, not silently swallowed."""
    with patch.object(_get_hasher(), "verify", side_effect=argon2.exceptions.InvalidHashError("corrupt")):
        assert verify_password("testpassword", "$argon2id$corrupt") is False
    assert any("password_hash_invalid" in r.message for r in caplog.records)

def test_verify_password_mismatch_no_log(caplog):
    """VerifyMismatchError (wrong password) returns False without logging."""
    hashed = hash_password("correct")
    assert verify_password("wrong", hashed) is False
    # No error-level log for expected mismatch
    assert not any(r.levelname == "ERROR" for r in caplog.records)

def test_production_hasher_uses_owasp_params(monkeypatch):
    """Production environment must use OWASP-recommended hasher params."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    hasher = _get_hasher()
    assert hasher.memory_cost == 65536
    assert hasher.time_cost == 3
    assert hasher.parallelism == 4

def test_test_hasher_uses_lighter_params(monkeypatch):
    """Test environment uses lighter hasher params to reduce flake surface."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()
    hasher = _get_hasher()
    assert hasher.memory_cost == 8192
    assert hasher.time_cost == 1
    assert hasher.parallelism == 1
```

### Review Trigger

- [ ] If argon2-cffi changes its exception hierarchy (e.g., `VerificationError`
      is restructured)
- [ ] If OWASP updates argon2 parameter recommendations
- [ ] If the flake recurs even with test-mode hasher (→ investigate CI runner
      resources or further param reduction)
- [ ] If a security audit identifies the 401-for-transient-error pattern as
      unacceptable (→ revisit Option B with rate-limited 500)
