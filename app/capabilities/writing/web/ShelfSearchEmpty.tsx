/**
 * The empty search result — undrafted, so the `shelf-empty` family's
 * honest variant (Task 7's disclosure): the same panel chrome (the low
 * surface, the rule border, the two soft glows), the serif du-tone
 * invitation one step down from the empty shelf's own (this panel stands
 * in the grid's place, under the hero), and one live door — clear the
 * search and the facets together, the way back to the whole shelf. No
 * blank book object: that one speaks for the absence of any book, and
 * here the books exist, they only do not answer.
 */

import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on the one control this panel offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

export function ShelfSearchEmpty({ onClear }: { onClear: () => void }) {
  const t = useTranslation();
  return (
    <section className="relative flex flex-col items-center justify-center overflow-hidden rounded-xl border border-rule bg-surface-container-low p-6 text-center shadow-sm lg:p-8">
      {/* The two soft glows — the empty family's ambient depth. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-24 -top-24 h-80 w-80 rounded-full bg-cover-sepia opacity-5 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-24 -right-24 h-80 w-80 rounded-full bg-primary opacity-5 blur-3xl"
      />
      <div className="relative z-10 max-w-xl space-y-3">
        <h2 className={`${SERIF} text-title font-semibold tracking-tight text-primary`}>
          {t("writing.shelf.search.empty.title")}
        </h2>
        <p className={`${SERIF} text-body italic leading-relaxed text-muted`}>
          {t("writing.shelf.search.empty.body")}
        </p>
      </div>
      <div className="relative z-10 pt-4">
        <button
          type="button"
          onClick={onClear}
          className={`inline-flex h-10 items-center gap-2 rounded-lg border border-rule bg-surface px-4 text-label text-foreground shadow-sm transition-colors hover:bg-surface-container ${FOCUS}`}
        >
          <Icon name="cross" size={16} />
          <span>{t("writing.shelf.search.empty.clear")}</span>
        </button>
      </div>
    </section>
  );
}
