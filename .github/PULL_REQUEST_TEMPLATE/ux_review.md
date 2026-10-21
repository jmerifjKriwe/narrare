---
name: UX Review
about: PR template for AI-powered UI changes (chat, continuation)
title: ''
labels: ux-review
---

## Description
<!-- What does this PR change? -->

## UX Checklist

### Streaming
- [ ] Text arrives incrementally; the frame renders each chunk as it lands
- [ ] The sources of an answer are visible with or before the answer

### User Controls
- [ ] A running generation can be cancelled
- [ ] Generated text is applied only on user confirmation

### Feedback
- [ ] Visible state change under 200 ms after the action starts
- [ ] Idle → working → streaming → done is distinguishable

### Copy
- [ ] All user-visible strings through the i18n catalog (en, de, fr)
- [ ] Errors say what happened and what to do next

### Accessibility
- [ ] AI activity announced to assistive tech (aria-live or equivalent)
- [ ] Focus lands sensibly after output arrives

## Items marked N/A
<!-- List any checklist items marked N/A with justification -->

## Screenshots / Demo
<!-- If UI changed, show before/after -->

## Test Plan
<!-- How was this tested? -->
