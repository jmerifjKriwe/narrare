"""Context assembler — assembles prompt context from multiple sources.

This module will assemble the full prompt context for writing sessions
by combining knowledge base entries, chapter content, user preferences,
and project settings into a structured context object.

Planned features:
- KB entry selection and ranking for prompt inclusion
- Chapter content assembly (last N paragraphs, summaries)
- User preference injection into context
- Token budget management for context windows

See: docs/reference/project-vision.md (writing session architecture)
"""
