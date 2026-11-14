# Procedural Book Cover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A reusable, deterministic procedural book-cover component (pure CSS/SVG) that the W2 setup wizard's live preview and the W3+ shelf both consume, ported from the owner-approved Stitch cover-system spec.

**Architecture:** A shell-shared module under `web/lib/cover/` (capabilities import the shell via `@shell`, never each other). Pure logic (hash, genre→channel mapping, variant axis, size detail tiers, edge normalization) is separated from the presentational component and the SVG motifs so each is unit-testable. Grounds/inks are design tokens in `web/globals.css`, drift-gated by `web/lib/tokens.test.ts`. No backend change: `title`, `genre`, `author` already exist on the novel.

**Tech Stack:** React 19, Tailwind CSS v4, TypeScript, vitest (+ `@testing-library/react`, jsdom per-file), MurmurHash3 x86_32 implemented locally (no new dependency).

**Spec:** `docs/design/stitch/screens/library/cover-system.html` (authoritative detail; the `.webp` beside it is a downscaled preview only). Wave context: `docs/superpowers/specs/2026-11-13-frontend-rebuild-design.md` (W2 wizard cover preview, W3 shelf).

## Global Constraints

- Covers are pure CSS/SVG book objects; never AI/stock imagery (spec intro).
- Lyrik is deliberately outside the genre matrix; it and any unknown genre fall to the neutral fallback (owner decision 2026-11-14).
- Canonical view sizes, exact: wizard `224×300`, hero `192×264`, shelf `144×200`, mini `36×48` (spec Sektion 04).
- Variant axis = `MurmurHash3(title) % 3` → 0 centered, 1 offset/diagonal, 2 monumental whitespace (spec Sektion 03).
- Long title (>60 chars): three-line clamp, **no ellipsis**, vignette recedes (spec Sektion 05 A).
- Dark mode: no colour inversion; grounds keep their pigment; add a 1px rim `rgba(255,255,255,0.08)` and a deeper contact shadow (spec Sektion 06).
- Every ground/ink pair clears WCAG AA 4.5:1 in both themes; `tokens.test.ts` is the drift gate.
- German copy uses **du**; all user-facing strings go through `t()` with keys present in **all three** catalogs (de/en/fr parity is a build error).
- Shared shell code lives in `web/`; import it as `@shell/lib/cover/…`. Capabilities never import each other.
- Commits: hidden type (`chore(web)` / `test(web)`) while no screen consumes the component; human author/committer; trailer `Assisted-by: OpenCode (<model>)`; no `--no-verify`, no force push.

## Review Focus

- Title longer than 60 chars (or a single mammoth word): clamps to three lines, no ellipsis, no layout break, vignette recedes.
- `genre` null / empty / unknown string (incl. Lyrik): neutral fallback ground + atelier-seal motif, never a crash or a blank cover.
- `author` null / empty / whitespace: elegant localized "Anonymus" placeholder, layout intact.
- Same title → identical variant on every render; two same-genre titles → not forced identical (hash spreads over the 3 axes).
- Mini size: monogram only, secondary ornaments culled, nothing overflows the 36×48 box.

## File Structure

- Create `web/lib/cover/hash.ts` — MurmurHash3 x86_32, pure.
- Create `web/lib/cover/hash.test.ts` — node env, known-answer + properties.
- Create `web/lib/cover/cover.ts` — channel/variant/size/edge model, pure.
- Create `web/lib/cover/cover.test.ts` — node env, pins mapping + tiers + edges.
- Modify `web/globals.css` — four new genre grounds + inks (+ `--color-cover-*` aliases).
- Modify `web/lib/tokens.test.ts` — extend `PAIRS` + `TEXT_PAIRS`.
- Create `web/lib/cover/motifs.tsx` — the eight hairline SVG vignettes + fallback seal.
- Create `web/lib/cover/motifs.test.tsx` — jsdom, one per channel.
- Create `web/lib/cover/BookCover.tsx` — the presentational book object.
- Create `web/lib/cover/BookCover.test.tsx` — jsdom, sizes/edges/dark/determinism.
- Modify the three i18n catalogs backing `web/lib/i18n.ts` — `cover.genre.*`, `cover.anonymous`.

### Token reconciliation (design note for review)

