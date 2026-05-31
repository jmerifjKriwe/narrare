<!-- Context: narrare-dev/guides/prompt-quality | Priority: high | Source: docs/development/prompt-content-standards.md | Updated: 2026-05-30 -->

# Prompt Content Standards

> Complete reference: `docs/development/prompt-content-standards.md`
> Enforced by: `scripts/check_architecture.py` (prompt content checker)

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
- [ ] Chain-of-thought included (if analysis task)
- [ ] `{{user_preferences}}` included (if content generation)
- [ ] `{{avoidance_patterns}}` in Constraints (if content generation)
- [ ] Length/scope defined
- [ ] i18n: DE and FR versions updated (or EN-only documented)
- [ ] Frontmatter version bumped

## Exemplary vs Weak

**⭐⭐⭐⭐⭐ Exemplary (KB Improve):** Role in first sentence, JSON output format, 5 Do-NOT rules, scope + quality thresholds.

**⭐⭐⭐ Weak (Worldbuilding Phase 2):** Missing formal output schema, Do-NOT section, CoT, confidence thresholds.

**Related**: `narrare-dev/guides/agent-creation`, `narrare-dev/concepts/project-vision`
