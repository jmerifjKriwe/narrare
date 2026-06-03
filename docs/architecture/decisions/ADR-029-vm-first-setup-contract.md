# ADR-029 — VM-First Setup Contract and Optional DevContainer Cleanup

> **Status:** Accepted — implemented
> **Date:** 2026-06-03
> **Deciders:** Architecture Agent, Narrare Dev Coordinator
> **Supersedes:** —

---

## Context

This ADR is the architecture/setup cleanup specification for the project setup audit. It documents the contract that Platform has implemented for setup/config cleanup; future changes to the setup contract must continue to satisfy the acceptance criteria below.

The audit found portability and drift issues across DevContainer configuration, VM-first helper commands, CI path filters, duplicate architecture gates, release image naming, package-manager pinning, frontend check mutability, Docker build context hygiene, and deployment/pre-commit docs.

### Problem Statement / Root Cause

The root cause is not one broken file; it is three ambiguous ownership boundaries:

1. **Environment mode ambiguity** — VM-first development and optional DevContainer development are both present, but the repository does not define a single contract for paths, hostnames, tool execution location, and database/Redis URLs per mode. Why does this break? Because setup helpers infer too much from installed tools (`psql`, Docker) instead of explicitly targeting the active mode. Why is inference wrong? Because a VM host and a container can both see tools but require different network names and paths.
2. **Duplicate gate SSOT** — CI and architecture validation exist in multiple workflows with different path filters and gate strength. Why does this break? Because config-only changes can bypass the strongest workflow, while a duplicate weaker workflow gives a false sense of coverage. Why is that possible? Because the blocking gate is not declared as the single CI source of truth for setup/config files.
3. **Derived-doc drift** — deployment, pre-commit, setup, and release docs reproduce command details, dependency versions, and environment defaults instead of referencing canonical sources. Why does this break? Because docs and config evolve independently. Why does that persist? Because there is no rule that derived docs reference SSOT files for setup contract details.

---

## Decision Drivers

- Narrare is currently **VM-first** for development, with DevContainer support optional.
- Setup/config changes must be validated by blocking CI even when no application code changes.
- `docs/_shared/` remains the authoritative documentation layer; derived docs should reference rather than reproduce canonical facts.
- No workaround path is acceptable: mode-specific behavior must be explicit, not inferred from incidental tool availability.
- Platform owns implementation details; this ADR defines the contract and acceptance criteria that the implementation must preserve.

---

## Goals / Non-Goals

### Goals

- Define a sustainable environment mode contract for VM-first and optional DevContainer usage.
- Make setup/config CI coverage explicit and blocking.
- Remove duplicate or stale gate ownership so there is one stronger SSOT for architecture/setup checks.
- Align release image naming between workflow output and release compose input.
- Establish docs SSOT discipline for setup and deployment instructions.
- Require non-mutating check commands and deterministic package-manager versioning.
- Require Docker build context hygiene via `.dockerignore`.

### Non-Goals

- No production code changes in this ADR.
- No new runtime dependencies.
- No redefinition of Narrare's application layer architecture, service-layer contracts, or feature specs.
- No redefinition of the release/versioning strategy beyond aligning the existing release image and compose contract.

---

## Environment Mode Contract

### Mode A — VM-first development (primary)

VM-first is the default development mode.

Expected contract:

- **Repository path:** host filesystem path chosen by the developer; no config may hardcode one user's absolute path.
- **Command execution:** `just` commands run on the VM/host unless explicitly documented otherwise.
- **PostgreSQL access from host helpers:** `localhost` plus the published PostgreSQL port; never implicit Unix socket fallback.
- **Redis access from host helpers:** `localhost` plus the published Redis port.
- **Docker/Compose:** infrastructure services may run in containers, but host helpers must still use host-reachable ports.
- **Tool detection:** installed `psql` and available Docker must not change the selected mode implicitly.

### Mode B — DevContainer development (optional)

DevContainer remains optional and must be portable.

Expected contract:

- **Build context:** relative to the repository, not an absolute host path.
- **Repository mount:** container path is defined by DevContainer configuration, not by a developer-specific host path.
- **PostgreSQL access from inside container:** Docker Compose service DNS name, not `localhost`.
- **Redis access from inside container:** Docker Compose service DNS name, not `localhost`.
- **Environment rewrite:** if DevContainer generates or rewrites `.env`, it must match the credentialed URL shape declared by `.env.example` while replacing only mode-specific hostnames.
- **Optionality:** DevContainer fixes must not make VM-first workflows depend on DevContainer assumptions.

---

## Options Considered

### Option A — VM-first contract with optional DevContainer support (chosen)

Define VM-first as the primary mode and keep DevContainer support as a portable optional mode. Platform implements explicit mode-specific hostnames, path handling, and validation.

**Pros:**
- Matches current project usage and avoids forcing all contributors into containers.
- Fixes root cause by making mode selection explicit.
- Keeps DevContainer useful without letting it define the whole setup contract.
- Supports incremental rollout where each Platform task is complete and validated.

**Cons:**
- Requires maintaining two documented modes.
- Platform must ensure helpers do not infer the wrong mode from available tools.

