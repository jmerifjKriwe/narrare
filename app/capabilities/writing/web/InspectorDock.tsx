/**
 * The inspector dock (W4 Tasks 11/20, W5 Tasks 1/2) — the scene-centric
 * draft's 320px right column, ported 1:1 onto the shell's tokens with the
 * gap doc's honest neutrals (D21: placeholders stay visibly neutral as
 * drafted):
 *
 * - Knowledge region: the registry's matched dock face through the
 *   Outlet, and nothing else. W5 Task 2 retired the #866/#867 interims
 *   (the dashed finding card, the neutral entity spotlight, the disabled
 *   wiki door): the knowledge wave is here, its content lives behind the
 *   Wissen tab, and a closed dock owes no placeholder promise.
 * - Header badge and tab badge: the real pending-findings count through
 *   the shell's query seam (the #866 family's retirement — the checker's
 *   own number, never an invented one; a pending or failed ask keeps the
 *   header's neutral dash, the tab wears no badge).
 * - Atmosphere grid: neutral „—" values (INTERIM #868 — no atmosphere
 *   fields exist on any model); the draft's scene label beside the grid
 *   is mock data and ships as the neutral too.
 * - Cover miniature: the ONE real card — the cover system's miniature,
 *   the book's own target_words, word_count and the derived progress
 *   (the shelf's floored-percent rule, never the draft's 4 %).
 * - Foot: the ⌘J assistant chip disabled with the canonical status note
 *   (INTERIM #869 — the chat wave owns the composer) and the
 *   Workspace-Layout tune disabled with the same note in its parenthetical
 *   (INTERIM #881 — light wins over the dark's enabled button).
 *
 * Task 20 finalized the family: the geometry is audited against both
 * faces of the round draft, every interim names its child issue, and the
 * cover miniature stands at the cover system's drafted size (36×48 — the
 * workspace draft's 48×64 chip is a mock object; the cover system owns
 * its sizes). The slots are the draft's: the waves replace content,
 * never slots.
 *
 * W5 Task 1 opened the knowledge slot: the dock registry (the generated
 * table, web/lib/generated/docks.ts) names one tab per capability dock,
 * and the matched dock child route renders through the Outlet in the
 * knowledge region. The composition is the generated route table's alone
 * (rule 1): this file imports no capability, only the registry, the
 * router and the shell's shared seams. The URL is the dock's whole open
 * state, so the back button closes it.
 */

import { Outlet, useChildMatches, useNavigate } from "@tanstack/react-router";

