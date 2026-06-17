# ADR-028 — Architecture Exception Register: Single Source of Truth

> **Status:** ✅ Accepted
> **Date:** 2026-06-03
> **Deciders:** Architecture Agent, Narrare Dev Coordinator
> **Supersedes:** — (codifies existing practice with corrections)

---

## Context

Architecture exceptions in Narrare are currently maintained in **three parallel sources** with inconsistent content:

1. **`pyproject.toml [tool.narrare.architecture.exceptions]`** — 1 entry (`embedding_providers.py`, RULE-01b)
2. **`CONSTRAINTS.md §7`** — 4 entries (different set: `mem0_client.py`, `gateway.py`, `provider_service.py`, plus in §7 text)
3. **Inline `# narrare: allow` comments** — ~26 approved markers across the codebase (the only source the checker actually reads)

The architecture checker (`scripts/architecture/_checkers/__init__.py`) reads `config["exceptions"]` from `pyproject.toml` but **never uses it** — it relies entirely on inline `# narrare: allow` markers via `is_approved_exception()`.

This creates three concrete problems:

- **No auditability**: There is no way to answer "what exceptions are currently approved?" — CONSTRAINTS.md is out of sync, pyproject.toml is incomplete.
- **No validation**: The checker cannot detect orphaned inline markers (ones without a registered exception) or orphaned registrations (entries without inline markers).
- **No governance**: Adding a new exception requires updating up to three locations, but no tooling enforces consistency.

Single-Source-of-Truth principle (referenced in CONSTRAINTS.md line 56: "Approved exceptions: Listed in `pyproject.toml [tool.narrare.architecture]`") was never fully implemented.

---

## Decision Drivers

- **SSOT principle**: One authoritative source must exist for all architecture exceptions
- **Machine-readability**: The SSOT must be parsable by the architecture checker (tomllib, no YAML/JSON dependency beyond stdlib)
- **Developer ergonomics**: Developers need narrative context for why an exception exists (not just machine data)
- **Auditability**: Must be possible to enumerate all approved exceptions and cross-reference them with inline markers
- **No new files**: Avoid creating yet another configuration file

---

## Options Considered

### Option A — `pyproject.toml` as SSOT (chosen)

`pyproject.toml [tool.narrare.architecture.exceptions]` becomes the authoritative register. Every exception MUST be registered there AND have a matching inline `# narrare: allow` comment in the source file. `CONSTRAINTS.md §7` becomes a narrative reference pointing to `pyproject.toml`.

**Pros:**
- `pyproject.toml` is already the config source for the checker (`load_config()` reads it via `tomllib`)
- `tomllib` is stdlib — no new dependency
- No new file to maintain
- CONSTRAINTS.md remains the human-readable explanation source without duplicating structured data
- Inline markers remain the "runtime" approval at each violation site

**Cons:**
- Existing inline markers (all ~26) must be audited and backfilled into `pyproject.toml`
- Checker must be updated to cross-reference both sources (explicit spec in this ADR)

### Option B — `CONSTRAINTS.md` as SSOT

Keep the exception list as a structured code block in `CONSTRAINTS.md §7` (current state).

**Pros:**
- No migration needed
- Documentation and exception register are co-located

**Cons:**
- Markdown is not machine-parseable without a custom parser
- Violates the existing pattern of `pyproject.toml` being the machine-readable config source
- Would require a tomllib-identical parser for markdown fenced blocks
- The checker already reads config from `pyproject.toml` — fragmenting the config surface is the wrong direction

### Option C — Standalone `exceptions.yaml` or `exceptions.toml`

Create a new file (`docs/architecture/exceptions.toml` or similar) as the SSOT.

**Pros:**
- Clean separation of concerns
- Single responsibility

**Cons:**
- New file with no existing tooling support
- Adds cognitive load ("where do exceptions live?")
- `pyproject.toml` already has the section defined — splitting it out is unnecessary indirection
- The checker's `load_config()` would need to read an additional file

---

## Decision

**We choose Option A: `pyproject.toml [tool.narrare.architecture.exceptions]` is the Single Source of Truth for all architecture exceptions.**

The exception register in `pyproject.toml` is structured TOML, machine-readable by `tomllib`, and already partially populated. Every exception **must** exist in both places:

1. **Registered in `pyproject.toml`** — provides auditability, governance, and a complete list
2. **Inlined in the source file** — provides the runtime signal for the checker

