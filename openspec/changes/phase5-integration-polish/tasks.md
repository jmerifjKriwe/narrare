## 1. Playwright E2E Infrastructure

- [x] 1.1 Add Playwright as dev-dependency (Python `playwright` + `@playwright/test` in packages/web) and run `playwright install chromium`
- [x] 1.2 Create `playwright.config.ts` at project root with baseURL, timeout, retry settings, and Chromium-only config
- [x] 1.3 Create `tests/e2e/conftest.py` with fixtures for authenticated session, API base URL, and test database state
- [x] 1.4 Create `tests/e2e/fixtures/auth.fixture.ts` with login helper that obtains JWT token and stores it in browser context
- [x] 1.5 Create `tests/e2e/mocks/llm-responses.ts` with canned LLM provider responses for setup wizard step 4 validation
- [x] 1.6 Update `.github/workflows/ci.yml` to run E2E tests on main branch only, with full stack (API + web + PostgreSQL + Redis)

## 2. E2E Hero Flow Test

- [x] 2.1 Create `tests/e2e/test_hero_flow.py` — test step: user registration via API or UI
- [x] 2.2 Extend hero test — setup wizard step 1 (project name, language, autosave config)
- [x] 2.3 Extend hero test — setup wizard steps 2-3 (novel metadata, select Fantasy demo content)
- [x] 2.4 Extend hero test — setup wizard step 4 (AI provider with mocked LLM validation via route.fulfill)
- [x] 2.5 Extend hero test — setup wizard step 5 (confirm and complete, verify redirect to dashboard)
- [x] 2.6 Extend hero test — dashboard shows demo novel with chapters, navigate to editor
- [x] 2.7 Extend hero test — editor loads chapter content, type new text, verify autosave API call fires after debounce

## 3. Backend Test Coverage Gaps

- [x] 3.1 Create `tests/unit/api/settings/test_settings_service.py` — unit tests for user settings and project settings CRUD (happy path, validation, not-found)
- [x] 3.2 Create `tests/integration/test_seed_dev_user.py` — integration test that runs seed script against fresh DB and verifies dev user exists and can authenticate
- [x] 3.3 Add tests to `tests/unit/api/setup/test_demo_loader.py` — cover `_load_chapters()` and `_load_kb_entries()` for all three demo projects (Fantasy 4 chapters + 15 KB, SciFi 3 + 8, German 2 + 6)
- [x] 3.4 Add tests to `tests/unit/core/llm/test_gateway.py` — cover `_classify_error()` for pydantic-ai typed exceptions, stdlib exceptions, string fallback, unknown errors
- [x] 3.5 Create `tests/unit/core/llm/test_retry.py` — cover `with_retry()` for: success on first attempt, retry on transient failure, max retries exceeded, exponential backoff timing
- [x] 3.6 Add test for `SetupService.complete()` — verify novel/chapters/settings creation flow in setup service unit tests

## 4. Frontend Test Coverage Gaps — Priority 1 (Editor + Wizard)

- [x] 4.1 Create `packages/web/components/editor/EditorSurface.test.tsx` — test autosave triggers on content change (debounced API call), word count updates on edit
- [x] 4.2 Create `packages/web/components/editor/ChapterSidebar.test.tsx` — test chapter list renders from props, click triggers chapter switch callback
- [x] 4.3 Create `packages/web/components/editor/StatusBar.test.tsx` — test displays correct save status (idle/saving/saved/error) and word count
- [x] 4.4 Create `packages/web/components/setup/WizardShell.test.tsx` — test step transitions (next/previous), current step indicator
- [x] 4.5 Create `packages/web/components/setup/WizardStep1.test.tsx` — test form validation (required fields), valid input advances
- [x] 4.6 Create `packages/web/components/setup/WizardStep2.test.tsx` — test form fields render, validation on submit
- [x] 4.7 Create `packages/web/components/setup/WizardStep3.test.tsx` — test demo content selection, radio/click interaction
- [x] 4.8 Create `packages/web/components/setup/WizardStep4.test.tsx` — test provider selection, API key input, mocked model loading
- [x] 4.9 Create `packages/web/components/setup/WizardStep5.test.tsx` — test confirmation summary renders, submit triggers completion

## 5. Frontend Test Coverage Gaps — Priority 2 (Dashboard + Shared)

- [x] 5.1 Create `packages/web/components/dashboard/DashboardView.test.tsx` — test novel cards render with mocked MSW data, click navigates to editor
- [x] 5.2 Create `packages/web/components/shared/ErrorBoundary.test.tsx` — test catches render error and displays fallback UI, normal render passes through

## 6. Documentation Polish

- [x] 6.1 Update `docs/architecture/questions/Q-001-to-Q-004.md` — mark Q-004 as ✅ Resolved (→ TaskIQ, ADR-007), re-scope Q-003 as post-MVP, update Q-001/Q-002 blocking notes
- [x] 6.2 Update `docs/architecture/questions/INDEX.md` — fix links to point to `Q-001-to-Q-004.md` instead of non-existent individual files, ensure Q-004 shows resolved status
- [x] 6.3 Update `docs/_shared/CURRENT_STATE.md` — restructure "Next Session" section to clearly separate Phase 5 scope from post-MVP items, fix Q-003 Blocks column
- [x] 6.4 Update `docs/development/testing-standards.md` — change E2E section from "Real services including LLM (cheapest model)" to "LLM responses mocked via Playwright route.fulfill()"
- [x] 6.5 Update `README.md` — add complete setup instructions (prerequisites, just dev-setup, just dev, just test, just check)
- [x] 6.6 Update `CHANGELOG.md` — add v0.1.0 entry with all MVP features organized by phase (0-4)

## 7. Verification

- [x] 7.1 Run `just test` — all unit + integration tests pass
- [x] 7.2 Run `just check` — architecture + lint + typecheck pass
- [ ] 7.3 Run Playwright E2E hero flow test — passes with mocked LLM
- [x] 7.4 Verify `pnpm test` in packages/web — all frontend tests pass including new ones
- [ ] 7.5 Run `just dev` and manually verify complete flow: signup → wizard → demo → editor → autosave
- [x] 7.6 Create conventional commit: `git add` all Phase 5 changes, commit with message `feat: complete MVP phase 5 — E2E tests, test coverage, docs polish (#phase5)` — run via NarrarePlatformSpecialist
