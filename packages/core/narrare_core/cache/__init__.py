"""Redis abstraction layer for caching.

Provides a clean interface for caching expensive operations such as
LLM responses, prompt cascade results, and session state. All Redis
interactions go through this module.

Planned features:
- LLM response caching with configurable TTL
- Prompt cascade result caching (resolved prompts by category/language/mode)
- Session state storage for active writing sessions
- Cache invalidation strategies (TTL-based, event-driven)
- Graceful degradation when Redis is unavailable

See: docs/_shared/CONSTRAINTS.md (RULE-08 — Redis in core/cache/ only)
"""