The spec's canonical light hexes for Mystery `#EEEBE5`, Literary `#743B1F`, Historical `#3A637B` equal the existing `--cover-pale` / `--cover-sepia` / `--cover-slate` light values, so those three channels reuse the legacy tokens (their measured dark halves stay). Sci-Fi reuses `--cover-ink`; the spec's canonical `#1A1815` differs slightly from the token's measured `#24211C` — flagged for the owner/Reviewer, not silently retuned (the norm is measured, `dark-tokens.md`). The four genuinely new channels (Fantasy, Romance, Thriller, Fallback) are added **theme-constant** (light = dark), which is the spec's "no inversion" rule and invents no dark shade; their inks follow the existing convention (parchment `#FFF8F2` on dark grounds, `#1E1B16` on light grounds). If the owner prefers a fully genre-named theme-constant palette instead, that is a one-task swap of the mapping table.

---

### Task 1: MurmurHash3

**Files:**
- Create: `web/lib/cover/hash.ts`
- Test: `web/lib/cover/hash.test.ts`

**Interfaces:**
- Produces: `export function murmur3_32(key: string, seed?: number): number` — unsigned 32-bit MurmurHash3 x86_32, default seed 0.

- [ ] **Step 1: Write the failing test** (`// @vitest-environment node`)

```ts
import { describe, expect, it } from "vitest";
import { murmur3_32 } from "./hash";

describe("murmur3_32", () => {
  it("matches the canonical seed-0 vectors", () => {
    expect(murmur3_32("")).toBe(0);
    expect(murmur3_32("hello")).toBe(0x248bfa47);
  });
  it("is deterministic and stays an unsigned 32-bit integer", () => {
    for (const s of ["Dead Signal", "Echo", "Im Stillen Wald", "x".repeat(200)]) {
      const a = murmur3_32(s);
      expect(a).toBe(murmur3_32(s));
      expect(Number.isInteger(a)).toBe(true);
      expect(a).toBeGreaterThanOrEqual(0);
      expect(a).toBeLessThanOrEqual(0xffffffff);
    }
  });
});
```

- [ ] **Step 2: Run to verify it fails** — `cd web && pnpm vitest run lib/cover/hash.test.ts`; expected FAIL (module missing).
- [ ] **Step 3: Implement** the standard MurmurHash3 x86_32 (32-bit blocks, tail switch, fmix32; use `Math.imul` and `>>> 0`). Signature as above; no other exports.
- [ ] **Step 4: Run to verify it passes** — same command; expected PASS.
- [ ] **Step 5: Commit** — `chore(web): the cover's deterministic title hash` + trailer.

### Task 2: Cover model (mapping, variant, sizes, edges)

**Files:**
- Create: `web/lib/cover/cover.ts`
- Test: `web/lib/cover/cover.test.ts`

**Interfaces:**
- Consumes: `murmur3_32` from Task 1.
- Produces:
  - `export type CoverChannel = "scifi"|"fantasy"|"mystery"|"literary"|"historical"|"romance"|"thriller"|"fallback"`
  - `export type CoverSize = "wizard"|"hero"|"shelf"|"mini"`
  - `export const COVER_SIZES: Record<CoverSize, { width: number; height: number }>`
  - `export function channelFor(genre: string | null | undefined): CoverChannel`
  - `export function variantFor(title: string): 0 | 1 | 2`
  - `export function coverModel(input: { title: string; genre?: string | null; author?: string | null; size: CoverSize }): CoverModel`
  - `export interface CoverModel { channel: CoverChannel; variant: 0|1|2; groundToken: string; inkToken: string; width: number; height: number; showEyebrow: boolean; showAuthor: boolean; showVignette: boolean; monogram: boolean; monogramText: string; authorName: string; anonymous: boolean; longTitle: boolean; shortTitle: boolean }`

