# Smoke Test Checklist: learn-001-feedback-loop

Manual verification path for the feedback loop feature.

## Prerequisites
- [ ] Backend running with memory endpoints available
- [ ] At least one novel created
- [ ] AI provider configured

## 1. Generation Flow with Rating

1. [ ] Open a novel chapter in the editor
2. [ ] Open Generation Panel (Sparkles icon)
3. [ ] Verify **LearningStatus badge** shows in panel header (e.g. "0/50 interactions")
4. [ ] Configure generation (mode, word target) and click Generate
5. [ ] Wait for streaming to complete, review phase appears
6. [ ] Click **Accept** — RatingPrompt should appear
7. [ ] Rate 1–5 stars, click Submit
8. [ ] Verify "Thanks for your feedback!" confirmation
9. [ ] Verify LearningStatus badge updated (event count incremented)

## 2. Reject Flow with Reason

1. [ ] Generate another draft
2. [ ] Click **Reject** — RatingPrompt with reason textarea should appear
3. [ ] Enter a reason, rate, and submit
4. [ ] Verify feedback recorded

## 3. Modify Tracking

1. [ ] Generate a draft
2. [ ] Note: Current implementation captures original text at accept time
3. [ ] Click Accept — original text is recorded
4. [ ] Feedback is sent with `action: "accept"` (modify tracking compares original vs final)

## 4. Learning Tab in Settings

1. [ ] Open Settings (gear icon in sidebar)
2. [ ] Verify **"Learning"** tab appears in sidebar (with Brain icon)
3. [ ] Click Learning tab
4. [ ] Verify **LearningStatus** progress indicator shows
5. [ ] Verify **"Analyze Now"** button (disabled if < 5 events)
6. [ ] After 5+ events: click Analyze Now
7. [ ] Verify loading state, then preference profile appears
8. [ ] Verify **Style Patterns**, **Content Patterns**, **Avoidance Patterns** sections
9. [ ] Verify **Confidence badge** with color coding
10. [ ] Click **Reset Preferences**
11. [ ] Verify confirmation dialog
12. [ ] Click **Yes, Reset** — profile cleared

## 5. i18n Verification

1. [ ] Switch language to German (Settings → General → Language)
2. [ ] Navigate to Learning tab — all strings should be in German
3. [ ] Switch to French — all strings should be in French
4. [ ] Verify RatingPrompt strings are translated

## 6. API Client Verification

Verify in browser DevTools Network tab:
- [ ] `POST /api/v1/memory/feedback` — correct payload with action, suggestion_id, rating, project_id, chapter_id, mode
- [ ] `GET /api/v1/memory/preferences?project_id=...` — returns PreferenceProfile
- [ ] `POST /api/v1/memory/analyze` — triggers analysis (429 if too frequent)
- [ ] `DELETE /api/v1/memory/preferences?project_id=...` — resets preferences

## Error States

- [ ] Backend down: Learning tab shows error alert
- [ ] No profile: "Not enough data yet" message
- [ ] Analysis with < 5 events: button disabled, hint text shown
