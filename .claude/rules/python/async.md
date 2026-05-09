---
paths:
  - "apps/api/**/*.py"
  - "core/**/*.py"
---

# Async Patterns

## Never block the event loop
- No `time.sleep()` — use `asyncio.sleep()`
- No sync file I/O in hot paths — use `aiofiles`
- All service methods are async
- All repository methods are async

## Service layer is always async
```python
class ChapterService:
    async def write(self, ...) -> WriteResult:  # ✅ async
    def _build(self, ...) -> str:                # ✅ sync helper OK
```
