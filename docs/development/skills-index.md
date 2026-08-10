# Skills Index — Inventory & Navigation

> **Purpose**: Übersicht, wo welche Skill liegt und wofür sie gedacht ist. Die
> autoritative Beschreibung jeder Skill steht in ihrer `SKILL.md` — dieser Index
> dupliziert keinen Skill-Inhalt.
>
> **Pflege**: Documentation Specialist. Bei Skill-Änderungen (Add/Remove/Update)
> mitpflegen. Status: 25 Skills, 2 Quellen.

---

## 1. Skill-Quellen

| Quelle | Ort | Owner | Natur |
|--------|-----|-------|-------|
| **Tech-Skills** | `.agents/skills/<name>/` | Narrare (repo) | Stack-/Tech-spezifisch (vercel-labs/anthropics-Ökosystem) |
| **Prozess- & Tool-Skills** | `.opencode/skills/<name>/` | Narrare (repo) | Vendorte Prozess-Skills (ehem. superpowers) + Narrare-eigene Tools |

Beide werden von opencode einheitlich via `skill`-Tool on-demand geladen. Dritte Quelle
(ehem. superpowers-Plugin) entfällt — die Skills sind vendort, kein Plugin-Bootstrap mehr.

---

## 2. Tech-Skills — `.agents/skills/` (10)

| Skill | Kategorie | Zweck |
|-------|-----------|------|
| `building-pydantic-ai-agents` | AI Agents | Pydantic-AI-Agenten (Tools, Capabilities, Structured Output, Streaming, Testing). Core-RULE-01b. |
| `frontend-design` | Frontend | Distinktive, polierte UI/Oberflächen bauen. |
| `mem0` | Memory | mem0 AsyncMemory OSS (pgvector) Patterns. Core-RULE (core/memory). |
| `remediate-review` | Prozess | End-to-End-Remediation einer Audit-Review-Datei. |
| `shadcn` | Frontend | shadcn/ui-Komponenten (Registry, Add, Config). Frontend nutzt shadcn aktiv. |
| `tailwind-design-system` | Frontend | Tailwind v4 Design-Tokens, Responsive, System-Patterns. Frontend nutzt Tailwind v4. |
| `vercel-composition-patterns` | Frontend | Compound Components, Render-Props, Context, Component-API. |
| `vercel-react-best-practices` | Frontend | React/Next.js-Performance (Rendering, Bundle, Data-Fetching, Memo). |
| `vercel-react-view-transitions` | Frontend | View-Transition-API (Page-/Shared-Element-Animationen). |
| `web-design-guidelines` | Frontend | UI/A11y/UX-Review gegen Web Interface Guidelines. |

> **Frontend-Trigger-Abgrenzung**: siehe Routing-Tabelle in
> `.opencode/agents/subagents/narrare-dev/frontend.md` (genau EIN Skill je Anlass).

---

## 3. Prozess- & Tool-Skills — `.opencode/skills/` (15)

### 3.1 Vendorte Prozess-Skills (12, upstream `obra/superpowers`)

| Skill | Zweck |
|-------|------|
| `brainstorming` | Anforderungen/Design explorieren vor Implementierung. |
| `dispatching-parallel-agents` | ≥2 unabhängige Tasks parallel auf Subagenten verteilen. |
| `executing-plans` | Geschriebenen Implementierungsplan mit Review-Checkpoints ausführen. |
| `finishing-a-development-branch` | Abgeschlossene Arbeit integrieren (Merge-Entscheidung). |
| `receiving-code-review` | Review-Feedback technisch prüfen (nicht blind umsetzen). |
| `requesting-code-review` | Review anfordern, wenn Aufgabe/Feature fertig ist. |
| `subagent-driven-development` | Implementierungsplan mit unabhängigen Tasks in-Session ausführen. |
| `systematic-debugging` | Systematisches Debugging vor jedem Fix-Vorschlag. |
| `test-driven-development` | TDD (Red→Green→Refactor) vor Implementierungs-Code. |
| `using-git-worktrees` | Isolierten Workspace für Feature-Arbeit per Worktree. |
| `verification-before-completion` | Verifizieren (Befehle + Output) vor "fertig"/Commit. |
| `writing-plans` | Multi-Step-Plan aus Spec/Requirements, vor Code. |

Update der vendorten Skills: `just skills-update` (siehe `scripts/update-skills.sh`).

### 3.2 Narrare-eigene Tool-Skills (3)

| Skill | Zweck |
|-------|------|
| `graphify` | Code-Knowledge-Graph (`/graphify`, `graphify query/path/explain`). Ersetzt die alten Graph-MCPs. |
| `context7` | Aktuelle Lib-Doku (FastAPI, TipTap, Next.js, …) via Context7-API. |
| `task-management` | Task-Tracking-CLI (Status/Dependencies/Validierung). |

---

## 4. Wartung

- **Tech-Skills** aktualisieren: `just skills-update` (via `npx skills update`).
- **Vendorte Prozess-Skills** aktualisieren: dasselbe Script (git-fetch `obra/superpowers`).
- **Skills sperren**: Via `permission.skill` pro Agent (z. B. Reviewer: nur
  `test-driven-development` + `verification-before-completion`).
- **Neue Skill anlegen**: Verzeichnis unter `.agents/skills/` (Tech) oder
  `.opencode/skills/` (Prozess/Tool), `SKILL.md` mit `name`+`description` (name = dir name).
  Danach diesen Index pflegen.