### Option B — DevContainer-only development

Make DevContainer the canonical development environment and de-emphasize VM-first helpers.

**Pros:**
- Single environment can reduce variance.
- Service DNS hostnames are simpler inside Compose networks.

**Cons:**
- Contradicts current VM-first project direction.
- Would require broader onboarding changes and may make local host workflows harder.
- Does not address release/docs/CI SSOT drift by itself.

### Option C — Leave mode implicit and patch individual symptoms

Fix each audit finding locally without defining a mode contract.

**Pros:**
- Small individual diffs.

**Cons:**
- Recreates the current failure mode: future changes can drift again because ownership is still ambiguous.
- Violates architectural discipline: symptom treatment instead of root-cause resolution.
- Not sustainable in three months.

---

## Decision

**We choose Option A: VM-first is Narrare's primary setup contract; DevContainer support remains optional and must be portable.**

Platform implemented the audit cleanup by making environment mode, CI gate ownership, release image naming, package-manager pinning, Docker context hygiene, and docs SSOT rules explicit. Config-specific details remain Platform-owned, but the resulting behavior must continue to satisfy the contract and acceptance criteria below.

---

## Implemented Changes

### Platform

- Make `.devcontainer/docker-compose.devcontainer.yml` portable by replacing user-specific absolute build context with a repository-relative context.
- Align DevContainer `.env` generation/rewriting with `.env.example` credentialed URL structure while changing hostnames according to container mode.
- Update VM-first `justfile` database/Redis helpers so host mode explicitly targets `localhost` ports and never falls through to local Unix sockets.
- Ensure container-mode helpers use Compose service DNS names.
- Pin pnpm consistently across package metadata, CI, and container/bootstrap scripts; avoid `latest`.
- Split mutating frontend formatting from non-mutating checks: check commands must verify only, while write/fix commands may mutate.
- Add `.dockerignore` for build-context hygiene and secret/cache exclusion.
- Clarify pre-commit comments so they describe actual behavior, including full-run type checks and mutating vs verifying hooks.

### CI

- Expand PR path filters so setup/config-only changes trigger blocking CI. At minimum cover `justfile`, `.devcontainer/**`, Dockerfiles, compose files, workflow files, lockfiles, package-manager metadata, and setup/deployment docs.
- Consolidate architecture/setup gate ownership: `.github/workflows/ci.yml` should be the blocking SSOT unless Platform explicitly chooses a different single owner.
- Retire duplicate `.github/workflows/architecture.yml` so stale/weaker checks, warning-only locale sync, or stale docs paths cannot masquerade as the blocking setup/architecture gate.

### Docs

- Treat `docs/_shared/CONSTRAINTS.md`, `docs/_shared/TECH_STACK.md`, `docs/_shared/CURRENT_STATE.md`, package metadata, and actual command definitions as SSOT depending on topic.
- Update derived setup/deployment/pre-commit docs to reference canonical sources instead of reproducing version numbers or command behavior.
- Correct drift such as Next.js version references, command names, and release bundle `.env.example` expectations.

### Release

- Align release workflow image push name with release compose default image name.
- Document the canonical GHCR owner/repository/image tuple in one place and reference it from release docs/config.
- Resolve release bundle docs/config disagreement about whether `.env.example` already contains Docker service hostnames.

---

## Acceptance Criteria / Definition of Done

Platform implementation is complete only when all criteria are satisfied:

- [x] VM-first mode uses host-reachable `localhost` ports for PostgreSQL and Redis helpers; no Unix socket fallback for `just` DB helpers.
- [x] DevContainer mode uses relative build context and service DNS hostnames for PostgreSQL and Redis.
- [x] DevContainer `.env` rewrite preserves the credentialed URL shape of `.env.example`.
- [x] Config-only PRs touching setup/platform files trigger blocking CI.
- [x] Architecture/setup gate has one blocking SSOT; duplicate workflows are removed, delegated, or made equivalent.
- [x] Release image name pushed by workflow matches release compose default.
- [x] pnpm version is pinned consistently; no `latest` bootstrap remains.
- [x] `just check-frontend` and other `check-*` commands are non-mutating; mutating behavior lives in explicit format/fix commands.
- [x] `.dockerignore` excludes secrets, dependency caches, build outputs, VCS metadata, and local runtime artifacts.
- [x] Derived setup/deployment/pre-commit docs reference SSOT files and no longer contradict current commands or versions.
- [x] Pre-commit comments describe actual hook behavior.

Validation commands:

```bash
just check-architecture
just check
just check-frontend
docker compose -f docker-compose.dev.yml config
docker compose -f docker-compose.dev.yml -f .devcontainer/docker-compose.devcontainer.yml config
docker compose -f docker-compose.release.yml config
```

The repository intentionally has no default `docker-compose.yml`; validation must
name the target topology explicitly. Release compose validation must not require
a committed `.env`, but actual self-hosted deployment still requires users to
copy `.env.example` to `.env` and configure the runtime secrets and provider
keys before `up -d`.

Platform may add more targeted validation commands, but failures must be fixed at the root cause. Do not bypass validation and do not use `git commit --no-verify`.

