---
name: UX Review
about: PR template for AI-powered features requiring UX review (Stage 3.5)
title: ''
labels: ux-review
---

## Description
<!-- What does this PR change? -->

## UX Review Checklist (Stage 3.5)

### Streaming
- [ ] SSE used where backend provides SSE endpoint
- [ ] No REST-only fallback for SSE-capable endpoints

### User Controls
- [ ] Cancel/Abort present for operations >2s
- [ ] Accept/Reject flow from `studio.aiActions.*`
- [ ] No auto-apply without user confirmation

### Loading States
- [ ] Visual feedback <200ms after AI action
- [ ] Three-state lifecycle: Idle → Loading → Streaming → Complete

### Action Labels
- [ ] Canonical `studio.aiActions.*` vocabulary used
- [ ] No deprecated key references (`aiModal.*`, `generation.stop`, `annotation.keep`, etc.)
- [ ] 3-locale parity (de/en/fr)

### Error Handling
- [ ] Actionable error messages (what happened + what to do)
- [ ] Retry available after errors

### Connection Resilience
- [ ] Connection loss preserves partial output
- [ ] Retry offered via `ConnectionLostBanner`

### Onboarding
- [ ] Feature discoverable from logical location
- [ ] Tooltip present if non-obvious pattern
- [ ] Keyboard shortcuts documented in SettingsView

### Accessibility
- [ ] ARIA labels on AI indicators
- [ ] Focus management after AI output

## Items marked N/A
<!-- List any checklist items marked N/A with justification -->

## Screenshots / Demo
<!-- If UI changed, show before/after -->

## Test Plan
<!-- How was this tested? -->