- [ ] **Step 1: Write the failing test** (node env). Pin, with the spec's exact values:
  - `COVER_SIZES` equals `{wizard:{width:224,height:300},hero:{width:192,height:264},shelf:{width:144,height:200},mini:{width:36,height:48}}`.
  - `channelFor("Science Fiction")==="scifi"`, `"Fantasy"→fantasy`, `"Mystery"→mystery`, `"Literary"→literary`, `"Historical"→historical`, `"Romance"→romance`, `"Thriller"→thriller`; case-insensitive; `null`, `""`, `"Lyrik"`, `"Essayistik"`, `"unknown"→fallback`.
  - `variantFor(t) === murmur3_32(t) % 3` and is stable across calls.
  - `coverModel({title:"Dead Signal",genre:"Science Fiction",author:"K. V. Holm",size:"wizard"})` → `groundToken:"cover-ink"`, `showVignette:true`, `showAuthor:true`, `anonymous:false`, `monogram:false`.
  - size tiers: `shelf` → `showVignette:false`; `mini` → `monogram:true`, `showEyebrow:false`, `showAuthor:false`, `showVignette:false`; `hero` → vignette true.
  - edges: title of 70 chars → `longTitle:true`, `showVignette:false`; `author:null` and `author:"  "` → `anonymous:true`, `authorName:""`; `title:"Echo"` → `shortTitle:true`; `title:"Dead Signal"` mini → `monogramText:"DS"`; empty title mini → `monogramText:"N"`.
  - mapping table: scifi→`cover-ink`/`cover-ink-ink`, mystery→`cover-pale`/`cover-pale-ink`, literary→`cover-sepia`/`cover-sepia-ink`, historical→`cover-slate`/`cover-slate-ink`, fantasy→`cover-fantasy`/`cover-fantasy-ink`, romance→`cover-romance`/`cover-romance-ink`, thriller→`cover-thriller`/`cover-thriller-ink`, fallback→`cover-fallback`/`cover-fallback-ink`.
- [ ] **Step 2: Run to verify it fails** — `pnpm vitest run lib/cover/cover.test.ts`.
- [ ] **Step 3: Implement** `cover.ts`. `channelFor` normalizes (trim+lowercase) against a fixed alias map (English + German labels, e.g. "historischer roman"→historical, "literary fiction"→literary); default fallback. `monogramText` = first letters of the first two title words uppercased, or "N" when empty. `longTitle` = trimmed length > 60; `shortTitle` = exactly one word (trimmed, non-empty). No i18n here (pure).
- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit** — `chore(web): the cover's genre, variant and size model` + trailer.

### Task 3: Genre tokens + drift gate

**Files:**
- Modify: `web/globals.css` (after the existing `--cover-*` block, ~line 128, and the `--color-cover-*` alias block ~line 248)
- Modify: `web/lib/tokens.test.ts` (`PAIRS`, `TEXT_PAIRS`)

**Interfaces:**
- Produces tokens: `--cover-fantasy:#2C382E`, `--cover-fantasy-ink:#FFF8F2`, `--cover-romance:#633B3E`, `--cover-romance-ink:#FFF8F2`, `--cover-thriller:#1D2228`, `--cover-thriller-ink:#FFF8F2`, `--cover-fallback:#DFD7CB`, `--cover-fallback-ink:#1E1B16` (theme-constant), plus matching `--color-cover-*` aliases.

- [ ] **Step 1: Extend the failing gate** — add to `PAIRS`: `"cover-fantasy":["#2C382E","#2C382E"]`, `"cover-fantasy-ink":["#FFF8F2","#FFF8F2"]`, `"cover-romance":["#633B3E","#633B3E"]`, `"cover-romance-ink":["#FFF8F2","#FFF8F2"]`, `"cover-thriller":["#1D2228","#1D2228"]`, `"cover-thriller-ink":["#FFF8F2","#FFF8F2"]`, `"cover-fallback":["#DFD7CB","#DFD7CB"]`, `"cover-fallback-ink":["#1E1B16","#1E1B16"]`; add to `TEXT_PAIRS` the four `["cover-<g>-ink","cover-<g>",4.5]`.
- [ ] **Step 2: Run to verify it fails** — `pnpm vitest run lib/tokens.test.ts`; expected FAIL (tokens missing).
- [ ] **Step 3: Add the tokens + aliases** in `globals.css` with a comment citing spec Sektion 02/06 (theme-constant, no inversion; rim-light lives in the component).
- [ ] **Step 4: Run to verify it passes** (both the pair gate and the contrast gate).
- [ ] **Step 5: Commit** — `chore(web): four genre grounds join the cover palette` + trailer.

### Task 4: Genre vignettes (SVG)

**Files:**
- Create: `web/lib/cover/motifs.tsx`
- Test: `web/lib/cover/motifs.test.tsx`

