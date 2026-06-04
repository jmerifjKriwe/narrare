<!-- Context: narrare-dev/standards/prompt-standards | Priority: high | Version: 1.0 | Updated: 2026-05-30 -->

# Prompt Engineering Standard — Quick Reference

> **Full document**: `docs/development/prompt-standards.md`
> **Enforcement**: `check_architecture.py` + promptfoo evals (ADR-018)
> **Related**: RULE-02, RULE-02a, ADR-002, ADR-019, ADR-026

---

## 9-Section Skeleton (every prompt MUST have)

| # | Section | Requirement |
|---|---------|-------------|
| 0 | Frontmatter | `prompt_type`, `prompt_language`, `prompt_version` (YAML) |
| 1 | Role Definition | First paragraph: WHO the AI is |
| 2 | Context | All relevant `{{variables}}` |
| 3 | Instructions | Numbered, concrete steps |
| 4 | Output Format | JSON schema + example object (or explicit free-text constraints) |
| 5 | Quality Rules | Minimum 3 positive standards |
| 6 | Do NOT | Minimum 4 specific prohibitions |
| 7 | User Preferences | `{{user_preferences}}` (all context-aware prompts) |
| 8 | Avoidance Patterns | `{{avoidance_patterns}}` (all context-aware prompts) |
| 9 | Constraints | Language, scope boundaries, operational limits |

---

## Per-Category Mandatory Variables

**Writing** (extend, rewrite, new_chapter, chat, inline_suggest, etc.):
`{{culture_guidelines}}`, `{{user_preferences}}`, `{{avoidance_patterns}}`,
`{{character_voice_profiles}}` (dialogue only), `{{kb_characters}}`, `{{kb_locations}}`

**KB** (interview, improve, suggest, enhance, extract, consistency, worldbuilding):
`{{user_preferences}}`, `{{avoidance_patterns}}`, `{{world_context}}`, `{{template_structure}}`

**Analysis** (beta_reader, consistency, summarize, review, preferences):
`{{user_preferences}}`, `{{avoidance_patterns}}`

**Planning** (outline): `{{user_preferences}}`, `{{avoidance_patterns}}`

**Meta**: Conversation Guardrails, `{{avoidance_patterns}}` (Fiction Content Guidelines and
conflict resolution are now in `NarrareUniversalRules` Capability, not meta templates — ADR-026)

---

## Security Requirements

- All user-content variables MUST be wrapped in XML tags (e.g., `<user_provided_text>`)
- User content vars: `{{existing_content}}`, `{{chapter_text}}`, `{{entry_content}}`,
  `{{existing_answers}}`, `{{selection_text}}`, `{{context_before/after}}`,
  `{{text_before/after}}`, `{{author_instructions}}`, `{{conversation_history}}`
- Register new user-content vars in `_USER_CONTENT_VARS` (`variable_engine.py`)
- Meta-prompt MUST include anti-injection directive

---

## Version Bump Rules

| Change | Bump | Example |
|--------|------|---------|
| Section added/removed, new mandatory variable | MAJOR | Adding `{{user_preferences}}` section |
| Better instructions, new rules, clearer wording | MINOR | Rewriting Do NOT items |
| Typos, minor wording | PATCH | Grammar fix |

**Declared localized prompt families** (meta, universal) — all declared locales MUST share the same version number. Bundled feature prompts are EN-only (ADR-026 Phase 5).

---

## Review Checklist (for prompt PRs)

- [ ] All 9 skeleton sections present
- [ ] Output format = JSON with example object
- [ ] Do NOT ≥4 items, Quality Rules ≥3 items
- [ ] `{{user_preferences}}` + `{{avoidance_patterns}}` included (where applicable)
- [ ] User content in XML tags
- [ ] Declared localized families: all locale variants updated, same version. Feature prompts: EN-only (no locale variants)
- [ ] Version bumped appropriately
