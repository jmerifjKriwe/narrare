<!-- Source: docs/development/skills-index.md | Priority: high | Maintained by: Documentation Specialist -->

# Skills Index — Inventory, Ownership & Navigation

> **Purpose**: Single source of truth for *which skill exists where, who owns
> it, and which one to reach for*. Resolves the "which skill greift?" ambiguity
> by documenting the three independent skill sources and the (intentional)
> overlaps between them.
>
> **Audience**: Agent authors, reviewers, and anyone adding or referencing a
> skill. Read this before creating a new skill directory or assuming two
> same-sounding skills are duplicates.
>
> **Scope**: This document is an index/navigation aid only. It does **not**
> duplicate skill content — the authoritative description of each skill lives in
> its own `SKILL.md`.

---

## 1. The three skill sources

Narrare environments expose skills from three independent locations. They differ
in **ownership** and **purpose**, not in mechanics — all three are loaded the
same way by opencode.

| Source | Location (relative to repo) | Owner | Nature |
|--------|------------------------------|-------|--------|
| **Project skills** | `.agents/skills/<name>/` | Narrare (this repo) | Project-specific & tech-specific canonical skills |
| **Opencode-native skills** | `.opencode/skills/<name>/` | Narrare (wired into the project) | Project-wired tooling skills (CLI, docs lookup) |
| **Superpowers** | `~/.cache/opencode/.../superpowers/skills/<name>/` (third-party plugin, **outside the repo**) | Upstream `obra/superpowers` | Generic dev-process methodology (TDD, debugging, planning) — used as-is |

> **Why three sources?** Project skills cover Narrare/stack specifics that no
> generic package provides. Opencode-native skills wrap CLI tools wired into
> this repo's config. Superpowers supplies reusable process discipline that
> applies to any codebase. None of these should be merged into one directory.

---

## 2. Full inventory (38 skills)

`Canonical?` is **yes** for every project- and opencode-owned skill (we control
them). Superpowers skills are **third-party** — used as-is, not project-owned.

### 2.1 Project skills — `.agents/skills/` (22, all canonical)

| Skill | Category | One-line purpose |
|-------|----------|------------------|
| `building-pydantic-ai-agents` | AI agents | Build AI agents with Pydantic AI (tools, structured output, streaming, testing). |
| `commit-context` | Memory (agentmemory) | Trace a file/function/line back to the agent session that produced its commit. |
| `commit-history` | Memory (agentmemory) | List recent git commits linked to agent sessions, filterable by branch/repo. |
| `forget` | Memory (agentmemory) | Delete specific observations or sessions from agentmemory (destructive). |
| `frontend-design` | Frontend / UI | Create distinctive, production-grade frontend interfaces with high design quality. |
| `handoff` | Memory (agentmemory) | Resume the most recent agent session for the current working directory. |
| `logfire-instrumentation` | Observability | Add Pydantic Logfire tracing/observability to an app (Python, JS/TS, Rust). |
| `logfire-query` | Observability | Query/analyze Logfire telemetry: traces, logs, spans, metrics, root cause. |
| `logfire-ui` | Observability | Open Logfire UI pages / live view / Explore in the browser (no query first). |
| `mem0` | Memory (external) | Mem0 Platform SDK for adding persistent memory to AI applications. |
| `recall` | Memory (agentmemory) | Search agentmemory for past observations/sessions/learnings about a topic. |
| `recap` | Memory (agentmemory) | Summarize the last N agent sessions for this project, grouped by date. |
| `remediate-review` | Review (project) | End-to-end remediation of one audit review file (`_audit/results/**`). |
| `remember` | Memory (agentmemory) | Explicitly save an insight/decision/learning to agentmemory long-term storage. |
| `session-history` | Memory (agentmemory) | Show what happened in recent past sessions on this project. |
| `shadcn` | Frontend / UI | Manage shadcn/ui components and projects (add, fix, style, compose). |
| `tailwind-design-system` | Frontend / UI | Build scalable design systems with Tailwind CSS v4, tokens, variants. |
| `vercel-composition-patterns` | Frontend / UI | React composition patterns that scale (compound components, context, DI). |
| `vercel-react-best-practices` | Frontend / UI | React/Next.js performance optimization rules from Vercel Engineering. |
| `vercel-react-native-skills` | Frontend / UI | React Native/Expo best practices for performant mobile apps. |
| `vercel-react-view-transitions` | Frontend / UI | Smooth animations via React's View Transition API (`<ViewTransition>`). |
| `web-design-guidelines` | Frontend / UI | Review UI code for Web Interface Guidelines compliance. |

