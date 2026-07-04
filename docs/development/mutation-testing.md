# Mutation Testing & Assertion Quality Audit

> **Stand:** 2026-07-04
> **Maintainer:** Platform Agent

## Überblick

Narrare verwendet zwei komplementäre Verfahren zur Testqualitäts-Messung:

| Verfahren | Was | Wann | Blockierend? |
|-----------|-----|------|-------------|
| **Assertion-Qualitäts-Audit** | Scannt Tests auf schwache Assertion-Patterns | On-demand / PR | Nein |
| **MutMut (Mutation Testing)** | Mutiert Python-Code, misst ob Tests die Mutation erkennen | Monatlich (CI) | Nein |

## Assertion-Qualitäts-Audit

### Zweck

Findet Tests, die zwar Zeilen covern, aber keine aussagekräftigen Assertions haben. Ein Test der nur `assert result is not None` macht, überlebt viele Mutationen — er prüft nicht, ob das Ergebnis *korrekt* ist.

### Skript

```bash
# Kompletten Audit laufen
uv run python scripts/audit_test_assertions.py

# Nur Unit-Tests, Top-20 Schwachstellen
uv run python scripts/audit_test_assertions.py --path tests/unit/ --top-n 20

# Mit JSON-Output
uv run python scripts/audit_test_assertions.py --json report.json

# Als CI-Gate (fail when score > threshold)
uv run python scripts/audit_test_assertions.py --path tests/unit/ --fail-on 0.5
```

### Erkannte Patterns

| Pattern | Weight | Beschreibung |
|---------|--------|-------------|
| `assert_true_literal` | 1.0 | `assert True` — toter Test |
| `trivial_truthy` | 0.6 | `assert result` ohne Feldzugriff |
| `response_json_truthy` | 0.5 | `assert response.json()` ohne Schema |
| `is_not_none_sole` | 0.4 | `assert x is not None` als einzige Assertion |
| `status_code_only` | 0.3 | Status-Code ohne Body-Validierung |
| `pytest_raises_no_match` | 0.3 | `pytest.raises(Exc)` ohne `match=` |
| `missing_model_validate` | 0.2/File | File mit status_code-Checks ohne `model_validate` |

### Wann ausführen

- **Nach größeren Test-Änderungen:** Prüfen ob neue Tests starke Assertions haben
- **Vor Refactoring:** Sicherstellen dass bestehende Tests Mutationen killen würden
- **Quartalsweise:** Baseline der Testqualität erfassen

## Mutation Testing (MutMut)

### Zweck

MutMut verändert (mutiert) Python-Code an bestimmten Stellen (z.B. `==` → `!=`, `and` → `or`, löscht Bedingungen) und prüft, ob mindestens ein Test fehlschlägt ("die Mutation killt"). Überlebende Mutationen zeigen Lücken in der Testabdeckung — nicht bei Zeilen, sondern bei *Verhalten*.

### CI-Job

Ein separater GitHub Actions Workflow läuft monatlich (1. des Monats, 06:00 UTC) oder manuell triggerbar:

```bash
# Manuell via GitHub UI: Actions → Mutation Testing (Monthly) → Run workflow
# Oder lokal (MutMut 3.x ist config-driven — nutze den Wrapper für Scopes):
uv run python scripts/run_mutmut.py                       # core (default)
uv run python scripts/run_mutmut.py --scope api            # api scope
uv run python scripts/run_mutmut.py --scope all            # all scopes
uv run python scripts/run_mutmut.py --scope custom \
    --paths "narrare_core/prompts/*" \
    --tests "tests/unit/core/prompts/"
```

> **Hinweis:** Der Wrapper erstellt temporäre Symlinks (`narrare_core → packages/core/narrare_core`),
> damit MutMut's pfadbasierte Modul-Schlüssel mit den Python-Import-Pfaden
> übereinstimmen. Symlinks und `pyproject.toml` werden nach dem Lauf (auch bei
> Fehlern) automatisch wiederhergestellt.

**Der Job ist NIEMALS blockierend** (`continue-on-error: true`). Ergebnisse werden als GitHub Issue mit Label `mutation-testing` veröffentlicht.

### Sandbox-Kompatibilität: Zwei Konventionen für Test-Autoren

MutMut arbeitet in einer **kopiebasierten Sandbox**: Das instrumentierte Paket
liegt unter `mutants/narrare_core/` (bzw. `mutants/narrare/`), und es gibt
**kein** `mutants/packages/`-Mirror des Repo-Worktrees. Wer Tests schreibt,
die im Mutation-Run mitlaufen sollen, muss zwei Konventionen einhalten:

#### 1. Bundled-Assets via `importlib.resources` auflösen

Tests, die gebündelte Paket-Assets lesen (Prompts unter `_bundled/`,
Templates), **MÜSSEN** den Pfad paket-relativ via `importlib.resources`
auflösen — und **DÜRFEN NICHT** repo-root-relativ über
`Path(__file__).parents[N] / "packages/..."` referenzieren.

