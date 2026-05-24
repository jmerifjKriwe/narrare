---
id: STATS-002
title: "AI Cost Tracking"
status: planned
area: analytics
mvp: false

ui_tooltip: "Monitor AI usage costs and set budgets to control expenses."
ui_help_short: |
  Monitor AI usage costs and set budgets to control expenses. Track token
  consumption per feature, calculate costs by provider/model, and set
  spending limits to stay within budget.
ui_help_long: |
  ## AI Cost Tracking

  Know what your AI assistance costs and control your spending.

  **Usage Tracking**
  - Token consumption per feature
  - Cost calculation by provider/model
  - Historical usage patterns
  - Project vs. user-level tracking
  - Real-time cost updates

  **Budget Management**
  - Monthly spending limits
  - Per-feature budget caps
  - Warning thresholds (80%, 90%, 100%)
  - Automatic usage suspension at limits
  - Budget alerts and notifications

  **Cost Analysis**
  - Cost per word written
  - Most expensive features
  - Usage efficiency metrics
  - Provider cost comparisons
  - Cost trend over time

  **Reporting**
  - Daily/weekly/monthly cost summaries
  - Usage breakdown by feature
  - Project cost allocation
  - Export for accounting (CSV, PDF)

  **How it works:**
  1. All AI calls tracked automatically
  2. View costs in Settings → Costs:
     - **Overview**: Current month spending
     - **Breakdown**: By feature and model
     - **Trends**: Usage over time
     - **Projects**: Cost per novel
  3. Set budgets:
     - Monthly spending limit
     - Per-feature caps
     - Warning thresholds
  4. Receive alerts when approaching limits
  5. Usage suspended when budget exhausted (configurable)

  **Best practices:**
  - Set conservative budgets initially
  - Monitor costs during heavy usage periods
  - Use cost-efficient models for routine tasks
  - Review usage patterns for optimization opportunities
  - Export costs for reimbursement or tax purposes

  Available in Settings panel or via CLI:
  `narrare analytics costs --period month --breakdown feature`
ui_available_in: [settings, cli]

service: cost/service.py
contract: cost/contracts.py#CostTrackingServiceProtocol
router: cost/router.py
prompt: ~
requires: [INFRA-001]
---

# STATS-002 — AI Cost Tracking

## What it does

AI usage cost monitoring and budget management. Tracks token consumption per feature, calculates costs by provider and model, and enables spending limits with automatic suspension to control expenses.

## Why it exists

AI costs add up quickly. Writers using AI assistance need visibility into spending: Which features cost the most? Am I staying within budget? Which models are most cost-effective? Cost tracking provides transparency and control over AI expenses.

## How it works (User perspective)

1. All AI calls tracked automatically in background
2. View costs in Settings → Costs:
   - **Overview**: Current month spending vs budget
   - **Breakdown**: Cost by feature and model
   - **Trends**: Usage over time charts
   - **Projects**: Cost allocation per novel
3. Set budgets:
   - Monthly spending limit
   - Per-feature caps (optional)
   - Warning thresholds (80%, 90%, 100%)
4. Configure behavior:
   - Suspend usage when limit reached
   - Continue with warning only
   - Require confirmation after limit
5. Receive alerts when approaching limits
6. Export cost reports for accounting

## How it works (Technical)

**Entry point:** `cost/router.py` → GET endpoints at `/api/v1/costs`
**Service:** `CostTrackingService` in `cost/service.py`
**Contract:** `CostTrackingServiceProtocol` in `cost/contracts.py`

**Usage record:**
```python
class UsageRecord:
    id: UUID
    timestamp: datetime
    feature: str  # Feature that made the call
    provider: str  # openai, anthropic, etc.
    model: str  # gpt-4, claude-3-opus, etc.
    tokens_in: int
    tokens_out: int
    cost_usd: float  # Calculated cost
    project_id: UUID | None
    user_id: UUID
```

**Cost calculation:**
- Provider pricing tables (cached, updated periodically)
- Token counting at LLM gateway level
- Real-time cost updates
- Historical pricing for past usage

**Cost Data:** AI cost estimates use per-model pricing from [models.dev](https://models.dev). See [Model Data Reference](../../reference/model-data.md) for details on how pricing data is sourced and cached.

**Budget enforcement:**
- Check budget before each LLM call
- Suspend if limit exceeded (configurable)
- Track near-limit warnings
- Per-feature and global budgets

## Constraints & Edge Cases

- Pricing updates may cause cost discrepancies
- Token counting varies by provider's definition
- Historical costs may not reflect current pricing
- Budget suspension is per-user, not per-provider
- Cannot track costs from external API usage
- Export formats limited to CSV/PDF
- No predictive cost estimation (historical only)

## Related Features

- [INFRA-001](../infra/INFRA-001-llm-gateway.md) — LLM usage source
- [STATS-001](STATS-001-writing-stats.md) — Writing statistics
- [SETUP-001](../setup/SETUP-001-setup-wizard.md) — Provider configuration

## Status & History

- `project-init` — Added to registry as planned feature
