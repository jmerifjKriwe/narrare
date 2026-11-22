---
files:
  - "app/capabilities/**/*.py"
  - "app/kernel/**/*.py"
  - "!**/tests/**"
  - "!**/e2e/**"
  - "!app/kernel/testing/**"
  - "!app/kernel/db/migrations/**"
---

# Every read and write of user-owned data is narrowed to the requesting user

Standing rule 4 in `docs/_shared/CONSTRAINTS.md`: every user-owned row carries
`user_id`, and data access goes through the scoped repository base
(`ScopedRepository` in `app/kernel/db/base.py`).

Today the app runs as one fixed local user (`LOCAL_USER_ID` in
`app/kernel/auth/__init__.py`). So a query that forgets the user predicate
returns the same rows in every test and every E2E, and nothing goes red. The
leak shows up only when a second tenant exists, after the hosting model
changes. SECURITY.md promises that the scoping is already enforced for that
day. This check stands in for the test that cannot exist yet.

## What breaks the requirement

- A new table that holds data a user can see subclasses `Base` instead of
  `UserOwned`, or declares its own `user_id` column without the
  `users.id` foreign key with `ondelete="CASCADE"`.
- A statement over a `UserOwned` model that is built with a bare `select(...)`,
  `update(...)`, `delete(...)` or a join, and does not start from
  `self.query()`, use `self.owned()` or carry `<Model>.user_id == self.user_id`.
  Every user-owned table in the statement needs the predicate, joined tables
  included.
- `session.get(Model, id)` on a user-owned model. It loads by primary key alone.
- A parent id that arrives from the request (`novel_id`, `chapter_id`,
  `entity_id`, `profile_id` …) is used to create or attach a row without
  first checking that the parent belongs to this user, and, where it applies,
  to the novel in the path. Otherwise a row can be created under another
  user's novel.
- A new row of a user-owned model created without `user_id=self.user_id`, or
  with a `user_id` taken from the payload instead of `current_user_id()`.
- A router or service that takes the user from anywhere other than the
  `current_user_id` dependency, or builds a repository for a fixed user.
- A missing or foreign row answered differently, for example a 403 for foreign
  and a 404 for absent. The convention is that a foreign row reads as missing
  (`NotFoundError`, a 404), so an id's existence never leaks.

## What satisfies it

Queries start from the scoped base or carry the predicate explicitly. A parent
from the path is resolved through a `require_*` lookup that is narrowed to the
user. Every bulk `delete`/`update` filters on `user_id`. Where the statement
targets a row the caller named and an absent row is an error, such as deleting
a scene by id, a rowcount of 0 raises `NotFoundError`. Where an empty set is
valid, a rowcount of 0 is fine: `_Scenes.replace_for_chapter` in
`app/kernel/interchange/engine.py` may delete no scenes from a chapter that has
none, and the scoped updates in `touch_exported` and the `renumber` methods of
`app/capabilities/writing/repository.py` need no existence error.

Some code legitimately acts without a requesting user, and is not a finding:

- The job runtime: the worker claiming and reclaiming `Job` rows by id
  (`app/kernel/jobs/worker.py`), and `reset_stuck_running` in
  `app/kernel/jobs/runtime.py` requeueing stale running `Job` rows of every
  user at startup and during periodic recovery.
- Setup's first-run transaction, `SetupService.complete` in
  `app/capabilities/setup/service.py`: checking for and creating the local
  user, creating the first novel through
  `NovelRepository(self.session, LOCAL_USER_ID)` or importing a demo archive
  for `LOCAL_USER_ID`, and reading the imported novel back with
  `session.get(Novel, report.novel_id)` in the same transaction.
- Migrations.

That is fine as long as setup acts only for `LOCAL_USER_ID`, and the work a
job handler then does for a job stays inside that job's `user_id`.

## Example

Incorrect: the chapter from the path is trusted, and the scene can land under
another user's chapter.

```python
async def create(self, novel_id: UUID, chapter_id: UUID, changes: dict[str, Any]):
    scene = ScenePlan(user_id=self.user_id, chapter_id=chapter_id, **changes)
    self.session.add(scene)
```

```python
chapters = await self.session.scalars(
    select(Chapter).where(Chapter.novel_id == novel_id)  # no user predicate
)
```

Correct, as `app/capabilities/planning/repository.py` does it:

```python
async def require_chapter(self, novel_id: UUID, chapter_id: UUID) -> Chapter | None:
    return await self.session.scalar(
        select(Chapter).where(
            Chapter.id == chapter_id,
            Chapter.novel_id == novel_id,
            Chapter.user_id == self.user_id,
        )
    )
```

and as `app/capabilities/writing/service.py` deletes:

```python
result = await self.session.execute(
    delete(Scene).where(Scene.id == scene_id, Scene.user_id == self.user_id)
)
if getattr(result, "rowcount", 0) == 0:
    raise NotFoundError
```

When you report a finding, name the statement and the model it reads or
writes, and say which row of which user it could reach.