```python
# RICHTIG — paket-relativ, funktioniert in Sandbox und Normal-Lauf:
from tests.unit.core._bundled import bundled_prompts_root

root = bundled_prompts_root()   # → .../narrare_core/prompts/_bundled
text = (root / "write" / "default.md").read_text()

# FALSCH — bricht im Mutation-Run (Pfad existiert in der Sandbox nicht):
root = Path(__file__).parents[3] / "packages/core/narrare_core/prompts/_bundled"
```

**Warum:** Die Sandbox enthält nur das importierbare Paket unter
`mutants/narrare_core/`. Repo-root-relative Pfade (`packages/...`) zeigen dort
ins Leere. Der Helper `tests/unit/core/_bundled.py::bundled_prompts_root()`
spiegelt die Produktionsauflösung (`registry.py`) und resolved in normalem
Dev/CI auf dieselben Dateien wie früher.

#### 2. `@pytest.mark.mutation_inert` für statische Repo-Struktur-Tests

Tests, deren Assertion-Ziel **statische Repo-Struktur** ist — nicht mutiertes
Laufzeitverhalten — können keine Mutanten killen **und** sind mit der Sandbox
inkompatibel. Beispiele: Quelldatei-Existenz-Checks, `pyproject.toml`-Inhalte,
AST-Scans der Quelle auf verbotene Imports.

Markiere solche Tests **pro Funktion**:

```python
@pytest.mark.mutation_inert
def test_prompt_files_ship_under_bundled():
    ...
```

MutMut's Test-Auswahl (`pytest_add_cli_args_test_selection`) deselektiert sie
über `-m "not mutation_inert"`. Normale CI-Läufe sind **nicht** betroffen — der
Marker wirkt ausschließlich im Mutation-Run.

**Kriterium:** Trifft zu, wenn die Assertion repo-Struktur prüft, nicht
Runtime-Verhalten. Im Zweifel: Mutation laufen lassen und prüfen, ob der Test
im Sandbox-Kontext überhaupt ausgeführt wird / sinnvoll killen kann.

#### Warum es kein `also_copy` / `mutants/packages/` gibt

Früher spiegelte ein redundanter `also_copy` den `packages/`-Baum in die
Sandbox, damit repo-root-relative Test-Pfade funktionierten. Das ist
bewusst entfernt: MutMut's `source_paths` kopiert ohnehin den **gesamten**
Paket-Baum (inkl. `.md`-Assets) nach `mutants/narrare_core/`. Ein zusätzlicher
`packages/`-Mirror war doppelt und hielt die falsche Auflösungs-Konvention
(Konvention 1 oben) künstlich am Leben. `also_copy` bleibt absichtlich leer
bzw. weg — `mutants/packages/` darf **nicht** wieder entstehen.

### Aktuelle Scope-Definition

| Scope | Pfade | Geschätzte Mutanten |
|-------|-------|-------------------|
| `core` (default) | `core/prompts/`, `core/writing/`, `core/llm/intents.py` | ~150–200 |
| `api` | `apps/api/narrare/` | ~300–500 |
| `all` | core + api | ~500–800 |

### Ergebnisse interpretieren

```
Mutation score: 86%
Survived: 15/105

Survived Mutants:
- pipeline_scene.py:47 — replace `and` with `or`
  → Test fehlt für Edge-Case (None-content)
```

Eine überlebende Mutation bedeutet: **Es gibt keinen Test, der diesen spezifischen Fehler fangen würde.** Das ist nicht immer ein Problem — manche Mutationen sind semantisch äquivalent (z.B. optimierte Bedingungen). Aber ein niedriger Score in Kernlogik (prompts/, writing/) ist ein Signal zum Handeln.

### Workflow

1. **Monatlicher Report** wird automatisch erstellt
2. **Issue gepostet** mit Label `mutation-testing`
3. **Team reviewed** die überlebenden Mutationen
4. **Targeted fixes** für echte Lücken (kein "Score-Jagd")
5. **Nächster Lauf** zeigt Verbesserung

## Zusammenspiel

```
Assertion-Audit (findet schwache Tests)     MutMut (findet ungetestetes Verhalten)
         │                                            │
         └──────────► Targeted Test-Verbesserung ◄────┘
                              │
                              ▼
                   Höhere Testqualität
                   (nicht nur Coverage)
```

## Geschichte

- **2026-07-03:** Assertion-Audit-Skript erstellt (`scripts/audit_test_assertions.py`)
- **2026-07-03:** Erster Audit: 782 Files gescannt, 586 Funde in unit/, 474 in integration/
- **2026-07-03:** Top-Schwachstellen gefixt: 49x `match=` ergänzt, 10x schwache Assertions, 6x `model_validate`
- **2026-07-03:** MutMut CI-Workflow eingerichtet (`mutation-testing-monthly.yml`)
- **2026-07-04:** Sandbox-Aufräumung: redundanten `also_copy`/`mutants/packages/`-Mirror entfernt; `mutation_inert`-Marker + `bundled_prompts_root()`-Helper eingeführt; 12 Tests auf paket-relative Asset-Auflösung umgestellt (Konventionen siehe § Sandbox-Kompatibilität)
