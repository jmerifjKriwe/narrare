---
files:
  - "app/capabilities/**/*.py"
  - "app/capabilities/**/*.ts"
  - "app/capabilities/**/*.tsx"
  - "app/kernel/**/*.py"
  - "web/**/*.ts"
  - "web/**/*.tsx"
  - "!web/lib/generated/**"
  - "!app/generated/**"
---

# A capability never reaches into another capability

Standing rule 1 and "the shape of a capability" in
`docs/_shared/CONSTRAINTS.md`: one capability is one folder under
`app/capabilities/<name>/`, and a capability never imports another one.
Imports point one way, `api → capabilities → kernel`. A capability's UI
reaches the shell only through `@shell/*`, and the shell reaches a capability
only through the generated tables (`web/lib/generated/`, `app/generated/`).

No linter or test enforces this. Ruff, pyright, Biome and tsc all accept a
cross-capability import, and the resolver in `scripts/affected.py` decides
which E2E suites a change owes by capability folder. A hidden coupling
therefore also means a change in one capability can break another capability
whose suite never ran.

## What breaks the requirement

- Python under `app/capabilities/<a>/` imports from `app.capabilities.<b>`
  (any module: `models`, `schemas`, `service`, `repository`, `prompts`),
  including inside a function body or under `TYPE_CHECKING`.
- Python under `app/kernel/` imports from `app.capabilities.*`. The one
  sanctioned route is the generated registry: code that iterates
  `app.generated.capabilities.CAPABILITIES` and loads modules by id, as
  `app/kernel/db/migrate.py` and `app/api/main.py` do.
- Capability logic placed in `app/kernel/` so that two capabilities can share
  it. Only shared domain belongs in the kernel (the contracts in
  `app/kernel/contracts/`, LLM, prompts, jobs, interchange). A function that
  only one capability's workflow needs stays in that capability.
- TypeScript under `app/capabilities/<a>/web/` imports a file under
  `app/capabilities/<b>/`, by relative path (`../../<b>/web/...`) or any
  other alias, including its i18n JSON.
- Non-test capability UI code imports a generated shell view that itself
  imports every capability's modules (`@shell/lib/generated/routes`). That
  reaches the other capabilities indirectly. `@shell/lib/generated/catalogs`
  and the other data tables are fine.
- Shell code under `web/` (outside `web/lib/generated/`) imports from
  `app/capabilities/` directly instead of through a generated table.
- A capability writes another capability's tables. Reading a kernel contract
  model (`Novel`, `Chapter`, `Scene`, `Entity` …) is fine. Writing a table
  defined in another capability's `models.py` is not.

## What satisfies it

Shared types and tables live in `app/kernel/contracts/`. Shared UI lives in
the shell and is imported as `@shell/...`. A value one capability needs from
another reaches it through a kernel contract or a generated table, which
`just generate` writes from `capability.yaml` and the capability's own files.

## Example

Incorrect: planning reaches into writing's service and UI.

```python
# app/capabilities/planning/service.py
from app.capabilities.writing.service import WritingService
```

```tsx
// app/capabilities/planning/web/StoryboardPage.tsx
import { ChapterCard } from "../../writing/web/ChapterCard";
```

Correct, as `app/capabilities/planning/repository.py` reads the novel's
chapters through the kernel contract, and the UI imports only the shell:

```python
from app.kernel.contracts.models import Chapter, Novel, Scene
```

```tsx
import { useTranslation } from "@shell/lib/i18n";
import { CARD_EYEBROW } from "@shell/ui/card";
```

When you report a finding, name the importing file and line, the capability
or module it reaches, and where the shared piece should live instead.
