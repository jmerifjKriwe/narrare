## Context

Narrare has five metadata-related concepts that are currently entangled: Genre, Tone, Language, and the Name Generator's "Culture" and "Language" fields. The codebase uses these terms inconsistently across Wizard, Settings, Editor, and the Name Generator. The exploration session (see proposal.md) identified that:

1. **Genre** is already freetext (good) but lacks guidance for users
2. **Tone** has two different option lists (Wizard: 7 options, Editor: 4 options), only 4 of 8 tones have `_tone_instructions`, and users cannot define custom tones
3. **Language** in the novel conflates UI language with writing language — the field determines prompt file selection AND implies output language, but cannot express "I write in Klingonisch"
4. **Culture** in the Name Generator is misnamed — it contains genre names ("fantasy", "modern", "scifi"), not cultural identifiers, and the "language" field has unclear semantics

There are no external users yet, so breaking changes to API field names are acceptable.

Current code references:
- `writing/pipeline.py`: `_TONE_INSTRUCTIONS` dict with 4 entries
- `writing/models.py`: `WritingContext` with `genre`, `language`, `tone` fields
- `generation/schemas.py`: `NameGenerateRequest` with `culture` and `language` fields
- `generation/name_service.py`: builds prompt with `culture` and `language`
- `components/studio/wizard/WizardStep3.tsx`: genre input, tone dropdown, no writing_language
- `components/studio/settings/NovelDetailsTab.tsx`: language dropdown (en/de/fr), genre input, tone dropdown
- `components/studio/editor/GenerationConfig.tsx`: separate tone dropdown (4 options)
- `components/studio/generation/NameGenerator.tsx`: culture dropdown (3 options), language dropdown (3 options)

## Goals / Non-Goals

**Goals:**
- Unify terminology: genre, tone, writing_language, name_style, explanation_language
- Provide consistent option lists across all UI surfaces (Wizard, Settings, Editor)
- Enable custom user-defined tones with persistent storage
- Separate writing language (novel metadata) from UI language (prompt file selection)
- Make name generator "name_style" freetext with suggestions (not a fixed 3-option dropdown)
- Add `_tone_instructions` for all bundled tones
- Update glossary with precise definitions

