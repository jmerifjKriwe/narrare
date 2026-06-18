# FIND-010 — Chat prompt surface drifts across runtime, manifest, and prompt management

Priority: 🔴 High
Status: ✅ Resolved (2026-06-18)
Source: CR-02 §2, CR-04 §3–§4 (2026-06-12)

> **Resolution:** Closed by [ADR-049](../../../../docs/architecture/decisions/ADR-049-prompt-surface-identity-path-contract.md) (Prompt-Surface Identity & Path Contract). Phase C implemented all Retrofit-Plan steps (route-table reverted to ADR-024 `category="writing", mode="chat"`; the orphan `_bundled/chat/` duplicate deleted; manifest/route aligned). Phase D enforces the fix via four machine-checkable gates (see "Resolution evidence" below). "Resolved" here means *implemented + enforced*, not merely *documented*.

## Finding

`LLMIntent.CHAT` has inconsistent prompt-surface ownership:

- Runtime route table maps `LLMIntent.CHAT` to category `chat`, mode `""` (`packages/core/narrare_core/prompts/route_table.py:8-52`, `route_table.py:145`).
- `PromptRegistry` therefore resolves the runtime template at `packages/core/narrare_core/prompts/_bundled/chat/en/system.md`, whose frontmatter says `prompt_type: chat` (`chat/en/system.md:1-5`).
- `scripts/architecture/prompt-surface-manifest.yaml:85-97` declares category `chat`, mode `""`, but its `template` path points to `packages/core/narrare_core/prompts/_bundled/writing/en/chat/system.md`.
- Both templates exist and have different frontmatter/content: the runtime file is `prompt_type: chat` (`chat/en/system.md:1-5`), while the manifest file is `prompt_type: writing` (`writing/en/chat/system.md:1-5`).
- `PromptManagementService.list_prompts()` requires `len(parts) >= 4` and then derives `prompt_mode = parts[2]` (`packages/core/narrare_core/prompts/management.py:73-89`); `get_prompt()` and `save_override()` require exactly three ID segments (`management.py:122-162`). A root-mode file path such as `chat/en/system.md` therefore does not have an explicit stable mode identity.
- CR-02 additionally found that chat's composed system prompt is concatenated into the user-channel prompt rather than injected as agent system/instructions. That is not a separate finding here because fixing the chat source of truth and injection path should happen under the same prompt-surface contract.

## Root Cause

The Prompt Surface Contract governs route category/mode but not the canonical filesystem path and prompt-management identity for root-mode prompts. This allowed a stale duplicate chat template to remain valid in the manifest while runtime uses a different file.

## User Impact

- Users may edit or review a chat prompt that is not the runtime prompt.
- Manifest security checks may validate the wrong template.
- Generated-suggestion labels and variable requirements can pass for the stale path while runtime behavior differs.
- CR-02’s chat injection issue becomes harder to fix safely because the source of truth is ambiguous.
- The free assistant can drift from Narrare's expected persona/task scope depending on whether reviewers, prompt management, or runtime resolve the prompt surface.

## Sustainable Recommendation

Fix the contract rather than patching one caller:

1. Choose one canonical chat prompt location and remove/retire the duplicate or mark it non-routeable.
2. Update the manifest template path to match the route-derived path.
3. Update the prompt-surface checker to verify route category/mode → expected path and template frontmatter.
4. Update PromptManagementService to support root-mode prompts explicitly, or represent chat with a non-empty governed mode such as `default`.
5. Add regression tests proving the prompt exposed in management is the prompt used by `PromptComposer` for `LLMIntent.CHAT`.

## Related CR Tasks

- `CR-AUFG-02-04`
- `CR-AUFG-04-04`
- `CR-AUFG-04-05`

## Related Findings

- Cross-references FIND-011 because both findings expose prompt-surface artifacts that pass structural checks while runtime uses a different prompt path.

---

## Resolution evidence (2026-06-18)

**Design (ADR):** ADR-049 Decisions D1–D6 — restored ADR-024 CHAT routing as canonical (`category="writing", mode="chat"`), forbade root-mode for routeable intents (D3), and added four identity invariants: path derivability (D4), frontmatter `prompt_type` == manifest category (D5), management-id derivability (D6).

**Implementation (Phase C — verified on disk):**
- `_bundled/chat/` directory and `_bundled/chat/en/system.md` **deleted** (the orphan duplicate that runtime previously loaded).
- `_bundled/writing/en/chat/system.md` is now the sole canonical CHAT template (3784 bytes, frontmatter `prompt_type: writing`).
- Route table, manifest, and management layer all resolve to the same file.

**Enforcement (Phase D — CI-blocking checkers):**
- `PROMPT-IDENTITY` (gate A1): full identity chain manifest ↔ route-table ↔ frontmatter ↔ management-id ↔ Composer resolution.
- `PROMPT-ROOT-MODE` (gate A2): no routeable intent may carry `default_mode == ""` (the root-mode shape that hid CHAT from the management UI).
- `PROMPT-PATH-DERIVABILITY` (gate A3): manifest `template:` path must equal `_bundled/{category}/{lang}/{mode}/system.md`.
- `PROMPT-FRONTMATTER-MATCH` (gate A4): frontmatter `prompt_type` must equal the manifest category and be a canonical enumeration value.
- `ORPHAN-TEMPLATE` (gate A6): every `system.md` under `_bundled/` must be reachable by a manifest entry or be a documented capability-loaded exemption.
- Root-cause bonus: the latent ADR-037 checker bug was found and fixed during Phase D — its AST parser only visited `ast.Assign` nodes, silently skipping `ast.AnnAssign`; the manifest's `context_modes` table was therefore never actually validated. Now fixed.

**Follow-up status:** None open for FIND-010. FIND-011 (the paired finding) is also resolved (see its file).
