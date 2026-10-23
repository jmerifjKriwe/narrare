# Third-party notices

Narrare's own code is MIT-licensed; see [LICENSE](LICENSE). This file records
the third-party material that lives in this repository, so the MIT grant is
never read as covering work it cannot license. Every entry names its source,
and the license of each entry stays with it.

Provenance of the agent skills is recorded here rather than in
`skills-lock.json`: that file is local installer state (git-ignored) and also
tracks skills installed outside this repository.

## Vendored agent skills (`.agents/skills/`)

| Skill | Source | License | Notice |
| --- | --- | --- | --- |
| building-pydantic-ai-agents | [pydantic/skills](https://github.com/pydantic/skills) | MIT | [LICENSE](.agents/skills/building-pydantic-ai-agents/LICENSE) |
| frontend-design | [anthropics/skills](https://github.com/anthropics/skills) | Apache-2.0 | [LICENSE.txt](.agents/skills/frontend-design/LICENSE.txt), bundled with the skill |
| mem0 | [mem0ai/mem0](https://github.com/mem0ai/mem0) | Apache-2.0 | [LICENSE](.agents/skills/mem0/LICENSE), bundled with the skill |
| shadcn | [shadcn/ui](https://github.com/shadcn-ui/ui) | MIT | [LICENSE.md](.agents/skills/shadcn/LICENSE.md) |
| tailwind-design-system | [wshobson/agents](https://github.com/wshobson/agents) | MIT | [LICENSE](.agents/skills/tailwind-design-system/LICENSE) |
| vercel-composition-patterns | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | MIT | declared in the skill's frontmatter; the source repository ships no license file |
| vercel-react-best-practices | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | MIT | declared in the skill's frontmatter; the source repository ships no license file |
| vercel-react-view-transitions | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | MIT | declared in the skill's frontmatter; the source repository ships no license file |
| web-design-guidelines | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | none declared | **Open item:** no license statement in the skill and no license file in the source repository — clarify upstream or remove the skill |
| remediate-review | — | first-party | Narrare's own; covered by the MIT grant |

The Apache-2.0 entries keep the license text bundled with the vendored copy,
as section 4 of that license requires; the MIT entries carry the upstream
license text so the copyright notice travels with the copy.

## OpenCode harness material (`.opencode/`)

| Skill | Source | License | Notice |
| --- | --- | --- | --- |
| context7 | built around the Context7 API; the [upstash/context7](https://github.com/upstash/context7) project is MIT | none declared | **Open item:** not tracked in `skills-lock.json` and carries no license statement — clarify the source or replace |
| task-management | unclear (author "opencode"; not present in opencode-ai/opencode) | none declared | **Open item:** not tracked in `skills-lock.json` and carries no license statement — clarify the source or replace |

`.opencode/agents/` (NarrareBuilder, NarrareReviewer) is first-party.

## The built web app (`web/dist/`)

The production bundle inlines the web application's production dependency
closure (when this was written: 70 MIT, 1 BSD-3-Clause, 1 Unlicense). The
minifier strips their license comments, so `pnpm build` renders
`web/dist/THIRD-PARTY-NOTICES.txt` from `pnpm licenses list --prod`, and the
API serves it at `/THIRD-PARTY-NOTICES.txt`. That file travels with every
served copy of the app and is the compliance artifact for the bundled
libraries.

## Python dependencies

Not vendored: `uv` installs each package together with its own license, so
nothing in this repository redistributes them. A future container image that
distributes the installed packages must carry the Apache-2.0 license texts of
`asyncpg` and `python-multipart` — an SBOM does not replace that.
