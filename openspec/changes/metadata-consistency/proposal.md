## Why

Novel metadata fields (genre, tone, language) and the name generator's parameters (culture, language) use inconsistent terminology, hardcoded limited options, and conflate distinct concepts. The word "culture" in the name generator is actually a genre. "Language" in the novel is used as both UI language and writing language. Tone options differ between Wizard and Editor. There is no way for users to define custom tones. These inconsistencies will confuse users and make future features harder to build correctly.

## What Changes

- **Genre**: Add `<datalist>` suggestions to the existing freetext input. No behavior change — genre remains freetext. Add placeholder/hint showing compound genres are possible (e.g. "Dark Urban Fantasy mit Noir-Elementen").
- **Tone**: Unify the tone option lists across Wizard, Settings, and Editor into a single canonical list (balanced, dramatic, humorous, suspenseful, contemplative, romantic, dark, adventurous, quiet). Add `_tone_instructions` for every tone. Add a custom tone system where users can define and save their own tones (name + instructions) that appear alongside bundled tones in all dropdowns. Bundled tone instructions become overridable via the prompt cascade.
- **Writing Language**: Replace the current "language" dropdown (en/de/fr) with a freetext field called "Writing Language". This field determines the language the novel is written in (not the UI language). It gets injected into prompts as an instruction: "Schreibe den Text auf: {writing_language}". The UI language (which determines prompt file selection) remains independent. Default writing language = UI language.
- **Name Generator**: Rename "culture" to "name_style" (freetext + `<datalist>` suggestions). Rename "language" to "explanation_language" (dropdown, default = novel's writing language). "name_style" is freetext because it describes the naming aesthetic (e.g. "Nordische Mythologie", "Klingonisch", "1920er Chicago Gangster") — not a fixed category. **BREAKING**: API field names change.
- **Glossary**: Correct the "Genre" entry (remove claim about genre-specific prompt files — not implemented and unlikely). Add entries for: Tone, Writing Language, UI Language, Prompt Language, Name Style, Explanation Language.

## Capabilities

### New Capabilities
- `custom-tones`: User-defined tone presets with name + instructions, stored per-user, available in all tone selectors alongside bundled tones. CRUD via Settings.

### Modified Capabilities
- `novel-metadata-edit`: Genre gets `<datalist>` suggestions. "language" field becomes "writing_language" freetext. Tone dropdown uses unified list and includes custom tones.
- `name-generator-api`: **BREAKING** — `culture` field renamed to `name_style` (freetext). `language` field renamed to `explanation_language`. Request/response schemas updated.
- `prompt-culture-injection`: Renamed concept from "culture" to "name_style". Culture definition files become name-style definition files. Same cascade mechanism, new terminology.

## Impact

- **Frontend**: WizardStep3, NovelDetailsTab, GenerationConfig, NameGenerator.tsx — all need field/option updates
- **Backend API**: `generation/schemas.py` (NameGenerateRequest breaking change), `generation/name_service.py`, novel update endpoints (language → writing_language)
- **Core**: `writing/pipeline.py` (_tone_instructions expansion), `writing/models.py`, `writing/context_assembler.py`, `prompts/context.py` (PromptContext), `llm/intents.py`
- **DB**: Novel table `language` column → `writing_language` (VARCHAR freetext, no enum constraint)
- **Prompts**: Bundled generation prompts update `{{culture}}` → `{{name_style}}`, add `{{writing_language}}` injection
- **Tests**: Extensive updates to factories, mocks, integration tests, e2e tests referencing genre/tone/language/culture
- **Glossary**: `docs/_shared/GLOSSARY.md` updates
- **No backward compatibility concern** — no external users yet
