# Dispatch and recovery

Applies whenever you dispatch a subagent. The provider's 5-hour usage window can
kill a dispatch mid-flight; the goal is to make that cost at most one task, not
the whole dispatch.

## Carrier

Dispatch subagents with `background: true`. The launch returns the session id
before any work starts. Write that id together with the base commit into the
dispatch progress file in the same turn — chat memory is compacted, the file is
not.

## Commit granularity

Commit after each numbered task, before starting the next. A dispatch that dies
must cost at most one task, and a fresh instance must be able to verify existing
commits instead of rebuilding them.

## On failure

When a subagent or tool call fails, read `git log --oneline <base>..HEAD` and
`git status --porcelain` before deciding anything. Do not reset on reflex.

- Nothing produced (no commits, empty porcelain): dispatch fresh, and say it is
  fresh.
- Commits or edits present: never reset. Resume the same session id with:
  "Your last turn was aborted by the provider, not by the task. The work is
  intact. Verify the existing commits, continue at task N, rebuild nothing."
- A provider limit is not a task failure. No re-brief, no reset, no re-run.

## If the session id is missing

If a foreground dispatch errored and you never saw the id, look it up:
`session.list` shows child sessions with a `parentID` field — filter by your own
session id. The id is discoverable after the fact; the work is not lost.

## Progress file

Each dispatch gets one file (`.opencode/dispatches/<name>.progress`) with at
minimum: base commit SHA, session id, current task number, and the next verify
command. Update it at task start, not at task end — a death leaves the most
recent state on disk.