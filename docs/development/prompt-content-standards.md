# Prompt Content Standards

> **Purpose**: Define verifiable quality criteria for all AI prompts in Narrare.
> Complements RULE-02 (where prompts are built) with quality rules for WHAT they contain.
>
> **Audience**: Developers writing or modifying bundled prompts.
>
> **Enforcement**: `scripts/check_architecture.py` (prompt content checker).

---

## Mandatory Elements

Every bundled prompt (`_bundled/**/*.md`) MUST contain:

### 1. Explicit Role Assignment (first sentence)

The first sentence of the system prompt must define WHO the AI is.

```
✅ "You are a Knowledge Base assistant helping an author..."
✅ "You are an experienced beta reader providing honest feedback..."
❌ "Analyze the following text..."  (no role)
❌ "Write a chapter about..."  (no role)
```

### 2. Output Format Specification

The expected response format must be explicitly stated.

```
✅ JSON schema example provided
✅ "Return exactly N alternatives wrapped in <alternative> tags"
✅ "Output ONLY the continuation text — nothing else"
❌ No mention of expected format
```

### 3. Do NOT Section

At minimum 3 concrete negative constraints.

```
✅ "### Do NOT" section with 3+ rules
❌ No negative constraints
❌ Only 1-2 vague rules ("be careful")
```

### 4. Injection Defense

All variables containing user-provided text MUST be listed in `_USER_CONTENT_VARS` in `packages/core/narrare_core/prompts/variable_engine.py`.

New prompt variables that contain user content require a corresponding entry.

---

## Recommended Elements

Every bundled prompt SHOULD contain:

### 5. Chain-of-Thought (where analysis precedes output)

If the task involves analysis, evaluation, or multi-step reasoning, include a CoT mechanism:
- `<scratchpad>` section for planning
- `reasoning` field in JSON output
- Explicit "think step by step" instruction

### 6. User Preferences Integration

If the task generates content for the author, include:
```markdown
### User Preferences

{{user_preferences}}
```

### 7. Avoidance Constraints

If the task generates content, include in Constraints:
```markdown
- Respect the author's avoidance constraints: {{avoidance_patterns}}
```

### 8. Length/Scope Definition

Define expected output size:
- Word count target or range
- Maximum number of items
- "Exactly one" or "3-5 suggestions"

---

## Quality Checklist

Before merging any prompt change, verify:

- [ ] Role assignment present in first sentence
- [ ] Output format explicitly specified
- [ ] At least 3 Do-NOT rules present
- [ ] All new user-content variables in `_USER_CONTENT_VARS`
- [ ] Chain-of-thought included (if analysis task)
- [ ] `{{user_preferences}}` included (if content generation)
- [ ] `{{avoidance_patterns}}` in Constraints (if content generation)
- [ ] Length/scope defined
- [ ] i18n: DE and FR versions created alongside EN (run `check_prompt_structure.py` for locale coverage)
- [ ] Frontmatter version bumped
- [ ] Meta-persona compatibility: Role definition compatible with Narrare identity (meta-prompt Role Flexibility)
- [ ] Fallback audit: No inline fallback that bypasses PromptComposer/MetaPromptLoader
- [ ] `check_prompt_structure.py --strict` passes for all locales

---

## Examples

### Exemplary Prompt: KB Improve (⭐⭐⭐⭐⭐)

```markdown
You are a Knowledge Base improvement analyst. Your job is to **analyze**...
                                        ^^^ Role assignment (first sentence)

### Output Format
Return a JSON object with this structure:...
                                        ^^^ Output format

### Do NOT
- Do NOT generate full entity entries — this is analysis, not generation.
- Do NOT leave important fields empty...
- Do NOT suggest content that contradicts existing entry data...
- Do NOT fabricate entity names...
- Do NOT inflate completeness_score...
                                        ^^^ 5 Do-NOT rules

### Quality Rules
- Maximum 8 suggestions per analysis — be selective...
- Minimum confidence threshold: 0.6...
                                        ^^^ Scope + quality thresholds
```

### Weak Prompt: Worldbuilding Phase 2 (⭐⭐⭐)

Missing: formal output schema, Do-NOT section, CoT, confidence thresholds.