CONSTRAINTS.md §7 transitions from a structured list to a narrative reference. The existing narrative explanation (mem0 exception, lines 879–903) remains — it is valuable developer context that has no place in `pyproject.toml`.

---

## Rationale

- **The checker already reads `pyproject.toml` configuration** — `load_config()` returns `config["exceptions"]` which is currently ignored. This decision makes the checker use what it already has.
- **`tomllib` is stdlib** — no dependency risk, works in CI without extra packages.
- **Dual registration** (both `pyproject.toml` + inline marker) provides two independent signals: governance-level and runtime-level. The checker cross-references them.
- **No new files** — the project already has too many config surfaces.
- **CONSTRAINTS.md stays human-focused** — narratives belong in docs, structured data belongs in config.

The tradeoff accepted: the ~26 existing inline markers need to be audited and backfilled into `pyproject.toml`. This is a one-time cost that establishes correctness going forward.

---

## Consequences

**Positive:**
- Single complete list of all approved exceptions, queryable by `tomllib`
- Checker can validate dual registration (inline marker + pyproject.toml entry)
- New exceptions follow a clear process: add to pyproject.toml + add inline comment
- CONSTRAINTS.md §7 no longer goes stale — it references the SSOT

**Negative / Tradeoffs:**
- Existing inline markers must be audited and registered (effort — but AI does it)
- Checker update required (see Implementation Notes)

**Constraints introduced:**
- All new exceptions MUST be dual-registered (pyproject.toml + inline), enforced by checker UPDATE (documented in this ADR, implemented in AUFG-04-04)
- CONSTRAINTS.md §7 MUST NOT contain structured exception data going forward

---

## Implementation Notes

### Phase 1 — Register sync (this task)

1. Add the 3 missing entries to `pyproject.toml [tool.narrare.architecture.exceptions]`:
   - `packages/core/narrare_core/memory/mem0_client.py` (RULE-01b)
   - `packages/core/narrare_core/llm/gateway.py` (RULE-01b)
   - `apps/api/narrare/setup/provider_service.py` (RULE-01b)
2. Replace structured list in `CONSTRAINTS.md §7` with SSOT reference
3. Keep narrative mem0 exception in CONSTRAINTS.md (developer context)

### Phase 2 — Checker update (AUFG-04-04)

Required behavior for `scan_file()` in `scripts/architecture/_checkers/__init__.py`:

1. **Load `config["exceptions"]`** — the list of `entries` from `pyproject.toml [tool.narrare.architecture.exceptions]` is parsed and indexed by file path.

2. **Cross-validation** — for every inline `# narrare: allow` marker found in a file:
   - Look up the file path in the exceptions index
   - If an inline marker exists but no pyproject.toml entry → emit a **WARNING** (approved_exception with warning flag)
   - If a pyproject.toml entry exists but no inline marker → emit a **WARNING**
   - Both must exist for a clean PASS

3. **Violation suppression** — only inline markers that also have a matching pyproject.toml entry suppress violations (current behavior remains: inline markers suppress violations — but future state is dual check)

4. **Exception entry format** — pyproject.toml entries MUST match exactly:
   ```toml
   [[tool.narrare.architecture.exceptions.entries]]
   rule = "RULE-XX"
   file = "path/from/repo/root/file.py"
   reason = "Why this exception exists"
   approved_by = "who-approved"
   date = "2026-01-01"
   ```

### Inline Comment Format

The `# narrare: allow` comment must follow this format for the checker to validate it against pyproject.toml:

```python
# narrare: allow  reason="Human-readable reason matching pyproject.toml"
```

Variant markers also remain valid:
- `# narrare: allow-agent` — for RULE-01b agent exceptions
- `# narrare: allow-direct-llm` — for RULE-01b LLM client exceptions
- `# narrare: allow-fstring` — for RULE-02 f-string exceptions

All variant markers MUST also have a corresponding pyproject.toml entry.

---

## Review Trigger

- When a new rule is added to CONSTRAINTS.md that requires exceptions
- If the number of exceptions exceeds 50 (scalability concern — consider dedicated exceptions file)
- After 3 months: audit that the checker cross-validation is in place and working

---

## Related

- CONSTRAINTS.md §7 (section updated by this ADR)
- `pyproject.toml [tool.narrare.architecture.exceptions]` (the SSOT)
- `scripts/architecture/helpers.py` (load_config, is_approved_exception)
- `scripts/architecture/_checkers/__init__.py` (scan_file — checker orchestration, target for AUFG-04-04)
- AUFG-04-04 (checker implementation task)
