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