### 2.2 Opencode-native skills — `.opencode/skills/` (2, all canonical)

| Skill | Category | One-line purpose |
|-------|----------|------------------|
| `context7` | Dev tooling | Retrieve up-to-date library/framework docs via the Context7 API. |
| `task-management` | Dev tooling | Task-tracking CLI: feature subtasks with status, dependencies, validation. |

### 2.3 Superpowers — third-party plugin (14, used as-is)

| Skill | Category | One-line purpose |
|-------|----------|------------------|
| `brainstorming` | Process | Explore intent, requirements & design before any creative/implementation work. |
| `dispatching-parallel-agents` | Process | Run 2+ independent tasks with no shared state or sequential dependencies. |
| `executing-plans` | Process | Execute a written implementation plan in a separate session with checkpoints. |
| `finishing-a-development-branch` | Process | Decide how to integrate completed work (merge, PR, cleanup). |
| `receiving-code-review` | Process | Receive review feedback with technical rigor before implementing suggestions. |
| `requesting-code-review` | Process | Verify completed work meets requirements before merging. |
| `subagent-driven-development` | Process | Execute implementation plans with independent tasks in the current session. |
| `systematic-debugging` | Process | Systematic approach to any bug/failure/unexpected behavior before fixing. |
| `test-driven-development` | Process | Write tests before implementation code (rigid discipline). |
| `using-git-worktrees` | Process | Ensure an isolated workspace (native tools or git worktree) for feature work. |
| `using-superpowers` | Process | How to find/use skills; invoke a relevant skill before any response. |
| `verification-before-completion` | Process | Run verification commands & confirm output before claiming work complete. |
| `writing-plans` | Process | Turn a spec/requirements into a multi-step plan before touching code. |
| `writing-skills` | Process | Create, edit, and verify skills work before deployment. |

---

## 3. Ownership rules

When adding or changing a skill, place it in the source whose **owner** matches
who should maintain it:

1. **`.agents/skills/`** → *project-specific canonical skills*. Put a skill here
   when it encodes Narrare/tech-stack specifics (pydantic-ai, mem0, logfire,
   vercel-*, shadcn, the agentmemory suite, the `_audit` remediation workflow).
   We own and version it with the repo.
2. **`.opencode/skills/`** → *opencode-native project-wired skills*. Put a skill
   here when it wraps a CLI/tool that this repo's opencode config wires up
   (`context7` docs lookup, `task-management` task CLI). Owned by the repo.
3. **Superpowers** → *third-party generic dev-process skills* (TDD, debugging,
   planning, code review). **Do not project-own these.** Consume them as-is;
   if you need different behavior, write a project skill rather than forking.

**Rule of thumb:** if the skill is generic dev process → it belongs upstream in
superpowers, not duplicated here. If it is Narrare- or stack-specific → it
belongs in `.agents/skills/` (or `.opencode/skills/` if it is a wired CLI).

---

## 4. Overlaps & aliases (no removal needed)

There are **no harmful exact-name duplicates** across the three sources — every
skill name is unique to its source. The overlaps that exist are *intentional,
complementary facets*, not redundancies. They are documented here as aliases so
reviewers need not treat them as a problem.

### 4.1 The agentmemory cluster (`.agents/skills/`)

