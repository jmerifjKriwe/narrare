---
# Global architecture constraints for Narrare
---

## RULE-01 · LLM calls go through the Gateway
- No `import openai` or `import anthropic` outside `core/llm/`
- No HTTP calls to LLM provider endpoints outside `core/llm/`
- Use: `from core.llm.gateway import LLMGateway`

## RULE-02 · Prompts are built in core/prompts/
- No f-strings for prompts in services
- No string concatenation for prompts
- Use: `from core.prompts.composer import PromptComposer`

## RULE-03 · Contracts before implementation
- Every service has a Protocol in contracts.py before implementation
- Example: `writing/contracts.py` defines ChapterWriterProtocol

## RULE-04 · File size limits are hard limits
- Router: 150 lines
- Service: 300 lines
- Any Python module: 400 lines
- Test file: 400 lines

## RULE-05 · Module boundaries
- No imports from `_internal` submodules of other domains
- Use public `__init__.py` exports only

## RULE-06 · One responsibility per file
- Router: FastAPI routes only, no business logic
- Service: Business logic, no DB queries
- Repository: DB queries only, no business logic

## RULE-09 · Type signatures mandatory
- Every public function has full type signature
- Return type annotation is mandatory
- No `Any` except in approved adapters

## RULE-10 · Tests are not optional
- Every service method needs a unit test
- Every router endpoint needs an integration test
- Minimum coverage: core/ 90%, apps/api/ 80%

## RULE-11 · No silent failures
- No bare `except: pass`
- Every exception is logged, re-raised, or converted to typed error

Full documentation: docs/_shared/CONSTRAINTS.md
