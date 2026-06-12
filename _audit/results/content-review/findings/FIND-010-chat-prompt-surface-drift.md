# FIND-010 — Chat prompt surface drifts across runtime, manifest, and prompt management

Priority: 🔴 High
Status: identified / open
Source: CR-02 §2, CR-04 §3–§4 (2026-06-12)

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