Implementation validation note (2026-06-03): the three explicit Compose config
commands above passed. The previously unrelated governance blockers found during
ADR-029 validation have since been resolved/revalidated: the frontend RULE-04
blocker was modularized via `useCoAuthorReviewState`, the architecture exception
baseline was revalidated at 17/17, and targeted validation now passes. These were
not root causes of ADR-029 and do not change the setup contract.

---

## Risks and Rollout Order

### Risks

- **Mode regression:** VM-first helpers could accidentally adopt container DNS names. Mitigation: validate host-mode commands separately from DevContainer config.
- **CI cost increase:** broader path filters can run CI on more config-only PRs. Mitigation: acceptable tradeoff; setup changes are high blast-radius and must be gated.
- **Docs churn:** replacing reproduced instructions with SSOT references may require multiple doc edits. Mitigation: reduce future drift by centralizing facts.
- **Release compatibility:** changing image defaults can affect existing local release bundles. Mitigation: document canonical image naming and keep env override behavior explicit.

### Rollout Order

1. **Gate SSOT first:** CI path filters and duplicate architecture workflow ownership, so later setup fixes are validated.
2. **Mode contract fixes:** VM-first helpers, DevContainer build context, and `.env` rewrite.
3. **Determinism and hygiene:** pnpm pinning, non-mutating checks, `.dockerignore`, pre-commit comment accuracy.
4. **Release alignment:** image naming and release `.env.example` expectations.
5. **Docs SSOT cleanup:** deployment/setup/pre-commit docs updated to reference canonical sources.

---

## Consequences

**Positive:**
- Setup behavior becomes predictable across VM-first and DevContainer modes.
- Config-only regressions are caught by blocking CI.
- Release artifacts and docs describe the same image and environment contract.
- Derived docs become less likely to drift from authoritative sources.

**Negative / Tradeoffs:**
- Platform must update several setup surfaces in a coordinated sequence.
- Broader CI path filters may run more often.
- Maintaining optional DevContainer support requires explicit mode-aware validation.

**Constraints introduced:**
- Setup helpers must not infer mode from incidental tool availability.
- `check-*` commands must be non-mutating unless explicitly named as fix/format commands.
- Derived setup docs must reference SSOT files instead of reproducing canonical facts where practical.

---

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-03 | ✅ | This ADR defines the setup contract before Platform implementation. No service Protocol needed because this is tooling/config architecture, not a service API. |
| RULE-04 | ✅ | No production modules are changed. Future config/doc edits must split rather than compress if size limits are approached. |
| RULE-05 | ✅ | Ownership is separated: Platform owns setup/CI/release config; Docs owns derived documentation cleanup; architecture owns this contract. |
| RULE-06 | ✅ | Proposed changes preserve one responsibility per file/workflow: gate SSOT, environment mode contract, release config, docs references. |
| RULE-07 | ✅ | No application dependency direction changes. |
| RULE-10 | ✅ | Acceptance criteria include validation commands for Platform after implementation. |
| RULE-11 | ✅ | CI must be blocking for setup/config paths; config-only failures must not be silent. |
| RULE-12 | ✅ | No client/service public API changes. |
| RULE-18 | ✅ | The ADR removes hardcoded setup paths/implicit hostnames from environment config. |
| RULE-20 | ✅ | Rejects symptom patches; requires complete mode contract and gate SSOT cleanup. |
| RULE-21 | ✅ | Material changes to rollout order or environment mode ownership require architecture re-review. |

---

## Sustainability Check

- **Correct in 3 months?** Yes; explicit mode contracts and gate SSOT reduce recurring drift.
- **Hard-to-undo coupling?** No; VM-first and DevContainer responsibilities are separated rather than conflated.
- **Simplest correct solution?** Yes; one primary mode plus optional portable DevContainer is simpler than container-only migration and more correct than symptom patches.
- **Design intent understandable?** Yes; this ADR states root cause, contract, rollout order, and acceptance criteria.

---

## Implementation Notes

- This ADR intentionally avoids prescribing exact shell implementation details; Platform owns the concrete edits.
- Platform should keep each rollout step internally complete and validated before moving to the next step.
- If a proposed implementation requires changing the primary mode away from VM-first, return to Architecture for a new ADR or ADR update.
- If validation later fails, fix the root cause. Do not bypass hooks or CI.

---

## Review Trigger

- When DevContainer becomes mandatory instead of optional.
- When release image ownership or GHCR namespace changes.
- When CI workflow ownership changes again.
- After the Platform cleanup is implemented, to verify no derived-doc drift remains.

---

## Related

- `docs/_shared/CONSTRAINTS.md` — Architecture constraint SSOT
- `docs/_shared/TECH_STACK.md` — Dependency/version SSOT
- `docs/_shared/CURRENT_STATE.md` — Current project state
- `.devcontainer/docker-compose.devcontainer.yml` — DevContainer compose target for Platform cleanup
- `justfile` — VM-first helper target for Platform cleanup
- `.github/workflows/ci.yml` — blocking CI and architecture/setup gate SSOT
- `docker-compose*.yml` and release compose files — release/setup targets for Platform cleanup
