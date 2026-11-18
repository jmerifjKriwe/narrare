/**
 * The inspector dock (W4 Tasks 11/20) — the scene-centric draft's 320px right
 * column, ported 1:1 onto the shell's tokens with the gap doc's honest
 * neutrals (D21: placeholders stay visibly neutral as drafted):
 *
 * - Finding card: dashed placeholder, „—", „Keine offenen Brüche — Wird
 *   mit der Wissens-Welle aktiv" (INTERIM #866 — the findings API exists,
 *   D4 defers the content to the knowledge wave).
 * - Entity spotlight: neutral „—" fields, „Wiki öffnen" disabled
 *   (INTERIM #867). The dark face draws the button enabled — light wins.
 * - Atmosphere grid: neutral „—" values (INTERIM #868 — no atmosphere
 *   fields exist on any model); the draft's scene label beside the grid
 *   is mock data and ships as the neutral too.
 * - Cover miniature: the ONE real card — the cover system's miniature,
 *   the book's own target_words, word_count and the derived progress
 *   (the shelf's floored-percent rule, never the draft's 4 %).
 * - Foot: the ⌘J assistant chip disabled with the „bald" mark (INTERIM
 *   #869 — the chat wave owns the composer) and the Workspace-Layout tune
 *   disabled with the draft's own parenthetical „später verfügbar"
 *   (INTERIM #881 — light wins over the dark's enabled button).
 *
 * Task 20 finalized the family: the geometry is audited against both
 * faces of the round draft, every interim names its child issue, and the
 * cover miniature stands at the cover system's drafted size (36×48 — the
 * workspace draft's 48×64 chip is a mock object; the cover system owns
 * its sizes). The slots are the draft's: the knowledge/chat waves replace
 * content, never slots.
 *
 * W5 Task 1 opens the knowledge slot: the dock registry (the generated
 * table, web/lib/generated/docks.ts) names one tab per capability dock,
 * and the matched dock child route renders through the Outlet in the
 * knowledge region — the finding card and the entity spotlight yield to
 * the capability's own face. The composition is the generated route
 * table's alone (rule 1): this file imports no capability, only the
 * registry and the router. With no dock child matched the interim
 * neutrals stand — the URL is the dock's whole open state, so the back
 * button closes it. The tab's count badge and the header badge retire
 * with #866 in Task 2.
 */

import { Outlet, useChildMatches, useNavigate } from "@tanstack/react-router";

import type { Novel } from "@shell/lib/api/client";
import { BookCover } from "@shell/lib/cover/BookCover";
import { docks } from "@shell/lib/generated/docks";
import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

import { progress } from "./shelf";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The draft's card eyebrow — the micro-label above each card's content. */
const CARD_EYEBROW = "text-[10px] font-bold uppercase tracking-wider text-muted";

/** One neutral field row — the label left, the dash right, mono. */
function NeutralRow({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-between text-meta">
      <span className="text-muted">{label}</span>
      <span className="font-mono text-muted">—</span>
    </div>
  );
}

/** The shell's focus ring on every control the dock offers. */
const FOCUS = "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

export function InspectorDock({ novel }: { novel: Novel }) {
  const t = useTranslation();
  const navigate = useNavigate();
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
      {/* The dock header — the checker's name and the neutral badge. The
          badge is the checker's own count: it ships „—" with the finding
          card's family (INTERIM #866 — Task 2 retires it with the count). */}
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-border bg-panel px-3.5">
        <div className="flex items-center gap-2">
          <span className="text-primary">
            <Icon name="checkCircle" size={15} />
          </span>
          <h3 className={`${SERIF} text-body font-bold text-foreground`}>
            {t("writing.workspace.dock.title")}
          </h3>
        </div>
        <span className="rounded-full border border-border bg-surface-container-low px-2 py-0.5 font-mono text-[11px] text-muted">
          —
        </span>
      </div>

      {/* The dock registry's tabs (W5 Task 1) — the AI-dock draft's tab
          switcher, one tab per registry row, the row's own glyph (the
          icon set names the registry ids). Opening and closing are
          navigations to and from the dock child route; the pressed tab
          closes its dock. The count badge the draft draws beside the
          label rides with #866's retirement (Task 2). */}
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
              </button>
            );
          })}
        </div>
      )}

      <div className="flex-1 space-y-3 overflow-y-auto p-3">
        {activeDock ? (
          /* The knowledge region yields to the registry's matched dock:
             the capability's own face renders through the Outlet the
             generated route table parents here (rule 1 — no capability
             import). The atmosphere and cover slots below stay standing:
             the waves replace content, never slots. */
          <Outlet />
        ) : (
          <>
            {/* Fund-Karte — INTERIM #866: the dashed placeholder, the
                knowledge wave fills it from the findings API (the Wissen
                tab above opens the live face; Task 2 retires the interim).
                No invented finding. */}
            <div data-testid="dock-finding" className="rounded-lg border border-dashed border-border bg-panel p-3">
              <div className="mb-1.5 flex items-center justify-between">
                <span className={CARD_EYEBROW}>{t("writing.workspace.dock.finding")}</span>
                <span className="font-mono text-muted">—</span>
              </div>
              <div className="space-y-1 py-3 text-center">
                <span className="inline-block text-muted/60">
                  <Icon name="clock" size={20} />
                </span>
                <p className="text-meta font-medium text-muted">{t("writing.workspace.dock.findingEmpty")}</p>
                <p className="text-[10px] text-muted">{t("writing.workspace.dock.findingNote")}</p>
              </div>
            </div>

            {/* Entity spotlight — INTERIM #867: neutral fields, the wiki
                door disabled until the knowledge wave serves the content
                (Task 2 fills the dock's entity face). */}
            <div data-testid="dock-entity" className="space-y-2.5 rounded-lg border border-border bg-panel p-3 shadow-card">
              <div className="flex items-center justify-between">
                <span className={CARD_EYEBROW}>{t("writing.workspace.dock.entity")}</span>
                <span className="font-mono text-muted">—</span>
              </div>
              <div className="space-y-1.5 py-1">
                <NeutralRow label={t("writing.workspace.dock.entityName")} />
                <NeutralRow label={t("writing.workspace.dock.entityFirst")} />
                <NeutralRow label={t("writing.workspace.dock.entityBinding")} />
              </div>
              <button
                type="button"
                disabled
                title={t("writing.workspace.dock.wikiNote")}
                className="flex w-full cursor-not-allowed items-center justify-center gap-1 rounded border border-border/70 bg-surface-container-low/60 px-2 py-1.5 text-[11px] font-medium text-muted opacity-60"
              >
                <Icon name="menuBook" size={12} />
                <span>{t("writing.workspace.dock.wiki")}</span>
              </button>
            </div>
          </>
        )}

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
              <kbd className="rounded border border-border bg-surface-container-low px-1 font-mono text-[10px]">
                ⌘J
              </kbd>
              <span className="text-meta">{t("writing.workspace.dock.assistant")}</span>
            </div>
            <span className="rounded bg-surface-container-low px-1 py-0.5 font-mono text-[9px] uppercase tracking-wider text-muted">
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