**Interfaces:**
- Consumes: `CoverChannel` from Task 2.
- Produces: `export function GenreMotif({ channel, className }: { channel: CoverChannel; className?: string }): ReactElement` — one hairline SVG per channel, `stroke="currentColor"`, `fill="none"` on the root (the spec's two filled dots — historical beacon, fallback seal center — keep their element-level `fill="currentColor"`), strokeWidth 1.2 (spec Sektion 02), `data-channel={channel}`, `aria-hidden="true"`.

- [ ] **Step 1: Write the failing test** (jsdom): for each of the 8 channels render `<GenreMotif channel={c}/>`; assert an `svg[data-channel=c]` exists and that the 8 channels produce 8 distinct `innerHTML` shapes (no two identical).
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement** the eight motifs per spec Sektion 02: scifi concentric rings r=14,6 + pulse line; fantasy star + astral arc; mystery blueprint rect 20×20 + escape lines; literary wave band (Q curve) + horizon; historical lighthouse geometry + fog edge; romance intertwined buds + botanical lines; thriller seismic crack + pulse; fallback dashed atelier-seal rect. Keep each a small pure SVG (viewBox 0 0 48 48).
- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit** — `chore(web): the eight hairline genre vignettes` + trailer.

### Task 5: BookCover component + i18n

**Files:**
- Create: `web/lib/cover/BookCover.tsx`
- Create: `web/lib/cover/BookCover.test.tsx`
- Modify: the three catalogs backing `web/lib/i18n.ts` (add `cover.genre.scifi|fantasy|mystery|literary|historical|romance|thriller|fallback`, `cover.anonymous`)

**Interfaces:**
- Consumes: `coverModel`, `COVER_SIZES`, `CoverSize` (Task 2); `GenreMotif` (Task 4); `useTranslation` (existing).
- Produces: `export function BookCover({ title, genre, author, size, className }: { title: string; genre?: string | null; author?: string | null; size?: CoverSize; className?: string }): ReactElement` (default size `"shelf"`).

- [ ] **Step 1: Write the failing test** (jsdom). Assert:
  - renders the title text and the localized genre eyebrow for a known genre.
  - `size="mini"` shows the monogram and NOT the full title / author / vignette.
  - `size="shelf"` renders no `svg[data-channel]` (vignette culled); `size="wizard"` renders one.
  - a 70-char title yields a 3-line clamp class and no "…" ellipsis character; vignette absent.
  - `author={null}` shows the localized `cover.anonymous` string.
  - `genre="Lyrik"` uses the fallback ground class (`bg-cover-fallback`) and the fallback seal motif.
  - two renders of the same props carry the same `data-variant`; the element exposes `data-variant` in {0,1,2}.
  - the root carries the dark rim/shadow classes and asymmetric rounding (`rounded-l-none`, right 6px).
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Add the i18n keys** to all three catalogs (du-tone German; English/French usual conventions), keeping parity.
- [ ] **Step 4: Implement `BookCover.tsx`**: root sized from `COVER_SIZES`, `bg-[var(--<groundToken>)] text-[var(--<inkToken>)]`, `rounded-l-none rounded-r-[6px] overflow-hidden relative`; a 14px spine gradient overlay (28% ink wedge + 1px 25% white refraction); eyebrow 10px `tracking-[0.2em]` uppercase; title EB Garamond italic with 3-line clamp (overflow hidden, no ellipsis) and a larger scale when `shortTitle`; author line; `GenreMotif` at 25–35% opacity behind the title when `showVignette`; mini renders only `monogramText`; dark rim via `border-t border-r border-b border-white/10` + a deeper contact shadow in the dark half. `data-variant` and `data-channel` exposed for tests.
- [ ] **Step 5: Run to verify it passes** — `pnpm vitest run lib/cover/BookCover.test.tsx`, then the whole web suite `pnpm vitest run` and `pnpm typecheck`.
- [ ] **Step 6: Commit** — `chore(web): the procedural book object, reusable by wizard and shelf` + trailer.

---

## Self-Review (completed)

- Spec coverage: anatomy (T5), genre matrix + tokens (T2,T3), variants (T1,T2,T5), sizes (T2,T5), edge cases (T2,T5 + Review Focus), dark mode (T3 comment,T5), motifs (T4). Lyrik exclusion pinned in T2 test. No backend task needed (fields exist).
- Type consistency: `CoverChannel`, `CoverSize`, `CoverModel`, `murmur3_32`, `GenreMotif`, `BookCover` names identical across tasks.
- Review Focus each has a test in T2/T5.
- Proportion: bodies left to the implementer except the hash algorithm reference and exact spec values; tests carry the assertions.