Eight skills operate on one backend — the **agentmemory** long-term memory store
(wired via `.mcp.json`). They differ by *direction of operation*, forming a
coherent CRUD/lookup suite:

| If you want to… | Use |
|-----------------|-----|
| Search past observations/sessions by topic | `recall` (the canonical read/search entry point) |
| Save an insight/decision for later | `remember` (write) |
| Delete observations/sessions | `forget` (destructive) |
| See a date-grouped rollup of recent work | `recap` |
| List recent sessions with highlights | `session-history` |
| Find which session produced a specific code location | `commit-context` |
| List commits linked to sessions (branch/repo filter) | `commit-history` |
| Resume the most recent session for this repo | `handoff` |

These are **not** duplicates: `recall` ≠ `remember` (read vs write), `recap` ≠
`session-history` (aggregate vs raw list), `commit-context` ≠ `commit-history`
(one location vs a commit list). Keep all of them.

> **Review-03 note:** earlier review flagged "`handoff` vs Superpowers-handoff"
> and "`task-management` vs Superpowers-task-management" as overlaps. These are
> **stale**: current Superpowers ships *neither* `handoff` nor a
> `task-management` skill. There is no conflict to resolve.

### 4.2 `task-management` vs Superpowers planning skills

Not duplicates — different layers:

- `.opencode/skills/task-management` = a **task-tracking CLI** that *persists*
  feature subtasks (status, dependencies, validation state). It is a tool.
- Superpowers `writing-plans`, `executing-plans`,
  `subagent-driven-development`, `dispatching-parallel-agents` = **process
  methodology** describing *how* to plan and execute work.

They compose: use the Superpowers process to decide the approach, then use
`task-management` to record and track the resulting tasks.

### 4.3 Other adjacent-but-distinct pairs

| Pair | Distinction |
|------|-------------|
| `handoff` (project) vs `using-git-worktrees` (superpowers) | `handoff` resumes an agent **memory** session; worktrees isolate a **git** workspace. |
| `remediate-review` (project) vs `requesting-code-review` / `receiving-code-review` (superpowers) | `remediate-review` drives the Narrare `_audit/results/**` pipeline end-to-end; the Superpowers pair governs the *interaction discipline* of a code review. |
| `verification-before-completion` (superpowers) vs `remediate-review` (project) | Generic "prove it works before claiming done" vs the audit-remediation pipeline. |
| Frontend cluster (`frontend-design`, `tailwind-design-system`, `shadcn`, `vercel-composition-patterns`, `vercel-react-best-practices`, `vercel-react-view-transitions`, `vercel-react-native-skills`, `web-design-guidelines`) | Each covers one facet: aesthetics, design system, component CLI, composition architecture, perf, animation, mobile, compliance review. Complementary. |

**Conclusion:** no skill directory should be removed or renamed. The overlaps
are by design. Removing one risks breaking agent references (skills are invoked
by name); documentation is the agreed resolution.

---

## 5. How to choose / where to find a skill

1. **Need a Narrare or stack-specific capability?** Look in
   `.agents/skills/` first (§2.1).
2. **Need a wired CLI tool (docs lookup, task tracking)?** Look in
   `.opencode/skills/` (§2.2).
3. **Need generic dev-process discipline (TDD, debugging, planning, review)?**
   Use the Superpowers skill as-is (§2.3) — do not re-implement it locally.
4. **Unsure if two skills overlap?** Check §4 before assuming a duplicate.
5. **Adding a new skill?** Follow the ownership rules in §3 and add a row to the
   relevant table in §2 in the same change. See `how-to-add-an-agent.md` for the
   broader agent-authoring workflow.

> **Pointer for orchestrators:** the root `AGENTS.md` lists the five
> orchestrator-facing `/slash` command skills (`check-constraints`,
> `explore-codebase`, `review-changes`, `debug-issue`, `refactor-safely`).
> Those are command-style skills distinct from the inventory above; this index
> covers the `SKILL.md` skill directories across the three sources.
