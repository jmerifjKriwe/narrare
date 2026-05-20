---
id: CONS-002
title: "Custom Consistency Rules"
status: in progress
area: consistency
mvp: false

ui_tooltip: "Define your own consistency rules for story-specific checks."
ui_help_short: |
  Create custom consistency rules for your story's unique requirements.
  Define patterns, relationships, and constraints that matter to your
  narrative — then check against them automatically.
ui_help_long: |
  ## Custom Consistency Rules

  Define your own consistency checks for story-specific requirements.

  **Rule types:**

  **Entity Rules**
  - Character X cannot appear in location Y
  - Faction A and Faction B are always enemies
  - Character must have trait X in scenes after chapter N
  - Location property must remain consistent

  **Relationship Rules**
  - If Character A knows Character B before chapter N...
  - Character C cannot know secret X until chapter Y
  - Relationship status must follow timeline

  **Timeline Rules**
  - Event X must happen before event Y
  - Character age must be consistent across timeline
  - Minimum time required between events

  **Plot Rules**
  - If plot thread A introduced, must be resolved by chapter N
  - Character arc must progress from X to Y
  - Setup must receive payoff

  **World Rules**
  - Magic system limits must be respected
  - Technology constraints maintained
  - Geographic limitations enforced

  **How it works:**
  1. Open Consistency panel → Custom Rules
  2. Click "Add Rule"
  3. Define rule:
     - Name and description
     - Rule type
     - Condition (when to check)
     - Constraint (what must be true)
  4. Test rule on existing content
  5. Save rule to project
  6. Run rule checks with Consistency Checker

  **Rule language:**
  - Natural language descriptions
  - AI translates to checkable conditions
  - Template library for common patterns
  - Reuse rules across projects

  **Best practices:**
  - Start with built-in rule templates
  - Test rules on known-good content
  - Keep rules specific and checkable
  - Document story-specific assumptions
  - Review rules when story evolves

  Available in Consistency panel or via CLI:
  `narrare consistency rules add --template "character_knowledge"`
ui_available_in: [consistency, cli]

service: consistency/rules_service.py
contract: consistency/contracts.py#RulesServiceProtocol
router: consistency/router.py
prompt: core/prompts/_bundled/consistency/en/rules
requires: [CONS-001]
---

# CONS-002 — Custom Consistency Rules

## What it does

User-defined consistency rules for story-specific requirements. Enables writers to create custom checks for entity relationships, timeline constraints, plot requirements, and world rules that go beyond generic consistency checking.

## Why it exists

Every story has unique constraints. Generic consistency checks catch common problems, but writers need to enforce story-specific rules: "Character X can't know about event Y until chapter 5," "Magic system requires sacrifice," etc. Custom rules make these constraints checkable.

## How it works (User perspective)

1. Open Consistency panel → Custom Rules
2. Click "Add Rule"
3. Choose from templates or create custom:
   - **Entity templates**: Character constraints, location rules
   - **Relationship templates**: Knowledge rules, status tracking
   - **Timeline templates**: Event ordering, age consistency
   - **Plot templates**: Thread resolution, arc requirements
   - **World templates**: System constraints, geographic rules
4. Define rule details:
   - Name and description
   - When to check (condition)
   - What must be true (constraint)
   - Error message on violation
5. Test rule on existing content
6. Save rule to project
7. Run with Consistency Checker or scheduled checks

## How it works (Technical)

**Entry point:** `consistency/router.py` → CRUD endpoints at `/api/v1/consistency/rules`
**Service:** `RulesService` in `consistency/rules_service.py`
**Contract:** `RulesServiceProtocol` in `consistency/contracts.py`

**Rule definition:**
```python
class ConsistencyRule:
    id: UUID
    name: str
    description: str
    type: RuleType  # entity, relationship, timeline, plot, world
    condition: str  # When to check (natural language)
    constraint: str  # What must be true (natural language)
    error_message: str  # What to show on violation
    severity: "error" | "warning" | "info"
```

**Rule execution:**
1. Parse rule with LLM into checkable condition
2. Evaluate condition against content
3. Check constraint against matched content
4. Return violations with locations
5. Aggregate with standard consistency check results

**Template library:**
- Pre-defined rule patterns
- Parameterized for customization
- Community-contributed templates
- Export/import rules between projects

## Constraints & Edge Cases

- Rules must be specific and checkable
- Natural language rules may be ambiguous
- LLM translation of rules may be imperfect
- Complex rules may be slow to evaluate
- Rules may become invalid as story evolves
- Test rules carefully to avoid false positives
- Cannot enforce creative decisions, only check consistency

## Related Features

- [CONS-001](CONS-001-checker.md) — Base consistency checker
- [KB-001](../kb/KB-001-entity-management.md) — Entity data
- [PLAN-004](../planning/PLAN-004-timeline.md) — Timeline rules
- [ANAL-005](../analysis/ANAL-005-coreference.md) — Reference tracking

## Status & History

- `project-init` — Added to registry as planned feature
