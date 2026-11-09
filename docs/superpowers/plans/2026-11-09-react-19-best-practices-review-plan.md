# Implementation Plan: React 19 Best-Practices Review

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Review `NovelPage.tsx` and `ChatPanel.tsx` for React 19 anti-patterns, apply
low-risk fixes, document medium/high-risk findings as follow-ups.

**Architecture:** Read-only review pass using the `vercel-react-best-practices` skill
checklist. Findings are triaged by severity and effort; only low-risk/high-value
fixes are applied in this pass.

**Tech Stack:** React 19.3.1, TypeScript, Vite, TanStack Router, TanStack Query.

**Spec:** `docs/superpowers/specs/2026-11-09-react-19-best-practices-review-design.md`

## Global Constraints

- No behavioral changes — all existing tests must pass unmodified.
- No new dependency, no new gate, no new standing rule (CONSTRAINTS §8).
- Changes limited to the two named files (+ shared components only if required).
- English in code/tests/docs.

---

## Task 1: Load the review skill and read the components

**Files:**
- Read: `app/capabilities/writing/web/NovelPage.tsx`
- Read: `app/capabilities/chat/web/ChatPanel.tsx`

**Steps:**
- [ ] Invoke the `vercel-react-best-practices` skill.
- [ ] Read both files end-to-end, noting findings per the checklist in the spec.
- [ ] Record findings in a temporary list (location, severity, description, fix, effort).

## Task 2: Triage and apply low-risk fixes

**Files:**
- Modify: `app/capabilities/writing/web/NovelPage.tsx` (if fixes needed)
- Modify: `app/capabilities/chat/web/ChatPanel.tsx` (if fixes needed)

**Steps:**
- [ ] For each finding rated low-risk/high-value: apply the fix.
- [ ] For each finding rated medium/high-risk: create a follow-up issue
      (`gh issue create --label follow-up --label "area: web"`).
- [ ] Run `just check` and `just test-frontend` after each fix.
- [ ] Run the affected E2E suites to confirm no behavioral change.

## Task 3: Write the findings report

**Files:**
- Create: `docs/superpowers/reports/2026-11-09-react-19-review.md`

**Steps:**
- [ ] Write per-finding: location, severity, description, recommended fix, effort.
- [ ] Include a summary table (finding count by severity).
- [ ] List applied fixes and created follow-up issues.

## Task 4: Verify

**Steps:**
- [ ] `just check` green.
- [ ] `just test-frontend` green.
- [ ] Affected E2E suites green.
- [ ] No test modifications.

## Review Focus

- Fixes must not change any observable behavior.
- Follow-up issues must be one per finding, with `area: web` label.
- The report must be honest about what was found vs. what was fixed.
EOF