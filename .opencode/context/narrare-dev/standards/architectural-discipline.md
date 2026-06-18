<!-- Context: narrare-dev/standards/architectural-discipline | Priority: critical | Version: 2.1 | Updated: 2026-06-18 -->

# Architectural Discipline Standard

> **Purpose**: Enforce thorough, future-proof implementations. No shortcuts, no
> technical debt, no "we'll fix it later." Every change must be architecturally
> sound and long-term sustainable.
>
> **Audience**: ALL Narrare specialists. This is Tier-1 reading.
>
> **Core Principle**: We build proper solutions. Not quick solutions, not
> "good enough for now" solutions, not "Phase 1 only" solutions. Proper solutions.
> A partial implementation that skips infrastructure is worse than no implementation
> — it creates coupling that's hard to undo and blocks future work.

---

## 0. The Quality Mandate

**Shortcuts are never acceptable.** If the correct solution requires infrastructure,
build the infrastructure. If it requires a migration, write the migration. If it
requires tests, write the tests. If it takes longer — it takes longer.

This is not a preference. This is not a guideline. This is the standard.

| Approach | Verdict |
|----------|---------|
| Correct implementation now | ✅ REQUIRED — always |
| Incremental, where each step is complete | ✅ ACCEPTABLE — each step is fully working |
| "Good enough for now" with TODO | ❌ FORBIDDEN — the TODO becomes permanent |
| Stub that passes tests but lacks real logic | ❌ FORBIDDEN — tests must validate real behavior |
| Skip infrastructure, fake results | ❌ FORBIDDEN — fake results hide real problems |
| "Phase 1 only" without Phase 2 | ❌ FORBIDDEN — Phase 2 never happens |

**Enforcement:** Every specialist must verify their implementation against this
standard before handing off. The coordinator must reject any implementation that
violates it.

---

## 1. Root Cause First

Every change starts with understanding WHY. Symptombekämpfung ist verboten.

**MANDATORY before any implementation:**

1. **Symptom**: What is the observable problem?
2. **Root Cause**: What is the underlying cause? (Ask "why" at least twice.)
3. **Design**: What is the architecturally correct solution that addresses the root cause?

**If you cannot articulate the root cause → HALT and escalate to coordinator.**

### Examples

| Symptom (WRONG fix) | Root Cause (RIGHT fix) |
|---------------------|----------------------|
| "Test fails because mock returns wrong type" → patch the mock | Service contract is underspecified → define proper Protocol |
| "Endpoint returns 500 on null" → add null check | Missing validation layer → add Pydantic schema validation |
| "File too large" → remove comments | Mixed responsibilities → extract focused module |
| "Import error" → add sys.path hack | Module boundary violation → fix the dependency direction |

---

## 2. Architectural Fit Check

"It works" is not sufficient. Every change must fit the existing architecture.

**MANDATORY assessment before implementation:**

1. Does this follow established patterns in the codebase?
2. Is it in the right layer? (core → apps/api → packages/web)
3. Does it follow dependency direction? (RULE-07)
4. Will it compose well with planned features?
5. Does it maintain or improve cohesion of its module?

**If the change doesn't fit → propose the architecturally correct alternative, even if more work.**

---

## 3. Alternatives Considered

Never implement the first idea. At minimum 2 alternatives must be evaluated.

**MANDATORY documentation for every non-trivial change:**

- **Chosen**: What approach was selected?
- **Alternatives**: What else was considered?
- **Rationale**: Why was this approach chosen?
- **Trade-offs**: What was knowingly accepted?

This documentation goes in the specialist's handoff back to the coordinator.

---

## 4. No Workarounds

Workarounds are architectural debt. They are FORBIDDEN unless the user explicitly approves.

**A workaround is anything that:**

- Bypasses an existing abstraction "just to make it work"
- Adds a special case instead of generalizing the pattern
- Uses a hack, TODO, or temporary fix without a concrete plan to resolve
- Circumvents a RULE-XX constraint instead of working within it
- Introduces coupling that will be hard to undo

**When tempted to add a workaround → HALT. Escalate to coordinator. Propose the proper fix.**

---

## 5. Sustainability Check

Every change must be evaluated for long-term viability.

**MANDATORY questions:**

1. Will this solution still be correct when [related planned feature] is added?
2. Does this create coupling that will be hard to undo?
3. Is this the simplest *correct* solution (not the quickest)?
4. Will the next person to touch this code understand the design intent?

---

## Decision Framework

| Approach | Verdict |
|----------|---------|
| Quick fix now + "refactor later" | ❌ FORBIDDEN — the "later" never comes |
| Correct fix now | ✅ REQUIRED |
| Incremental path to correct (with documented steps) | ✅ ACCEPTABLE — each step is a complete, working feature |
| Minimal viable fix + filed architectural debt | ⚠️ Only with explicit user approval |

### 5.1 Streaming is always required (not deferred)

If the backend already supports SSE streaming for an AI feature, the frontend
MUST use SSE as well. REST-only frontend for an SSE-capable backend is:

| Approach | Verdict |
|----------|---------|
| REST-only frontend + "SSE later" | ❌ FORBIDDEN — the SSE infrastructure already exists |
| SSE + REST (REST for data, SSE for AI) | ✅ REQUIRED — matches existing patterns (generation, extend) |

