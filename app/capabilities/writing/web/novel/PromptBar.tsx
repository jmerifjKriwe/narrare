import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

/**
 * The floating prompt bar (the draft's "AI assistant launcher"): a pill
 * below the card holding the style chip, the inline prompt field and the
 * Weiterschreiben trigger, with the three quick prompts beneath it.
 *
 * It is honest about what it can send (D-4). The one control that does
 * what it says is the Weiterschreiben trigger — the same continuation the
 * runhead's button above the card starts, frozen while that stream runs.
 * The field and the pills stand `aria-disabled` with the reason on their
 * titles, readonly rather than natively disabled, so the reason stays in
 * the tab order and reachable by reader and pointer alike (the band's
 * history-button idiom). The trigger chip names no style yet — the honest
 * placeholder, not a fiction about presets the app does not have.
 *
 * The pill is the launcher's own drafted shape, the one the ghost's
 * keycap hint already speaks; the bar yields with the frame at focus
 * depth 2, where the draft's paper is the prose alone.
 */

/** The quick prompts, in the draft's own order. */
const QUICK_PROMPTS = [
  "chapters.promptQuickTension",
  "chapters.promptQuickDialogue",
  "chapters.promptQuickDetail",
] as const;

export function PromptBar({
  onContinue,
  disabled,
}: {
  onContinue: () => void;
  disabled: boolean;
}) {
  const t = useTranslation();
  return (
    <div
      role="group"
      aria-label={t("chapters.promptBarLabel")}
      data-prompt-bar
      className="mt-8 flex flex-col items-center gap-2 lg:sticky lg:bottom-6 lg:z-20"
    >
      {/* The launcher pill: the surface a step above the paper, blurred
          behind and carrying the floating pair's shadow — the overlay
          tokens are what floats above the page, and this does. */}
      <div className="flex w-full max-w-xl items-center gap-2 rounded-full bg-surface/95 p-1.5 shadow-overlay backdrop-blur-xl">
        {/* The context trigger (the draft's neurology chip): what the
            continuation would read. It names no style, because there is
            none to name:
            interim: no style presets — follow-up filed in W3's index */}
        <span
          data-prompt-style
          className="flex shrink-0 items-center gap-1.5 rounded-full bg-surface-container-low py-1 pr-3 pl-2.5 text-label text-muted"
        >
          <span aria-hidden="true" className="text-area-writing">
            <Icon name="neurology" />
          </span>
          {t("chapters.promptStyle")}
        </span>
        {/* The inline prompt field (the draft's input): dressed, and
            unable to take a prompt — nothing typed here can reach the
            continuation, which takes no prompt parameter. Readonly keeps
            the field in the tab order, so the title's reason is one Tab
            away for a keyboard or screen reader.
            interim: no prompt parameter on the continuation endpoint — follow-up filed in W3's index */}
        <input
          type="text"
          data-prompt-input
          aria-label={t("chapters.promptLabel")}
          placeholder={t("chapters.promptPlaceholder")}
          readOnly
          aria-disabled="true"
          title={t("chapters.promptDisabled")}
          className="h-8 min-w-0 flex-1 border-0 bg-transparent p-0 px-1 text-body text-foreground placeholder:text-muted focus-visible:outline-hidden"
        />
        {/* The working trigger: the drafted words on the terracotta cover
            ground, the object tone the shelf's drafted CTA wears — the
            screen's one `--primary` fill stays the runhead's (L1), and
            the pill is the launcher's own shape. */}
        <button
          type="button"
          data-prompt-continue
          onClick={onContinue}
          disabled={disabled}
          className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-full bg-cover-sepia px-3.5 text-label text-cover-sepia-ink shadow-sm transition-opacity hover:opacity-95 disabled:opacity-50 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent"
        >
          <Icon name="spark" />
          {t("chapters.continue")}
        </button>
      </div>
      {/* The quick prompts (the draft's suggestion pills): real copy in
          the band's chip clothes — and as unable to send as the field
          above them.
          interim: no prompt parameter on the continuation endpoint — follow-up filed in W3's index */}
      <div data-prompt-quicks className="flex flex-wrap items-center justify-center gap-2">
        {QUICK_PROMPTS.map((key) => (
          <button
            key={key}
            type="button"
            aria-disabled="true"
            title={t("chapters.promptDisabled")}
            className="rounded-full bg-surface-container-low px-2.5 py-1 text-meta text-muted opacity-50"
          >
            {t(key)}
          </button>
        ))}
      </div>
    </div>
  );
}
