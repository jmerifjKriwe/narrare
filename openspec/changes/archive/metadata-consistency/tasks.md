## 1. Glossary & Terminology Foundation

- [x] 1.1 Update `docs/_shared/GLOSSARY.md`: correct Genre entry (remove genre-specific prompt file claim, add freetext compound-genre note)
- [x] 1.2 Add GLOSSARY entries: Tone (bundled + custom), Writing Language, UI Language, Prompt Language, Name Style, Explanation Language

## 2. Core: Tone System Expansion

- [x] 2.1 Expand `_TONE_INSTRUCTIONS` in `packages/core/narrare_core/writing/pipeline.py` to cover all 9 bundled tones (add entries for contemplative, romantic, dark, adventurous; "quiet" and "balanced" already exist)
- [x] 2.2 Add tone instructions override support via prompt cascade (reuse cascade mechanism from `core/prompts/registry.py`)
- [x] 2.3 Update `WritingContext` in `packages/core/narrare_core/writing/models.py`: rename `language` → `writing_language`, ensure `tone` field accepts both bundled and custom tone identifiers
- [x] 2.4 Update `PromptContext` in `packages/core/narrare_core/prompts/context.py`: add `writing_language` field for prompt injection
- [x] 2.5 Write unit tests for expanded `_tone_instructions` (all 9 tones return non-empty strings except "balanced")
- [x] 2.6 Write unit tests for `WritingContext.to_prompt_variables()` with new `writing_language` field

## 3. Core: Writing Language Injection

- [x] 3.1 Add writing_language injection to `WritingPipeline._build_prompt_context()` — inject as "Schreibe den Text auf: {writing_language}" in prompt extra variables
- [x] 3.2 Update `WritingPipeline.generate()` to pass `writing_language` through from request to context assembler
- [x] 3.3 Update `WritingContextAssembler.assemble()` to accept and propagate `writing_language`
- [x] 3.4 Update `WritingGraph` in `packages/core/narrare_core/agents/writing_graph.py` to include writing_language in prompt
- [x] 3.5 Write unit tests for writing_language prompt injection in pipeline and context assembler

## 4. Backend: Novel Schema & API Updates

- [x] 4.1 Update novel model: rename `language` column to `writing_language` (VARCHAR freetext, no enum)
- [x] 4.2 Update novel schemas (Pydantic request/response): `language` → `writing_language` (freetext string)
- [x] 4.3 Update novel service: handle `writing_language` field in create/update operations
- [x] 4.4 Update setup service and provider schemas: `language` → `writing_language` in wizard completion
- [x] 4.5 Write/update integration tests for novel API with writing_language freetext
- [x] 4.6 Update demo loader to use `writing_language` field

## 5. Backend: Custom Tone CRUD

- [x] 5.1 Define custom tone storage schema in user preferences (JSON array of `{id, name, instructions}`)
- [x] 5.2 Create custom tone CRUD endpoints: GET/POST/PUT/DELETE `/api/v1/user/preferences/tones`
- [x] 5.3 Add validation: max 20 tones, name 1-50 chars, instructions 1-500 chars, name uniqueness
- [x] 5.4 Create service methods for custom tone operations in user preferences service
- [x] 5.5 Write unit tests for custom tone CRUD service
- [x] 5.6 Write integration tests for custom tone API endpoints

## 6. Backend: Name Generator API Rename

- [x] 6.1 Update `NameGenerateRequest` in `generation/schemas.py`: rename `culture` → `name_style` (freetext, 1-100 chars), rename `language` → `explanation_language` (string, 2-50 chars)
- [x] 6.2 Update `GeneratedName` response: rename `culture` → `name_style`
- [x] 6.3 Update `NameGenerateResponse`: rename `culture` → `name_style`
- [x] 6.4 Update `NameGeneratorService._build_user_prompt()`: use `name_style` and `explanation_language`
- [x] 6.5 Update `NameGeneratorService.generate_names()`: pass `name_style` and `explanation_language` in PromptContext extra
- [x] 6.6 Update `NameGeneratorService._parse_names()`: use `name_style` instead of `request.culture`
- [x] 6.7 Write unit tests for renamed schema validation (old field names rejected, new field names accepted)
- [x] 6.8 Update existing name service tests (happy path, edge cases, integration, parse) to use new field names

## 7. Core: Prompt Culture → Name Style Migration

- [x] 7.1 Rename `_bundled/generation/cultures/` directory to `_bundled/generation/name-styles/` (or keep as alias)
- [x] 7.2 Update bundled name generation prompts (`en/names/system.md`, `de/names/system.md`, `fr/names/system.md`): `{{culture}}` → `{{name_style}}`, add `{{explanation_language}}` variable, update instructions
- [x] 7.3 Update PromptComposer culture resolution: try to resolve name-style definition file; if not found, inject raw name_style string as fallback
- [x] 7.4 Update `prompt-culture-injection` related code in composer to use new terminology (name-style instead of culture)
- [x] 7.5 Write unit tests for name-style file resolution with freetext fallback
- [x] 7.6 Write unit tests for bundled prompt variable substitution with new field names

