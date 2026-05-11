## Context

The metrics router (`apps/api/narrare/metrics/router.py`) currently has two endpoints:
`/metrics` (Prometheus) and `/health` (hardcoded ok). We're adding `/ready`.

## Goals / Non-Goals

**Goals:**
- Add `/ready` that pings PostgreSQL via the existing async engine
- Return structured JSON for both healthy and unhealthy states
- Keep it fast — `SELECT 1` is sufficient, no complex queries

**Non-Goals:**
- Redis health check (no Redis client is wired up yet)
- LLM provider connectivity checks
- Detailed dependency enumeration (just DB for now)

## Decisions

### Decision 1: Use `SELECT 1` via raw connection

Use `engine.connect()` to run `SELECT 1` rather than going through the session
factory. This is the lightest possible DB check — no transaction overhead,
no ORM involvement.

### Decision 2: 503 with error details on failure

Return HTTP 503 with a JSON body including the error message. This gives
operators useful debugging info while being a standard unhealthy status code.