import type { Novel } from "@shell/lib/api/client";
import { BookCover } from "@shell/lib/cover/BookCover";
import { docks } from "@shell/lib/generated/docks";
import { useTranslation } from "@shell/lib/i18n";
import { useFindingsQuery } from "@shell/lib/query";
import { CARD_EYEBROW, FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import { progress } from "./shelf";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

export function InspectorDock({ novel }: { novel: Novel }) {
  const t = useTranslation();
  const navigate = useNavigate();
  // The checker's own count (W5 Task 2 — #866 retired): the pending
  // findings through the shell's query seam, the same cache the dock
  // face reads. A pending or failed ask is no number — the header keeps
  // the neutral dash and the tab wears no badge until the answer lands.
  const findings = useFindingsQuery(novel.id);
  const findingCount = findings.data?.length ?? 0;
  // The matched child — not a local flag — is the dock's open state, so
  // the URL is the whole truth and the back button closes it. The tab
  // for a registry row is pressed exactly while that row's own route is
  // the match; the workspace knows no dock by name (the registry is the
  // whole vocabulary, and a new dock appears by existing in it).
  const childMatches = useChildMatches();
  const activeDock = docks.find((dock) =>
    childMatches.some((match) => match.routeId === dock.path),
  );
  const result = progress(novel.word_count, novel.target_words);
  return (
    <aside
      aria-label={t("writing.workspace.dock.label")}
      className="flex h-full w-[320px] shrink-0 flex-col border-l border-border bg-surface-container-low/60 text-meta"
    >
      {/* The dock header — the checker's name and its real count (W5
          Task 2 — #866 retired). The badge reads the pending findings;
          the dash is the honest pending/failed state, never a permanent
          placeholder. The face's own diagnosis count is the live region
          when the dock is open; the badge is the labeled indicator. */}
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-border bg-panel px-3.5">
        <div className="flex items-center gap-2">
          <span className="text-primary">
            <Icon name="checkCircle" size={15} />
          </span>
          <h3 className={`${SERIF} text-body font-bold text-foreground`}>
            {t("writing.workspace.dock.title")}
          </h3>
        </div>
        <span
          data-testid="dock-findings-badge"
          role={findings.isSuccess ? "img" : undefined}
          aria-label={findings.isSuccess ? t("knowledge.dock.openCount", { count: findingCount }) : undefined}
          className={`rounded-full border border-border bg-surface-container-low px-2 py-0.5 font-mono text-[11px] ${
            findings.isSuccess && findingCount > 0 ? "text-warning" : "text-muted"
          }`}
        >
          {findings.isSuccess ? findingCount : "—"}
        </span>
      </div>

      {/* The dock registry's tabs (W5 Task 1) — the AI-dock draft's tab
          switcher, one tab per registry row, the row's own glyph (the
          icon set names the registry ids). Opening and closing are
          navigations to and from the dock child route; the pressed tab
          closes its dock. The draft's count badge (W5 Task 2 — #866
          retired) reads the real pending findings: the warning circle
          stands only while there is one, and never renames the tab. */}
      {docks.length > 0 && (
        <div
          role="group"
          aria-label={t("writing.workspace.dock.tabs")}
          className="flex shrink-0 items-center gap-1 border-b border-border bg-surface-container-low p-1.5"
        >
          {docks.map((dock) => {
            const active = activeDock?.id === dock.id;
            return (
              <button
                key={dock.id}
                type="button"
                aria-pressed={active}
                onClick={() =>
                  void navigate(
                    active
                      ? { to: "/novels/$novelId", params: { novelId: novel.id } }
                      : { to: dock.path, params: { novelId: novel.id } },
                  )
                }
                className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-meta font-medium transition-all ${FOCUS} ${
                  active
                    ? "bg-surface text-primary shadow-sm"
                    : "text-muted hover:bg-surface hover:text-foreground"
                }`}
              >
                <Icon name={dock.id} size={15} />
                <span>{t(dock.titleKey)}</span>
                {/* The checker's count rides the checker's dock: the
                    knowledge registry row is the face that reads the
                    findings (the id is the registry's own vocabulary,
                    the icon discipline's sibling). The badge is the
                    draft's warning circle, aria-hidden so the tab keeps
                    its name — the header badge carries the labeled
                    count. */}
                {dock.id === "knowledge" && findings.isSuccess && findingCount > 0 && (
                  <span
                    data-testid="dock-tab-badge"
                    aria-hidden="true"
                    className="flex h-4 w-4 items-center justify-center rounded-full bg-warning text-[10px] font-bold leading-none text-surface"
                  >
                    {findingCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      <div className="flex-1 space-y-3 overflow-y-auto p-3">
        {/* The knowledge region belongs to the registry's matched dock
            alone (W5 Task 2 — the #866/#867 interims retired): the
            capability's own face renders through the Outlet the generated
            route table parents here (rule 1 — no capability import); a
            closed dock stands empty in this region, the Wissen tab above
            is its door. The atmosphere and cover slots below stay
            standing: the waves replace content, never slots. */}
        {activeDock && <Outlet />}

        {/* Atmosphere — INTERIM #868: no atmosphere fields exist; the grid
            keeps its geometry with neutral values, the label neutral too
            (the draft's beside-label is mock data). */}
        <div data-testid="dock-atmosphere" className="space-y-2 rounded-lg border border-border bg-panel p-3 shadow-card">
          <div className="flex items-center justify-between">
            <span className={CARD_EYEBROW}>{t("writing.workspace.dock.atmosphere")}</span>
            <span className="font-mono text-[10px] text-muted">—</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1 rounded border border-border bg-surface-container-low p-2">
              <span className="block text-[9.5px] font-semibold uppercase text-muted">
                {t("writing.workspace.dock.light")}
              </span>
              <span className="font-mono text-meta font-medium text-muted">—</span>
            </div>
            <div className="space-y-1 rounded border border-border bg-surface-container-low p-2">
              <span className="block text-[9.5px] font-semibold uppercase text-muted">
                {t("writing.workspace.dock.acoustics")}
              </span>
              <span className="font-mono text-meta font-medium text-muted">—</span>
            </div>
          </div>
        </div>

        {/* Cover miniature — the dock's one REAL card: the cover system's
            object, the book's own target and count, the derived progress
            (the shelf's floored rule). A missing target keeps the honest
            neutral: no percent, an empty track. */}
        <div data-testid="dock-cover" className="space-y-2.5 rounded-lg border border-border bg-panel p-3 shadow-card">
          <div className="flex items-center justify-between">
            <span className={CARD_EYEBROW}>{t("writing.workspace.dock.meta")}</span>
            <span className="font-mono text-[10px] font-semibold text-primary">
              {result !== null ? t("writing.workspace.dock.percentTotal", { percent: result.percent }) : "—"}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <BookCover title={novel.title} genre={novel.genre} author={novel.author} size="mini" />
            <div className="min-w-0 flex-1 space-y-1">
              <p className={`${SERIF} truncate text-body font-semibold text-foreground`}>{novel.title}</p>
              <p className="text-[11px] text-muted">
                {t("writing.workspace.dock.target")}{" "}
                <strong className="font-mono text-foreground">
                  {novel.target_words != null
                    ? t("writing.workspace.tree.words", { count: novel.target_words })
                    : "—"}
                </strong>
              </p>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-border">
                {result !== null && (
                  <div className="h-full rounded-full bg-primary" style={{ width: `${result.width}%` }} />
                )}
              </div>
              <p className="font-mono text-[10px] text-muted">
                {t("writing.workspace.dock.captured", { count: novel.word_count })}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* The dock foot — INTERIM #869 (⌘J, the chat wave) and #881 (the
          layout tune). The chips keep their geometry and their marks. */}
      <div data-testid="dock-foot" className="shrink-0 space-y-2 border-t border-border bg-panel/70 p-3">
        <div className="flex items-center justify-between gap-1.5">
          <div
            aria-disabled="true"
            className="flex flex-1 cursor-not-allowed select-none items-center justify-between rounded border border-border/70 bg-surface-container-low/50 px-2.5 py-1.5 text-muted opacity-60"
          >
            <div className="flex items-center gap-1.5">
              {/* The command mark is the app's own SVG and the J the bundled
                  mono's real glyph — no U+2318 rides a system face. */}
              <kbd className="inline-flex items-center gap-px rounded border border-border bg-surface-container-low px-1 font-mono text-[10px]">
                <Icon name="command" size={10} />
                J
              </kbd>
              <span className="text-meta">{t("writing.workspace.dock.assistant")}</span>
            </div>
            <span data-testid="dock-soon-badge" className="rounded bg-surface-container-low px-1 py-0.5 font-mono text-[9px] uppercase tracking-wider text-muted">
              {t("writing.workspace.dock.soon")}
            </span>
          </div>
          <button
            type="button"
            disabled
            aria-label={t("writing.workspace.dock.layout")}
            title={`${t("writing.workspace.dock.layout")} (${t("writing.workspace.dock.layoutNote")})`}
            className="cursor-not-allowed rounded border border-border/70 bg-surface-container-low/50 p-1.5 text-muted opacity-60"
          >
            <Icon name="gridView" size={15} />
          </button>
        </div>
      </div>
    </aside>
  );
}