## 8. Frontend: Type & Shared Config Updates

- [x] 8.1 Update `packages/web/types/index.ts`: expand `StoryTone` to include all 9 tones (add "balanced", "quiet"); rename any language-related types if needed
- [x] 8.2 Create shared tone options constant (single source of truth) used by Wizard, Settings, and Editor
- [x] 8.3 Create genre `<datalist>` suggestions constant
- [x] 8.4 Create name-style `<datalist>` suggestions constant
- [x] 8.5 Update `WizardState` type: `language` → `writing_language` (freetext)

## 9. Frontend: Wizard Step 3 Updates

- [x] 9.1 Update `WizardStep3.tsx`: add `<datalist>` to genre input with compound-genre hint
- [x] 9.2 Update `WizardStep3.tsx`: replace language dropdown with `writing_language` freetext input (default = UI locale)
- [x] 9.3 Update `WizardStep3.tsx`: use unified tone list from shared constant, include custom tones from user preferences
- [x] 9.4 Update wizard store (`wizardStore.ts`): `language` → `writing_language` in state shape
- [x] 9.5 Update wizard API client: send `writing_language` instead of `language`
- [x] 9.6 Write/update unit tests for WizardStep3 with new fields
- [x] 9.7 Update e2e wizard tests with new field names

## 10. Frontend: Settings NovelDetailsTab Updates

- [x] 10.1 Update `NovelDetailsTab.tsx`: add `<datalist>` to genre input
- [x] 10.2 Update `NovelDetailsTab.tsx`: replace `LANGUAGE_OPTIONS` dropdown with `writing_language` freetext input
- [x] 10.3 Update `NovelDetailsTab.tsx`: use unified tone list + custom tones in tone selector
- [x] 10.4 Write/update unit tests for NovelDetailsTab with new fields

## 11. Frontend: Editor GenerationPanel Updates

- [x] 11.1 Update `GenerationConfig.tsx`: expand `TONE_OPTIONS` to full unified list (all 9 tones + custom tones)
- [x] 11.2 Update `GenerationPanel.tsx`: no language field change needed (writing language comes from novel metadata)
- [x] 11.3 Write/update unit tests for GenerationConfig with unified tone list

## 12. Frontend: Name Generator Updates

- [x] 12.1 Update `NameGenerator.tsx`: rename "culture" dropdown to "name_style" freetext input with `<datalist>`
- [x] 12.2 Update `NameGenerator.tsx`: rename "language" dropdown to "explanation_language" dropdown, default to novel's writing_language
- [x] 12.3 Update `NameGenerator.tsx`: update API call to send `name_style` and `explanation_language`
- [x] 12.4 Update `generationApi.generateNames()` in `lib/api/client.ts`: use new field names
- [x] 12.5 Update `types/index.ts`: update `NameGenerateRequest` and `NameGenerateResponse` types
- [x] 12.6 Write/update unit tests for NameGenerator with new fields
- [x] 12.7 Update e2e tests for name generator if applicable

## 13. Frontend: Custom Tone Management UI

- [x] 13.1 Create "Tone Library" section in user settings
- [x] 13.2 Build custom tone list view with edit/delete actions
- [x] 13.3 Build custom tone create/edit form (name + instructions fields)
- [x] 13.4 Wire custom tone management to CRUD API endpoints
- [x] 13.5 Integrate custom tones into all tone selectors (fetch from user preferences on load)
- [x] 13.6 Write unit tests for Tone Library UI
- [x] 13.7 Add i18n keys for Tone Library UI (en, de, fr)

## 14. Test Suite Updates

- [x] 14.1 Update `tests/factories.py`: rename `language` → `writing_language`, `culture` → `name_style` in test factories
- [x] 14.2 Update `tests/fakes/fake_services.py`: align with renamed fields
- [x] 14.3 Update all integration tests referencing novel `language` to use `writing_language`
- [x] 14.4 Update all integration tests referencing name generator `culture` to use `name_style`
- [x] 14.5 Update mock handlers (`packages/web/mocks/handlers.ts`): use new field names
- [x] 14.6 Run full test suite and verify all tests pass

## 15. Documentation & Final Validation

- [x] 15.1 Update `docs/_shared/GLOSSARY.md` with all new and modified terms (verify tasks 1.1 and 1.2 are reflected)
- [x] 15.2 Run architecture validation (`scripts/check_architecture.py`)
- [x] 15.3 Run full test suite and verify zero failures
- [x] 15.4 Verify i18n: all new UI elements have translations in en, de, fr
