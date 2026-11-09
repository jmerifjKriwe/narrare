# Complexity Seam Refactor — Design

> **Status:** Approved in conversation, 2026-11-09.
> **Type:** Design note for a behavior-preserving refactor.
> **Plan:** `2026-11-09-complexity-seam-refactor-plan.md`.

## Intent

Codacy's complexity metric is a file-level aggregate: the sum of the
cyclomatic complexities of all methods in a file. It therefore flags large
service and component files even when no single method is hard to follow.
This refactor addresses the two things that are real:

1. the four methods that individually exceed a healthy complexity, and
2. the UI files that are too large to hold in context at once.

It does not tune the metric, and it does not split files that have no seam.

## Goals

- Bring `url.resolve`, `writing.service.update_novel`,
  `backup.dump_database` and `migrate.prepare_database` back to a size a
  reviewer can hold in context.
- Split `NovelPage.tsx`, `EntitiesPanel.tsx` and `PromptsPage.tsx` along
  their existing responsibilities.
- Keep every public API, route, schema and i18n key unchanged.
- Keep the existing tests as the behavior proof; add unit tests only for
  newly extracted pure helpers.

## Non-goals

- No Codacy threshold change.
- No service packages or new capability layout.
- No new rule, hook, check script or mandatory document
  (`docs/_shared/CONSTRAINTS.md`, spec §8).
- No attempt to push every kernel file's aggregate below 20. The kernel
  file sums stay high by design; the method hotspots are the target.

## Constraints

- One capability is one folder; imports point `api → capabilities → kernel`;
  a capability never imports another capability.
- Code, tests and developer documentation are English. No new user-visible
  text is introduced, so no catalog change is expected.
- The checkout is shared with other sessions. Before editing a file, check
  `git status` and re-read the file. If it changed since this plan, stop and
  report instead of overwriting another session's work.
- Nothing is committed before the review is green. A commit made through an
  agent ends with `Assisted-by: OpenCode (<model>)` via `git commit --trailer`.

## Approaches Considered

1. **Seam refactor (chosen).** Extract private helpers where one function
   already has distinct stages; split UI files into components and hooks
   along existing state boundaries. Public surfaces stay fixed. Lowest risk,
   reviewable per file.
2. **Structural packages.** Turn `service.py`, `backup.py` or `migrate.py`
   into packages. More file-level metric improvement, but changes import
   paths and makes the kernel's lock/transaction code harder to follow.
   Rejected as too much churn for no behavior gain.
3. **Metric-first splitting.** Cut every flagged file until the aggregate
   drops below the threshold. Produces artificial modules and hides the real
   signal. Rejected.

## Workstream A — Backend method hotspots

| Function | Current | Seam | Target |
|---|---:|---|---:|
| `app/kernel/db/url.py::resolve` | 25 | dev-port parsing, parts reading, port/sslmode validation, URL building | ~8 |
| `app/capabilities/writing/service.py::update_novel` | 25 | pure field normalizers in `writing/metadata.py` | ~6 |
| `app/kernel/db/backup.py::dump_database` | 30 | run the dump, accept the artifact, retain old dumps | ~10 |
| `app/kernel/db/migrate.py::prepare_database` | 24 | take the pre-migration backup, run the bootstrap decision | ~14 |

The helpers stay in their module except the novel metadata normalizers,
which become `app/capabilities/writing/metadata.py` — the same pattern the
capability already uses for `prompts.py` and `jobs.py`.

## Workstream B — UI files

- `writing/web/NovelPage.tsx` → composition root plus `novel/` hooks and
  presentational components: workspace state, draft/autosave/leave guard,
  chapter rail, toolbar, editor column, dock column.
- `knowledge/web/EntitiesPanel.tsx` → list/search/filter/passages remain;
  entity types, detail and the three dialogs move to their own files.
- `prompts/web/PromptsPage.tsx` → page state remains; labels, diff, editor
  and card move to their own files.

## Scope Note: Settings

While this design was being written, PR #755 split the old 746-line
`ProvidersPanel.tsx` into `ProvidersPanel.tsx`, `ProvidersSection.tsx`,
`ModelsSection.tsx`, `TasksSection.tsx` and `ModelState.tsx`. The approved
design named `ProvidersPanel`; that exact file no longer exists in the form
the design described. This plan therefore does not rework the freshly
merged settings UI. If Codacy still flags the new section files after its
next analysis, that is a separate follow-up with its own design.

## Verification

- Per task: `just test-file <path>` plus `just check`.
- Before merge: `just verify all` once, or the four affected capability
  suites in sequence if the full run is too slow.
- No new gate. Complexity is measured with the same local AST count used in
  the analysis; Codacy remains the external confirmation.

## Done Criteria

- The four named methods are below 20 in the local AST count.
- `NovelPage.tsx`, `EntitiesPanel.tsx` and `PromptsPage.tsx` are composition
  roots, not monoliths.
- All existing tests and the affected E2E suites pass.
- No public API, route, schema, generated file or i18n key changed.