**Non-Goals:**
- Genre-specific prompt files (glossary claims this exists but it doesn't; removing the claim)
- Per-chapter or per-scene language overrides (writing_language is per-novel; special cases go through AI assistant)
- UI language selection changes (already works via next-intl, stays independent)
- Adding new bundled prompt languages beyond existing en/de/fr
- Custom genres (genre is already freetext, no structured system needed)

## Decisions

### Decision 1: Tone system — Three-layer architecture

**Choice**: Bundled tones (system) + User-custom tones (DB) + Per-generation selection.

**Rationale**: A pure dropdown is too rigid (users write in many moods not captured by 8 options). Pure freetext is annoying for repeated use (user must retype complex instructions). The three-layer approach gives: convenience (predefined options), power (custom definitions with saved instructions), and flexibility (override per generation).

**Layers**:
```
Layer 1: Bundled Tones (hardcoded in _tone_instructions, overridable via cascade)
  balanced, dramatic, humorous, suspenseful, contemplative,
  romantic, dark, adventurous, quiet

Layer 2: Custom Tones (per-user, stored in user_preferences or dedicated table)
  User creates: name + instructions text
  Appears in all tone selectors with visual separator

Layer 3: Tone Application
  Novel.tone = default for the whole novel
  Editor GenerationPanel = per-generation override
  Both can select from Layer 1 + Layer 2
```

**Alternative considered**: Freitext-only (like genre). Rejected because tone instructions are longer and reused frequently — users would have to store them externally and paste them every time.

### Decision 2: Writing Language as freetext, not enum

**Choice**: `writing_language` is a freetext string field on the Novel. Default = UI language at creation time.

**Rationale**: Users may write in "Australisches Englisch", "Schweizerdeutsch", or "Klingonisch". The LLM handles these as natural-language instructions. A fixed dropdown would artificially limit creative possibilities for zero technical benefit — the field is just injected as `"Schreibe den Text auf: {writing_language}"` in the prompt.

**Prompt integration**:
- UI language → determines which `_bundled/{category}/{language}/...` prompt file is loaded
- Writing language → injected as an instruction in the prompt content
- These are orthogonal: German UI with Klingonisch writing language works fine

**Alternative considered**: Dropdown with "Other..." freetext option. Rejected because the LLM doesn't need structured codes — it works better with natural descriptions.

### Decision 3: Name Generator — rename "culture" to "name_style", freetext + datalist

**Choice**: Replace `culture` (fixed 3-option dropdown) with `name_style` (freetext input + `<datalist>` suggestions like "Nordisch", "Elbisch", "Klingonisch", "Arabisch", "Steampunk", etc.).

**Rationale**: The current "culture" values (fantasy, modern, scifi) are genres, not cultures. A user writing a Sci-Fi novel with Japanese-influenced character names has no way to express this. Freetext + suggestions gives maximum flexibility while still guiding new users.

**Breaking change**: API field `culture` → `name_style` in `NameGenerateRequest`. The `GeneratedName.culture` response field also becomes `name_style`.

### Decision 4: Name Generator — rename "language" to "explanation_language"

**Choice**: Replace `language` with `explanation_language` (dropdown, default = novel's writing_language). This field determines the language in which name meanings/pronunciations are explained — NOT the naming style or the prompt language.

**Rationale**: The current `language` field in the name generator is overloaded — it determines both which prompt file is loaded AND what appears in the `Language: {language}` prompt variable. But the prompt file should follow UI language, and the output explanation language should follow the novel's writing language. Separating these concerns makes the system coherent.

**Prompt integration**: The prompt composer for name generation will use UI language for file selection and `explanation_language` as an injected variable: "Erkläre die Namensbedeutungen auf: {explanation_language}".

### Decision 5: Storage for custom tones

**Choice**: Store custom tones as part of the user preferences system (not a separate DB table). Each user's custom tones are a JSON array of `{id, name, instructions}` entries.

**Rationale**: Custom tones are user-level settings (available across all their novels), not novel-level metadata. The existing user preferences infrastructure can handle this without a new migration/entity. If the preference system grows complex later, migration to a dedicated table is straightforward.

**Alternative considered**: Dedicated `custom_tones` table with CRUD endpoints. Rejected as over-engineering for the current scope. Can be migrated later if needed.

### Decision 6: Tone instructions override via prompt cascade

**Choice**: Bundled `_tone_instructions` entries can be overridden by the user via the prompt cascade mechanism (same as bundled prompt overrides). A user can place a file at `.narrare/tone-overrides/{tone_id}.md` or equivalent to customize the instructions for any bundled tone.

**Rationale**: Consistent with how bundled prompts are already overridable. No new override mechanism needed — reuse the cascade pattern.

## Risks / Trade-offs

**[Risk] Breaking API change for name generator** → Mitigation: No external users exist. Update all internal consumers (frontend, tests) in the same change.

**[Risk] Custom tone storage in user preferences could hit size limits** → Mitigation: Enforce reasonable limits (max 20 custom tones, max 500 chars instructions each). JSON blob stays well under typical preference field limits.

**[Risk] Writing language freetext may produce unexpected LLM behavior** → Mitigation: The instruction is clear and the LLM handles natural language well. Edge cases (nonsense inputs) degrade gracefully — the LLM simply writes in whatever language it interprets. No validation needed beyond non-empty.

**[Risk] Prompt file selection still depends on UI language, which has only 3 options (en/de/fr)** → Mitigation: Document that adding a new prompt language requires creating bundled prompt files for all intents in that language. This is a separate concern from writing_language freetext.

**[Trade-off] name_style freetext loses the structured culture definition file system** → The `prompt-culture-injection` spec's culture definition files become less relevant. When name_style is freetext, the composer cannot resolve a predefined file. Instead, the name_style string is passed directly as a prompt variable. If the user types "Elbisch" and a culture definition file exists, it can still be resolved; if not, the raw string is used. This is graceful degradation — not a loss.

## Open Questions

1. **Custom tone management UI location**: Where exactly in Settings should custom tones be managed? A new "Tone Library" section under user settings? Or within the novel settings? Decision: user-level (not novel-level), so user settings.
2. **Name style `<datalist>` suggestions source**: Should the datalist suggestions be hardcoded in the frontend, or loaded from a bundled list that can be extended? Recommend: hardcoded initially, extensible later.
3. **Prompt cascade for tone instructions**: Exact file path convention for tone instruction overrides. Needs to align with the existing cascade in `core/prompts/registry.py`.
