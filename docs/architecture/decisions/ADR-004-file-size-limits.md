# ADR-004 — Hard File Size Limits

> **Status:** ✅ Accepted
> **Date:** project-init
> **Deciders:** Architecture Agent
> **Supersedes:** —

---

## Context

`writing/service.py` in the previous codebase reached 1,200+ lines and
contained 8 distinct responsibilities: chapter generation, chapter extension,
rewriting, interactive sessions, multi-draft generation, co-author sessions,
KB-grounding assessment, and prompt building. It was the file with the most
LLM violations, the most f-string prompts, and the most direct API bypasses —
precisely because it was too large to review carefully.

File size is a proxy for responsibility count. Large files are not a style
problem — they are an architecture problem that makes every other problem worse.

## Decision Drivers

- Large files resist review — reviewers skim, miss violations
- Large files accumulate responsibilities — the "just add it here" impulse
- Splitting is easier when it happens early — forced splitting after 1,200 lines
  is a refactor; splitting at 250 lines is a normal code organization task
- AI coding agents (GLM, Claude Code) produce better output on focused files

## Options Considered

### Option A — Hard limits enforced in CI (chosen)
Line count checked by `check_architecture.py`. Build fails if exceeded.
Different limits for different file types.

### Option B — Soft limits (linting warnings only)
Warnings in IDE, not build failures.
**Rejected:** Warnings are ignored. The previous codebase had no limits and
  accumulated 1,200-line files. Only hard enforcement changes behavior.

### Option C — No limits, rely on code review
**Rejected:** Code review catches logical errors; size creep is invisible until
  it's too late. No reviewer says "this PR is fine except the file is now 310 lines."

## Decision

**We choose Option A.**

Hard limits by file type, enforced in CI. Soft targets exist as early warning.
The limits are generous enough not to impede normal development but tight enough
to force splits before files become unmaintainable.

## Consequences

**Positive:**
- Forces early splitting — before responsibilities entangle
- Makes violations visible immediately (CI failure)
- Produces smaller, more focused files that AI agents handle better

**Negative / Tradeoffs:**
- Occasionally a file legitimately needs more lines — requires a split decision
- Some schema files with many fields may hit limits — split by domain group

**Constraints introduced:**
- RULE-04 in `CONSTRAINTS.md`

## Implementation Notes

Limits are read from `pyproject.toml [tool.narrare.architecture]` by
`check_architecture.py`. Changing a limit requires updating pyproject.toml
and adding a DECISIONS.md entry — not just editing the script.

```toml
[tool.narrare.architecture]
file_size_limits = {router = 150, service = 300, repository = 250, default = 400}
```

## Review Trigger

- [ ] If a file type consistently requires exceptions (signal that limit is wrong)
- [ ] After 6 months of active development — assess if limits are appropriate
