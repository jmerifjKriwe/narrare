<!-- Context: narrare-dev/guides/prompt-quality | Priority: high | Source: docs/development/prompt-content-standards.md | Updated: 2026-06-05 -->

# Prompt Content Standards

> Complete reference: `docs/development/prompt-content-standards.md`
> Enforced by: `scripts/check_architecture.py` (prompt content checker) +
> Prompt Surface Contract manifest checker (ADR-037)

## Mandatory Elements (every bundled prompt MUST have these)

### 1. Explicit Role Assignment (first sentence)

Define WHO the AI is in the very first sentence.

```
✅ "You are a Knowledge Base assistant helping an author..."
✅ "You are an experienced beta reader providing honest feedback..."
❌ "Analyze the following text..."  (no role)
```

### 2. Output Format Specification

State the expected response format explicitly.

```
✅ JSON schema example provided
✅ "Return exactly N alternatives wrapped in <alternative> tags"
✅ "Output ONLY the continuation text — nothing else"
❌ No mention of expected format
```

### 3. Do NOT Section

At minimum **3 concrete negative constraints**.

```
✅ "### Do NOT" section with 3+ rules
❌ No negative constraints
❌ Only 1-2 vague rules ("be careful")
```

### 4. Injection Defense

All variables containing user-provided text MUST be listed in `_USER_CONTENT_VARS` in `packages/core/narrare_core/prompts/variable_engine.py`. New user-content variables require a corresponding entry.

## Recommended Elements

| Element | When to include |
|---------|-----------------|
| **Chain-of-Thought** | Tasks involving analysis, evaluation, multi-step reasoning. Use `<scratchpad>`, `reasoning` field, or "think step by step" |
| **User Preferences** | Content generation tasks: `{{user_preferences}}` |
| **Avoidance Constraints** | Content generation tasks: `{{avoidance_patterns}}` in Constraints |
| **Length/Scope Definition** | Always define: word count target, max items, "exactly one" or "3-5 suggestions" |

## Quality Checklist (before merging any prompt)

- [ ] Role assignment present in first sentence
- [ ] Output format explicitly specified
- [ ] At least 3 Do-NOT rules present
- [ ] All new user-content variables in `_USER_CONTENT_VARS`
- [ ] Variable provenance: every template variable classified with provenance and security class per ADR-037 manifest / INFRA-012 taxonomy
- [ ] Chain-of-thought included (if analysis task)
- [ ] `{{user_preferences}}` included (if content generation)
- [ ] `{{avoidance_patterns}}` in Constraints (if content generation)
- [ ] Length/scope defined
- [ ] i18n: bundled feature prompts are EN-only (output language via `{{writing_language}}`); declared localized families updated in all declared locales per ADR-026 Phase 5
- [ ] Frontmatter version bumped
- [ ] Meta-persona compatibility: Role definition compatible with Narrare identity (meta-prompt Role Flexibility)
- [ ] Fallback audit: No inline fallback that bypasses PromptComposer/MetaPromptLoader
- [ ] Manifest conformance: intent registered in Prompt Surface Contract manifest with correct routeable status and variable list (ADR-037)
- [ ] Output-language variable present for user-facing generation prompts (per manifest `output_language_variable`)
- [ ] `check_prompt_structure.py --strict` passes for all locales

## Exemplary vs Weak

**⭐⭐⭐⭐⭐ Exemplary (KB Improve):** Role in first sentence, JSON output format, 5 Do-NOT rules, scope + quality thresholds.

**⭐⭐⭐ Weak (Worldbuilding Phase 2):** Missing formal output schema, Do-NOT section, CoT, confidence thresholds.

**Related**: `narrare-dev/guides/agent-creation`, `narrare-dev/concepts/project-vision`
