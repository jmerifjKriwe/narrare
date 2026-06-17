<!-- Context: narrare-dev/standards/prompt-standards | Priority: high | Version: 1.2 | Updated: 2026-06-12 -->

# Prompt Engineering Standard — Quick Reference

> **Full document**: `docs/development/prompt-standards.md`
> **Enforcement**: `check_architecture.py` + `prompt_governance_checks.py` + Pydantic Evals (ADR-032) + Prompt Surface Contract manifest checker (ADR-037)
> **Related**: RULE-02, RULE-02a, RULE-02b, ADR-002, ADR-019, ADR-026, ADR-037, ADR-046, INFRA-012

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

- All user-content variables MUST be explicitly wrapped in approved XML tags:
  `<user_provided_text>`, `<user_provided_data>`, `<user_instructions>`.
- User content vars include: `{{existing_content}}`, `{{chapter_text}}`, `{{entry_content}}`,
  `{{existing_answers}}`, `{{selection_text}}`, `{{context_before/after}}`,
  `{{text_before/after}}`, `{{author_instructions}}`, `{{conversation_history}}`, `{{entity_name}}`.
- Register new user-content vars in `variable_registry.USER_CONTENT_VARS` — this is the SSOT.
- The composer/variable engine does NOT auto-wrap user content; bundled templates must wrap explicitly.
- Classify every prompt variable as user-authored, system-generated, or feature-dynamic;
  new unregistered variables are CI failures, not warnings
- Meta-prompt MUST include anti-injection directive

---

## Governance Rules Added by CR-01 Remediation

- `{{writing_language}}` is canonical for output language. `{{language}}` is deprecated and not allowed in bundled system prompts.
- Any `{{kb_suggested}}` section MUST say the data is generated, unaccepted, lower-priority, and must not override author instructions, scene/timeline context, project settings, or curated KB.
- Analysis prompts that emit issues/suggestions need evidence, confidence, or false-positive gates.
- Runtime manuscript/user text is data to analyze or transform, not instructions to obey.

---

## Cross-Feature Context Precedence

Default order when context conflicts:
current author instruction > explicit project writing profile/manual override >
current scene/storyboard/timeline plan > curated KB > learned memory/mem0
preferences > generated suggestions/inferred extraction.

High-impact conflicts between explicit/manual/curated sources must be surfaced,
not silently resolved.

---

## Version Bump Rules

| Change | Bump | Example |
|--------|------|---------|
| Section added/removed, new mandatory variable | MAJOR | Adding `{{user_preferences}}` section |
| Better instructions, new rules, clearer wording | MINOR | Rewriting Do NOT items |
| Typos, minor wording | PATCH | Grammar fix |

**Declared localized prompt families** (meta, universal) — all declared locales MUST share the same version number. Bundled feature prompts are EN-only (ADR-026 Phase 5).

---

## Variable Provenance (ADR-037 / INFRA-012)

Every template variable must have a provenance class and security classification
in the manifest or registry. Seven provenance classes (INFRA-012):
`current_author_instruction`, `project_writing_profile`, `scene_story_plan`,
`curated_kb`, `learned_memory`, `generated_suggestion`, `system_generated`,
`feature_dynamic`. A variable is valid only when classified, security-tagged,
and consumed according to its security class.

---

## Review Checklist (for prompt PRs)

- [ ] All 9 skeleton sections present
- [ ] Output format = JSON with example object
- [ ] Do NOT >=4 items, Quality Rules >=3 items
- [ ] `{{user_preferences}}` + `{{avoidance_patterns}}` included (where applicable)
- [ ] User content in approved XML tags; unsafe vars align with `variable_registry.USER_CONTENT_VARS`
- [ ] All variables registered/classified with provenance and security; no new unregistered variables
- [ ] Bundled prompts use `{{writing_language}}`, not `{{language}}`
- [ ] `{{kb_suggested}}` uses generated-candidate boilerplate where present
- [ ] Analysis prompts include evidence/confidence/false-positive gates where applicable
- [ ] Declared localized families: all locale variants updated, same version. Feature prompts: EN-only (no locale variants)
- [ ] Version bumped appropriately
- [ ] Manifest conformance (ADR-037): intent registered, routeable status correct, no production inline fallback
- [ ] Output-language variable present for user-facing generation prompts
