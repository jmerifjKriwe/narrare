import type { HTMLAttributes, ReactNode } from "react";

/**
 * The app's one state vocabulary: outage, empty, refresh-failure and
 * loading all speak through `Notice` — four tones, one quiet form. The
 * form is deliberately unboxed: no fill, no edge (`--border` is for
 * surfaces), so a notice reads as the page speaking rather than a block
 * shouting. The state colours (`--warning`, `--danger`) surface here and
 * nowhere else (§8.1); the census bans `text-danger` outside this file,
 * which is why `noticeClass` is exported — a surface that needs the
 * danger voice wears the whole notice, not a hand-picked red.
 *
 * The parked P1 rule binds the form: no tone wears a `--soft` fill. The
 * quiet tone's `text-muted` is legal on card, panel and ground, and below
 * AA on soft (4.43:1 light). `info` is foreground text: an informational
 * note has nothing to raise its voice about.
 *
 * `live` is the announcement contract, not decoration: `"alert"`
 * interrupts (`role="alert"` — the outage that took the content away),
 * `"status"` announces politely (`role="status"` — loading, refresh
 * failure beside standing content), `"none"` — the default — is silent:
 * the empty state is already on screen when the reader reaches it.
 */

/** The four voices a Notice speaks in. */
export const NOTICE_TONES = ["info", "warning", "danger", "quiet"] as const;
export type NoticeTone = (typeof NOTICE_TONES)[number];

const NOTICE_BASE = "flex items-center gap-2 px-3 py-2 text-body";

const TONE_CLASSES: Record<NoticeTone, string> = {
  info: `${NOTICE_BASE} text-foreground`,
  warning: `${NOTICE_BASE} text-warning`,
  danger: `${NOTICE_BASE} text-danger`,
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
};

export function Notice({
  tone,
  live = "none",
  action,
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
    </div>
  );
}
