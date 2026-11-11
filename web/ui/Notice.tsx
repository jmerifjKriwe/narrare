import type { HTMLAttributes, ReactNode } from "react";

/**
 * The app's one state vocabulary: outage, empty, refresh-failure and
 * loading all speak through `Notice` — four tones, one card. The shell is
 * the drafted finding card's (spec §6.5): a hairline `--border` edge on
 * the surface radius, and the severity tones crown it with their own
 * colour as a 4 px rule on top — warning amber, danger rust — while
 * `info` and `quiet`, with nothing to raise, keep the plain edge. The
 * state colours (`--warning`, `--danger`) surface here and nowhere else
 * (§8.1); the census bans `text-danger` outside this file, which is why
 * `noticeClass` is exported — a surface that needs the danger voice
 * wears the whole notice, not a hand-picked red.
 *
 * The parked P1 rule binds the fill: no tone wears one. The card is its
 * edge and its rule; the ground stays the surface the notice rides. The
 * quiet tone's `text-muted` is legal on card, panel and ground, and below
 * AA on soft (4.43:1 light). `info` is foreground text: an informational
 * note has nothing to raise its voice about.
 *
 * Two slots, two shapes: `action` is the inline notice's one far-edge
 * control (the retry beside standing content), `actions` the finding
 * card's decision row below the message — the caller's primary/ghost
 * pair built on the button matrix, never button styles of this file's
 * own.
 *
 * `live` is the announcement contract, not decoration: `"alert"`
 * interrupts (`role="alert"` — the outage that took the content away),
 * `"status"` announces politely (`role="status"` — loading, refresh
 * failure beside standing content), `"none"` — the default — is silent:
 * the empty state is already on screen when the reader reaches it.
 *
 * The tone strings are pinned in `noticeClasses.test.ts`; the live →
 * role wiring is rendered beside it (jsdom — only the DOM can pin that a
 * caller's own `role` prop cannot override `live`), the axe pass is the
 * E2E suites'.
 */

/** The four voices a Notice speaks in. */
export const NOTICE_TONES = ["info", "warning", "danger", "quiet"] as const;
export type NoticeTone = (typeof NOTICE_TONES)[number];

/** The drafted card shell: the edge, the surface radius, the wrap. */
const NOTICE_BASE =
  "flex flex-wrap items-center gap-2 rounded-[var(--radius-surface)] border border-border px-3 py-2 text-body";

const TONE_CLASSES: Record<NoticeTone, string> = {
  info: `${NOTICE_BASE} text-foreground`,
  // The severity rule: the tone's own colour as a 4 px crown on the
  // card's top edge (the drafted finding card's top highlight rule).
  warning: `${NOTICE_BASE} border-t-4 border-t-warning text-warning`,
  danger: `${NOTICE_BASE} border-t-4 border-t-danger text-danger`,
  quiet: `${NOTICE_BASE} text-muted`,
};

/**
 * The whole look for one tone. Exported because this file is the only
 * place the state colours surface: the census's `text-danger = 0 outside
 * Notice` is kept by wearing `noticeClass("danger")`, never a bare
 * `text-danger` elsewhere.
 */
export function noticeClass(tone: NoticeTone): string {
  return TONE_CLASSES[tone];
}

export type NoticeProps = HTMLAttributes<HTMLDivElement> & {
  tone: NoticeTone;
  /** The announcement contract: alert interrupts, status informs, none is silent. */
  live?: "status" | "alert" | "none";
  /** One control at the far edge — the retry, or the empty state's first step. */
  action?: ReactNode;
  /** The finding card's decision row: the caller's primary/ghost pair. */
  actions?: ReactNode;
};

export function Notice({
  tone,
  live = "none",
  action,
  actions,
  className,
  children,
  ...rest
}: NoticeProps) {
  // Appended after the matrix: `noticeClass` is the contract, this the
  // extension (the P3 precedence).
  const classes = className
    ? `${noticeClass(tone)} ${className}`
    : noticeClass(tone);
  return (
    <div
      {...rest}
      // Set after the spread so the live mapping is the contract — a
      // caller's own role cannot contradict the `live` they named.
      role={
        live === "alert" ? "alert" : live === "status" ? "status" : undefined
      }
      className={classes}
    >
      {children}
      {action != null ? <div className="ml-auto shrink-0">{action}</div> : null}
      {/* The finding card's decision row: the full-width row wraps under
       * the message, so the plain notice's DOM — the words, maybe the one
       * far-edge control — stays exactly what it always was. */}
      {actions != null ? (
        <div className="flex w-full items-center gap-2 pt-1">{actions}</div>
      ) : null}
    </div>
  );
}
