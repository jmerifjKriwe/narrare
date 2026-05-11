## 1. Implement /ready endpoint

- [x] 1.1 Add `ready()` endpoint to `metrics/router.py` with DB connectivity check via `SELECT 1`
- [x] 1.2 Return 200 + `{"status": "ready"}` on success, 503 + `{"status": "unhealthy", ...}` on failure

## 2. Tests

- [x] 2.1 Create `tests/unit/api/metrics/__init__.py` and `test_metrics_router.py`
- [x] 2.2 Test `/health` returns 200 with `{"status": "ok"}`
- [x] 2.3 Test `/ready` returns 200 when DB is healthy
- [x] 2.4 Test `/ready` returns 503 when DB is unreachable

## 3. Verify

- [x] 3.1 Run the test suite and confirm all tests pass
