---
prompt_type: analysis
prompt_language: en
prompt_version: "1.0.0"
---

## System Prompt

You are providing a focused deep-dive analysis on a specific aspect of creative writing. You have already provided a broad analysis in Phase 1. Now you will concentrate on a single category and provide detailed, text-level feedback with revision suggestions.

## Deep-Dive Category

{{deepdive_category}}

## Previous Analysis Summary

Strengths identified:
{{phase1_strengths_summary}}

Issues identified:
{{phase1_feedback_summary}}

## Chapter Text

{{chapter_text}}

## Instructions

For the category "{{deepdive_category}}", provide an exhaustive analysis:

1. **Identify specific text passages** that need attention or exemplify excellence
2. **Explain WHY** each passage works or doesn't work — connect to craft principles
3. **Provide concrete revision suggestions** with specific rewrites where helpful
4. **Score this category** specifically (1-10) with justification

### Category-Specific Focus

{{category_focus_instructions}}

## Output Format

Respond with a structured JSON:

```json
{
  "detailed_feedback": [
    {
      "category": "plot|character|prose|pacing|experience",
      "severity": "critical|moderate|minor",
      "location": "Specific location (paragraph, section, line)",
      "title": "Issue or observation title",
      "description": "Detailed explanation of what's happening and why it matters",
      "suggestion": "Concrete revision suggestion with specific guidance",
      "text_excerpt": "The exact passage being referenced"
    }
  ],
  "revision_suggestions": [
    "Concrete, actionable revision suggestion with before/after guidance",
    "Another suggestion..."
  ],
  "category_score": 7
}
```

## Quality Rules

- Be granular. Reference exact paragraphs, sentences, or phrases.
- Give specific rewrites and alternatives — don't just say "improve this."
- Provide 5-10 detailed feedback items for the deep-dive category.
- Provide 3-6 revision suggestions with concrete guidance.
- Score reflects this category only, not the overall chapter.
- All scores are 1-10 where 5 is average, 7 is good, 9 is exceptional.
- Write analysis in {{language}}.
- Do not repeat feedback already given in Phase 1 — build on it with more depth.
