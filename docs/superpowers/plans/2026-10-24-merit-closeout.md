# Merit Closeout Implementation Plan (rounds A+B and every parked item)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land every parked finding (all 18) plus the merit rounds that carry them: the knowledge surface completion (round A — passage-reaching dock search, honest queue states, manual entity CRUD) and consistency checking as the second durable job kind (round B — the trigger the JobStatus-copy and marker-vocabulary parks wait for). The PR follows only after all of it, per the user's binding decision of 2026-10-24 ("Voll-Abschluss A+B").

**Architecture:** Six tasks on file-ownership lines: two craft batches (registry/test edges; editor/chat hardening), two knowledge-surface features (search + honest states; manual CRUD), and the consistency pair (backend with the kernel purpose-marker vocabulary; frontend with the kind-aware JobStatus). Consistency checking lives inside the knowledge capability — its findings are knowledge about the text, its prompt is grounded on accepted entities, and the Wissen dock is the surface. No new capability, no new dock, no cross-capability import.

**Tech Stack:** as landed (phases 1–6 + cleanup).
**Spec:** `docs/superpowers/specs/2026-10-22-frontend-design.md` (§5.6, §5.9, §5.11, §9 D10/D14); architecture spec §11 (the merit criterion — this plan is the round's answer: each surface here earns its keep on a working kernel).
**Base:** branch `frontend-foundation` @ 79133d07. Execute on a new branch `merit-closeout` from it.

## Global Constraints

- Pre-decided scope ONLY (the parked ledger + the two rounds as tasked); anything else found en route gets parked in the ledger, not fixed.
- English everywhere; user-visible text only via all three catalogs together (de du-form).
- All standing contracts: tolerant validateSearch (output never carries `dock`), dockRoutes conventions, RAC only in `web/ui/`, ghost seam, at-least-once handler contract (single terminal commit; handlers idempotent or committing once — the reference is `extract_entities`).
- E2E real stack; `assert_accessible(page)` ends every new/changed flow; editor component tests zero mocks (scripted bytes only at the network boundary).
- Conventional commits; `feat`/`fix` carry a real `User-visible:` line; `--no-verify` forbidden; `just` recipes only; generate stays drift-free.

## Review Focus

1. **The PURPOSE marker retires the phrase sniff** — prompts declare their purpose in a marked line (`PURPOSE: <job kind>`), the fake branches on it, chat prompts (no purpose line) keep byte-identical behavior, and the extraction E2E stays green without content changes.
2. **Findings review is exactly-once** — the `locked()` concurrency proof mirrored for acknowledge/dismiss.
3. **JobStatus speaks per kind** — the extraction done-copy text stays unchanged (existing assertions prove it); an unknown kind shows itself raw (the drift default).
4. **Dedupe is pending-only** — a re-run after an outage stacks nothing; a re-run after accept still files a fresh suggestion (documented and pinned).
5. **CRUD is keyboard-reachable and announced**; rows stay user-scoped through the repository base; merge keeps the target and deletes the source.
6. **The new handler honors at-least-once** — one terminal commit; a re-run dedupes pending findings.

---

### Task 1: Craft batch A — registry drift and the suite's sharp edges

**Files:**
- Modify: `app/api/test_capability_views.py` (drift test: regenerate into a temp location and compare against the committed `web/lib/generated/{routes,docks}.ts}` views — the committed files ARE the contract; fix the stale "five views" docstring while there; sharpen the duplicate-path guard's assertion to match the capability list, not the substring the path already contains)
- Modify: `app/capabilities/chat/e2e/test_chat_e2e.py` or the writing e2e arrangement (pin the tolerant external `?dock=chat` parse end to end: navigate to `/novels/$id?dock=chat` → the workspace renders, the dock opens by its route, and the URL carries no `dock=` after normalization)
- Modify: `app/capabilities/knowledge/e2e/test_knowledge_dock_e2e.py` (robustness pass on the two timing windows: the done-window race before `stop_api()` and the `to_have_count(0)` milliseconds window — restructure so a job that completed in the window costs a retry round, not a flake)
- Modify: `app/capabilities/knowledge/jobs.py` (`_refuse` message: keep the repr truncation but carry the item's true length, so a clipped over-long name stays diagnosable)
- Modify: `app/capabilities/knowledge/tests/test_extraction.py` (`_enqueue_extraction` docstring: "Every test expecting the 202" — one word)

Mostly pins by nature (drift, parse tolerance, guard sharpening); red-able: the `_refuse` length assertion. Name which is which in the report.

- [ ] **Step 1: Red where possible** (the `_refuse` length; the rest are pins — state it). Run, capture.
- [ ] **Step 2: Implement** all five.
- [ ] **Step 3: Green** — `just test`, `just test-e2e`, `just check`, `just generate` drift-free.
- [ ] **Step 4: Commit**

```
test(web): pin the generator's drift and sharpen the suite's edges

The generated routes and docks views gain a drift test against the
committed files, the duplicate-path guard asserts the capability
list instead of a substring the path already contains, and the
tolerant external ?dock= parse is pinned end to end: the URL
normalizes and the dock still opens. The knowledge E2E's two
timing windows get their robustness pass, and the refusal message
carries a clipped item's true length.

User-visible: none.
```

### Task 2: Craft batch B — the editor's honest announcements and a clean abort guard

**Files:**
- Modify: `app/capabilities/writing/web/ChapterEditor.tsx` (the failure announcement fires only when the failed stream's ghost is the visible one — the ownership check; the `!response.ok` continuation path announces `editor.ghostFailed` instead of nothing)
- Modify: `app/capabilities/chat/web/ChatPanel.tsx` (the finally-cleanup nulls the controller only when it is still its own: `if (askAbort.current === controller)`)
- Modify: `app/capabilities/writing/web/ChapterEditor.test.tsx` (assert the Esc keyCode as the literal 27, not equality between two possibly-empty readings; `clearAnnouncer()` from `@react-aria/live-announcer` in afterEach so baselines never count expiring nodes)
- Modify: `app/capabilities/chat/web/ChatPanel.test.tsx` (the guard's most honest reachable witness — if the second-ask path stays UI-unreachable, test the guard directly and say so)

- [ ] **Step 1: Red** — ownership announce, `!response.ok` copy, keyCode 27, guard. Run, capture.
- [ ] **Step 2: Implement** the five items (two behavior, three test-infrastructure/hardening).
- [ ] **Step 3: Green** — `just test-frontend`, full `just test-e2e`, `just typecheck`, `just build`.
- [ ] **Step 4: Commit**

```
fix(writing): a failed ghost announces its own truth

The failure announcement fires only when the failed stream's ghost
is the one on screen, and a refused continuation request announces
the failure instead of nothing. The test arrangement clears its
live region between cases and pins the Esc keyCode literally, and
the chat abort's cleanup no longer discards a future ask's
controller.

User-visible: screen readers hear a failure as a failure — and
only when the failure is theirs.
```

### Task 3: The Wissen dock's search reaches passages; the queue speaks up

**Files:**
- Modify: `app/capabilities/knowledge/web/EntitiesPanel.tsx` (the search box gains a second tier: a debounced server query to `POST /api/knowledge/search` renders a passages block — document title + text — under the entity list while the query is non-empty; the instant client-side entity filter stays; a failed search query shows a named error, not silence)
- Modify: `app/capabilities/knowledge/web/ExtractionPanel.tsx` (the pending-suggestions query gains the error state — same shape as the entities panel, distinct copy; a dead poll no longer leaves a stale "queued" row beside the failure alert: the alert is the truth, a row promising progress it cannot show is not)
- Modify: `app/capabilities/knowledge/service.py` + `repository.py` (pending dedupe: `create_many` skips a parsed entity whose (chapter_id, name, kind) is already pending — a re-run after an outage stacks nothing; after accept the old row is consumed, so a re-run still files fresh — document and pin both)
- Modify: `web/lib/query.ts` (the search query hook + debounce, only as needed)
- Modify: `i18n/{en,de,fr}.json` (queue-error key, passages block key(s), search-error key — ×3, de du-form, distinct copies per the two-outages-nameable-apart precedent)
- Modify: `app/capabilities/knowledge/e2e/test_knowledge_dock_e2e.py` (outage masks nothing: `stack.stop_api()` → the queue names the outage, not emptiness; dedupe pin: enqueue twice on one chapter → one card set; passage search: seed a document through the API, type the query, assert the passage with its document title — and the error state on outage)

- [ ] **Step 1: Red** — the three E2E flows. Run, capture.
- [ ] **Step 2: Implement** the panels, the dedupe, the search tier.
- [ ] **Step 3: Green** — knowledge E2E module, full suite, `just check`, `just build`, typecheck.
- [ ] **Step 4: Commit**

```
feat(knowledge): the dock's search reaches passages

The review queue names an outage instead of masking it as an empty
queue, a dead poll no longer leaves a queued row promising progress
it cannot show, and re-running an extraction stacks no duplicate
pending suggestions. The dock's search box now queries the semantic
search: passages surface with their documents beside the entities.

User-visible: the Wissen dock finds passages, not just names, and
its failures speak up.
```

### Task 4: Manual entity CRUD — rename, delete, merge

**Files:**
- Modify: `app/capabilities/knowledge/router.py` (`PATCH /api/knowledge/entities/{id}` — name/kind/description, validated like the parse contract; `DELETE /api/knowledge/entities/{id}`; `POST /api/knowledge/entities/{id}/merge` with `{target_id}` — target survives, source is deleted; 404s scoped through the service, 422 on a self-merge)
- Modify: `app/capabilities/knowledge/service.py` + `repository.py` + `schemas.py` (the three operations; entity rows have no referents — suggestions are self-contained copies — so delete is a row delete and merge is delete-plus-keep; document that in the service docstring)
- Modify: `app/capabilities/knowledge/web/EntitiesPanel.tsx` (the detail view gains edit (TextField/ComboBox form), delete (confirm dialog), merge (target picker over the novel's other entities) — keyboard-reachable, every outcome announced, list reflects each change)
- Modify: `i18n/{en,de,fr}.json` (the CRUD key family ×3)
- Modify: `app/capabilities/knowledge/e2e/test_knowledge_dock_e2e.py` (rename shows the new name; delete leaves it gone; merge leaves the target and not the source; keyboard-only for at least one flow; `assert_accessible(page)` everywhere)

- [ ] **Step 1: Red** — the three flows. Run, capture.
- [ ] **Step 2: Implement** endpoints + panel.
- [ ] **Step 3: Green** — knowledge E2E module, full suite, check, build, typecheck.
- [ ] **Step 4: Commit**

```
feat(knowledge): entities can be corrected by hand

Rename, delete and merge land in the Wissen dock's detail view: a
typo no longer lives forever, and two entries for the same thing
fold into one. Every action is reachable from the keyboard and
announced, and the entity list reflects each change at once.

User-visible: your knowledge base is finally editable.
```

### Task 5: Consistency checking as the second job kind — the backend

**Files:**
- Modify: `app/kernel/llm/contract.py` (`PURPOSE_PREFIX = "PURPOSE: "` beside `SOURCE_PREFIX`)
- Modify: `app/kernel/llm/fake.py` (branch on the marked purpose line: `extract-entities` → the existing derivation; `check-consistency` → the contradiction derivation below; no purpose line → today's behavior unchanged. The `JSON array` phrase sniff retires — both JSON prompts are marked now. The passage assembly reads ALL `SOURCE:` lines (extraction has one, consistency has N). The contradiction derivation: names paired with different numbers across the source (e.g. "Mira ist 34" / "Mira ist 37") yield one finding per name quoting both readings — deterministic, content-derived, steerable by test text)
- Modify: `app/kernel/tests/` llm tests (purpose branching: both kinds, the unmarked default, multi-source assembly; the phrase sniff's removal pinned)
- Modify: `app/capabilities/knowledge/prompts.py` (the extraction prompt carries `PURPOSE: extract-entities`; new `consistency_prompt`: instruction — contradictions of age, date, timeline, name or fact across the chapters; answer a JSON array of `{"summary": string, "detail": string}`, empty valid — then the accepted entities as grounding (names + kinds), then every chapter as `Chapter: {title}\nText:\nSOURCE: {body}`)
- Modify: `app/kernel/contracts/models.py` (`ConsistencyFinding`: user_id, novel_id, summary String(200) — length-checked at parse, mirroring `MAX_NAME_LENGTH`; detail Text nullable; status pending|acknowledged|dismissed; created_at)
- Modify: `app/capabilities/knowledge/jobs.py` (`KIND_CHECK = "check-consistency"`; `parse_findings` with the same defensive shape as `parse_entities`; `check_consistency` handler: read all the novel's chapters scoped to the job owner + the accepted entities, prompt, parse, file pending findings with summary-dedupe (a re-run stacks nothing pending), progress 100, one terminal commit)
- Modify: `app/capabilities/knowledge/repository.py` + `service.py` + `router.py` + `schemas.py` (`POST /api/knowledge/consistency/{novel_id}` → 202 `{job_id}`; `GET /api/knowledge/novels/{id}/findings?status=`; `POST /api/knowledge/findings/{id}/acknowledge` and `/dismiss` — exactly-once via the `locked()` pattern, 409 on reviewed)
- Modify: `app/capabilities/knowledge/tests/` (parse refusals incl. over-long summary; empty array; enqueue 202; exactly-once ack/dismiss under real concurrency — mirror the suggestion proof; cross-restart durability — mirror the extraction proof; findings dedupe)

- [ ] **Step 1: Red** — the parse/prompt/branching tests first. Run, capture.
- [ ] **Step 2: Implement** the vocabulary, the handler, the model, the endpoints.
- [ ] **Step 3: Green** — kernel + knowledge tests, `just test`, `just check`, typecheck.
- [ ] **Step 4: Commit**

```
feat(knowledge): consistency checking as the second job kind

A whole-novel check reads every chapter plus the accepted
entities and files its findings as reviewable rows — the second
durable job kind on the lane extraction proved. The prompt marker
vocabulary becomes real: prompts declare their purpose in a marked
line, the provider fake branches on it, and the JSON-phrase
sniffing retires.

User-visible: none (the findings surface lands with the next
commit).
```

### Task 6: The findings surface and the kind-aware JobStatus

**Files:**
- Modify: `app/capabilities/knowledge/web/ChecksPanel.tsx` (new: the novel-wide check trigger beside extraction's chapter trigger — disabled while a check runs, the same single-shot rule; JobStatus for the check job; the findings queue as ProposalCards — acknowledge and dismiss)
- Modify: `app/capabilities/knowledge/web/dock.tsx` (compose the third section; nothing else moves)
- Modify: `web/lib/query.ts` (`useFindingsQuery`, acknowledge/dismiss mutations with invalidation, the check-enqueue mutation)
- Modify: `web/ui/JobStatus.tsx` + `web/ui/JobStatus.test.tsx` (kind-aware: `job.kind` maps to `{done i18n key, result count key}` — extraction's copy text stays byte-identical under its new key; the check kind reads `result["findings"]`; an unknown kind keeps the raw drift default)
- Modify: `i18n/{en,de,fr}.json` (the per-kind done copies, the findings family ×3)
- Modify: `app/capabilities/knowledge/e2e/test_knowledge_dock_e2e.py` (the planted contradiction: two chapters give a name two different ages → run the check → the finding arrives as a card → acknowledge one, dismiss another → the kind-aware done copy shows the count → polling provably stops → `assert_accessible(page)`)

- [ ] **Step 1: Red** — the E2E flow + the JobStatus kind cases. Run, capture.
- [ ] **Step 2: Implement** the panel, the queries, the JobStatus map.
- [ ] **Step 3: Green** — knowledge E2E module, full `just test-e2e`, `just test-frontend`, check, build, typecheck, generate drift-free.
- [ ] **Step 4: Commit**

```
feat(knowledge): findings review, and JobStatus speaks per kind

The Wissen dock gains the findings queue: acknowledge or dismiss
each finding as a review card, with the job's progress beside it.
JobStatus stops hardcoding the extraction's result — each job kind
names its own outcome, and an unknown kind shows itself raw.

User-visible: the novel's continuity findings arrive beside the
text, reviewable in two clicks.
```

---

## Interfaces

- `POST /api/knowledge/consistency/{novel_id}` → 202 `{"job_id"}`; `GET /api/knowledge/novels/{id}/findings?status=pending|acknowledged|dismissed`; `POST /api/knowledge/findings/{id}/acknowledge|dismiss` → 409 when already reviewed (mirrors the suggestion contract).
- `PATCH /api/knowledge/entities/{id}` (name/kind/description), `DELETE /api/knowledge/entities/{id}`, `POST /api/knowledge/entities/{id}/merge` `{"target_id": uuid}` (422 on self-merge).
- `PURPOSE_PREFIX = "PURPOSE: "` (kernel llm contract); the purpose value is the job kind; one marked purpose line per prompt, N marked source lines.
- `ConsistencyFinding` pending-identity is the summary; suggestion pending-identity is (chapter_id, name, kind).
- `Job.kind` is already on the API row — JobStatus maps kind → {done key, result count key}; the drift default stays.

## Self-review notes

Scope = the parked ledger exactly (16 directly; the 2 second-job-kind parks resolve across Tasks 5–6) + round A's remainder (manual CRUD) + round B whole. Deliberately OUT, with reasons: graph/canvas — needs a relationship model and real usage of the landed surface first (spec §11: a later answer is a decision); notes/wiki, analysis, series, adaptive, templates, import/export, observability, auth/hosting — §11 deferrals, untouched. Observed and left: accept-then-re-extract can file a fresh suggestion for an accepted name (dedupe is pending-only by design — a re-suggestion after acceptance is sometimes right; a product call for later, not this round). Chapters are not in the semantic search — the corpus is documents; the dock search reaches what the endpoint reaches, and widening the corpus is its own merit question.

## Corrections (recorded after execution, 2026-10-25)

- Task 1's drift-test bullet says the test "regenerates into a temp
  location". The shipped test does not: `app/api/test_capability_views.py`
  calls the generator functions in-process (`typescript_routes(ROOT)`,
  `python_registry(...)`, …) and compares their output against the committed
  files. Same contract — the committed files are the contract — reached by a
  different mechanism. The PR #284 review flagged the mismatch (an audit
  trail stating a mechanism the code does not use); the wording above stays
  as written, per the no-retroactive-rewrite rule.