**Rationale:**
- The `connectSSE()` utility is already built and production-tested
- SSE is the core UX pattern for AI interaction — users see streaming output live
- REST-only hides the AI response behind a loading spinner (schlechtere UX)
- Adding SSE later means rewriting components that were built REST-only
- Backend SSE infrastructure without a real frontend consumer is dead code and
  must be either consumed by a real progressive UX or removed

**Existing precedents:**
- WRITE-002/003: SSE for AI generation, REST for CRUD
- WRITE-005: SSE for interactive sessions

---

## 6. Fixing-Treue: Pre-existing Issues werden beim ersten Fund gefixt, nicht analysiert

Wenn ein CI-Gate, Hook oder Check fehlschlägt, gilt ausschließlich:

1. **Fixieren, nicht forschen.** Ob ein Fehler "pre-existing" ist oder in dieser Session
   eingeführt wurde, ist irrelevant. Der Commit ist blockiert → der Fehler wird behoben.
2. **Keine Ursachen-Debatte.** Der Platform-Subagent forscht nicht nach der "root cause"
   eines Lint/Test-Fehlers. Er fixt die Violation an der Fundstelle und macht weiter.
3. **Keine Ausreden.** "Das war schon vorher kaputt" ist keine gültige Rechtfertigung für
   einen fehlgeschlagenen Gate. Kaputt = wird jetzt repariert.
4. **Geschwindigkeit > Eleganz.** Bei einem blockierten Gate ist ein schneller, korrekter
   Fix besser als ein stundenlanges Refactoring. Der perfekte Fix kann im nächsten Commit
   nachgereicht werden.

Diese Regel ist Teil des Architectural Discipline Standards und gilt für ALLE Subagents.
Der Coordinator setzt sie durch. Verstöße sind Prozessverstöße.

---

## 7. Dokumentiert ≠ Implementiert — Verify reality, not claims

**Mandatory for every specialist, especially during review/governance closure.**

Three distinctions that must never be collapsed:

| Tempting shortcut | The truth |
|-------------------|-----------|
| "It's documented" | Documentation describes intent. Verify the code matches the doc. |
| "The template exists" | A file on disk is not "runtime uses it". Trace the load path end-to-end. |
| "The check is green" | A green check covers **only the layer it inspects**. Green ≠ the whole system is correct. |

### Concrete lessons (relearned in CR-04, do not relearn again)

- **FIND-010 / FIND-011:** A governed prompt template sat on disk while the
  service sent an inline f-string; every prompt checker was green because each
  validated one slice and none validated that all slices referred to the same
  file. "Template exists" ≠ "runtime loads it".
- **ADR-037 latent bug:** the manifest checker's AST parser visited only
  `ast.Assign` and silently skipped `ast.AnnAssign` — so the manifest's
  annotated table was never actually validated. "Check is green" covered the
  parser's blind spot, not the manifest.
- **ADR-048 premature reference:** production code cited "ADR-048 Mode 2" while
  ADR-048 was still 🔄 Proposed. A Proposed ADR's contract cannot be relied on
  by production code.

### Mandatory verification protocol

Before marking anything `resolved` / `✅ Implemented` / "done":

1. **Implementation on disk** — point at the files that exist (read them; do not
   trust a claim). See `.opencode/context/narrare-dev/standards/finding-lifecycle.md`.
2. **Enforcement** — name the CI-blocking checker or regression test that
   prevents reintroduction, and the ratchet baseline it set.
3. **Cross-feature integration** — when a change crosses a feature boundary,
   verify the *integration contract* (does the other consumer actually receive
   the data?), not just that each feature passes its own local tests. ADR-050
   exists because feature-local green hid a cross-feature coherence gap.
4. **ADR status discipline** — `✅ Accepted` ≠ `✅ Implemented`. `🔄 Proposed`
   is not a contract you may depend on. INDEX.md and CURRENT_STATE.md reflect
   the more conservative of the two.

**Red flag — stop and escalate:** "We have an ADR for this" used as the entire
evidence that a runtime behaviour is fixed.

---

## Red Flags — Stop and Escalate

If you catch yourself thinking any of these, **STOP**:

- "I'll just add a special case here..."
- "This is a quick fix, we can refactor later..."
- "I know this isn't the right pattern but it works..."
- "This bypasses [abstraction] but just for now..."
- "I'll add a TODO to fix this properly..."
- "This is hacky but it solves the immediate problem..."
- **"Let's start without streaming, we can add SSE later..."** ← ❌ FORBIDDEN
- **"SSE infrastructure exists but let's keep it simple with REST first..."** ← ❌ FORBIDDEN
- **"We'll use REST for now and upgrade to SSE when users complain..."** ← ❌ FORBIDDEN

→ **Any of these is an architectural discipline violation. Escalate to coordinator immediately.**

**Exception:** The ONLY acceptable reason to defer streaming is when the backend
does NOT have streaming infrastructure for that feature yet — AND the coordinator
has approved an incremental path where each step is complete and self-contained.
Even then, the non-streaming implementation must support the same interface
(RULE-13) so streaming can be added without rewriting.

---

## Enforcement

- This standard is Tier-1 for ALL specialists
- Coordinator checks for architectural fit during Propose stage (Stage 4)
- Violations flagged during specialist self-review
- Pattern violations caught during Validate stage (Stage 6)
