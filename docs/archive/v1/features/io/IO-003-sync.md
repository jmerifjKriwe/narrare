---
id: IO-003
title: "External Sync"
status: planned
area: io
mvp: false

ui_tooltip: "Sync your manuscript with external folders or cloud storage."
ui_help_short: |
  Keep your Narrare project in sync with an external directory — a cloud folder,
  a Git repository, or a local backup location. Changes flow both ways: edits
  in Narrare appear in your external files, and edits made outside come back in.
ui_help_long: |
  ## External Sync

  Narrare stores your manuscript in its own database for fast search and AI
  features. But many writers also keep files in a cloud folder, a Git repo,
  or a backup drive. External Sync connects these two worlds.

  **How it works:**

  You configure one or more sync targets — a local directory, a cloud storage
  mount, or a Git repository. Narrare watches for changes in both directions:

  - **Narrare → External:** When you save a chapter in Narrare, the
    corresponding file is updated in the sync target.
  - **External → Narrare:** When you edit a synced file outside Narrare,
    the changes are detected and pulled back into the project on the next sync.

  **Conflict handling:**
  When both sides change the same chapter between syncs, Narrare shows a
  diff and asks which version to keep — or lets you merge manually.

  **Use cases:**
  - Back up your manuscript to Google Drive or Dropbox automatically
  - Edit chapters in your preferred offline editor and sync back to Narrare
  - Maintain a Git history of your manuscript for version control
  - Collaborate with a co-author who works in plain text files

  Sync runs on a configurable schedule or on demand. It never deletes files —
  conflicts always surface for manual resolution.
ui_available_in: [dashboard, settings]

service: sync/service.py
contract: ~
router: ~
prompt: ~
requires: [IO-001, IO-002]
---

# IO-003 — External Sync

> **Status:** 📋 Planned — not yet implemented

## What it does

Establishes two-way synchronization between a Narrare project and an external
directory. Edits made in Narrare are exported to the directory; edits made to
files in the directory are detected and imported back. Conflicts are surfaced
for manual resolution. Supports local directories, cloud storage mounts, and
Git-backed targets.

## Why it exists

Narrare's local-first philosophy means the writer's data stays on their machine.
But "local-first" should not mean "locked in." Writers have existing workflows —
cloud backup folders, Git repos for version history, preferred text editors for
certain tasks, or co-authors who work with plain files.

The vision promises the writer owns their data and can take it anywhere. Export
(IO-001) handles one-time delivery. Sync handles the ongoing relationship:
write in Narrare, edit in Vim, back up to Google Drive, review on a tablet —
all without manually copying files back and forth.

## How it works (User perspective)

1. Open Settings → Sync and click "Add Sync Target"
2. Choose the target type: local directory, cloud mount, or Git repository
3. Point to the directory path (or enter the Git remote URL)
4. Map how Narrare chapters correspond to files in the target:
   - One chapter per file (default: `chapter-01.md`, `chapter-02.md`, ...)
   - File naming template (customizable)
   - Format for synced files (Markdown by default, or TXT)
5. Choose sync direction: two-way (default), export-only, or import-only
6. Set sync schedule: on every save, every N minutes, or manual only
7. First sync runs — Narrare matches existing chapters to existing files
8. Review the initial match and confirm

**Ongoing usage:**
- Edits in Narrare automatically push to the sync target (if scheduled)
- External edits are detected on the next sync cycle
- Conflicts appear as notifications with a side-by-side diff for resolution

## How it works (Technical)

**Service:** `SyncService` in `sync/service.py`
**Contract:** `SyncProtocol` in `sync/contracts.py` (to be defined)
**Entry points:**
- `POST /api/v1/sync/targets` — configure a sync target
- `POST /api/v1/sync/run/{target_id}` — trigger sync
- `GET /api/v1/sync/status/{target_id}` — last sync status, conflicts
- `POST /api/v1/sync/conflicts/{conflict_id}/resolve` — resolve a conflict

**Sync engine:**

1. **Change detection** — Track last-synced timestamps per chapter/file pair.
   Detect external changes via filesystem modification time (mtime) or Git
   commit diff. Detect Narrare changes via chapter `updated_at` timestamp.
2. **Export side** — Serialize changed chapters to the target format (Markdown
   by default) using a subset of IO-001's rendering pipeline. Write to the
   target directory with the configured naming template.
3. **Import side** — Parse changed external files using IO-002's parsing
   pipeline. Compare content to current Narrare chapter text.
4. **Conflict detection** — If both sides changed since last sync, flag as
   conflict. Store both versions for diff display.
5. **Conflict resolution** — User chooses: keep Narrare version, keep external
   version, or merge manually in the editor.

**Git target specifics:**
- Uses `gitpython` for commit, diff, and log operations
- Each sync creates a commit with a descriptive message
- Supports branch selection and conflict resolution via Git merge

**Scheduling:**
- Configurable interval via `sync_interval_seconds` in sync target config
- Minimum interval: 30 seconds (prevents rapid-fire syncs)
- Manual trigger always available via the dashboard

## Constraints & Edge Cases

- Sync is eventually consistent, not real-time — there is a configurable
  delay between a change and its reflection on the other side
- Binary formats (DOCX, PDF) are not supported as sync targets; only
  Markdown and plain text formats work bidirectionally
- Renaming a file in the sync target does not automatically rename the
  chapter in Narrare — the mapping must be updated manually
- Sync does not handle KB entities, only chapter text — Knowledge Base
  changes are Narrare-internal
- Cloud storage targets require the folder to be mounted as a local
  filesystem (e.g., via `rclone mount`); Narrare does not include cloud
  API clients
- Git targets require SSH keys or credential helper configured on the host
  machine
- Very large manuscripts may have slow initial sync; subsequent syncs are
  incremental (only changed chapters)
- Sync is paused during active writing sessions to avoid overwriting
  in-progress edits
- No simultaneous sync to multiple targets in one operation — targets
  sync independently
- Deleted files are never automatically deleted in Narrare; deletion
  requires explicit confirmation

## Related Features

- [IO-001](IO-001-export.md) — Manuscript export (used by sync's export side)
- [IO-002](IO-002-import.md) — Project import (used by sync's import side)
- [SETUP-003](../setup/SETUP-003-import.md) — File import (lighter, one-time)
- [SET-002](../settings/SET-002-project-settings.md) — Project settings (sync configuration stored here)
- [WRITE-011](../writing/WRITE-011-volume-management.md) — Volume management (sync operates per volume)
- [WRITE-001](../writing/WRITE-001-editor.md) — Writing editor (source of Narrare-side changes)

## Status & History

- `project-init` — Added to registry as planned feature
