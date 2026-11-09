import type { components } from "@shell/lib/api/schema";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { activeLocale } from "@shell/lib/locale";

type Model = components["schemas"]["ModelRead"];

/**
 * One provider's live model list, as the providers section's "Load models"
 * answered this session: the ids, and the moment they were fetched — the
 * timestamp the row's "not in the current offer" mark names. Session state
 * only: nothing here is stored, and before the user has pressed the button
 * no list exists for anyone to mark against.
 */
export type LiveList = { ids: string[]; fetchedAt: Date };

/** Every provider's live list so far, or `"failed"` where the endpoint could not be asked. */
export type LiveLists = Record<string, LiveList | "failed">;

/** The live list of one provider, when one was fetched and it answered. */
export function liveListOf(
  discovered: LiveLists,
  providerId: string | undefined,
): LiveList | undefined {
  if (providerId === undefined) return undefined;
  const entry = discovered[providerId];
  return typeof entry === "object" ? entry : undefined;
}

/**
 * The failed call's code, named in the reader's language. A settings-side
 * names map, deliberately not the `errors.*` sentences: those are full
 * sentences that point at the settings with `{link}` — the right words for a
 * dead stream's headline, the wrong shape inside a row mark. The codes are
 * the kernel's closed wire vocabulary; a code outside it (or none — a stream
 * the consumer walked away from carries no code) reads as the generic name.
 */
const ERROR_CODE_NAMES: Record<string, MessageKey> = {
  "model-not-found": "settings.profiles.errorCode.model-not-found",
  "provider-auth": "settings.profiles.errorCode.provider-auth",
};

/** A moment in the reader's own date and time — the platform's words, so no
 * catalog carries the format and every language the app can switch to is
 * covered without a new key. */
function stamp(moment: Date): string {
  return new Intl.DateTimeFormat(activeLocale(), {
    dateStyle: "short",
    timeStyle: "short",
  }).format(moment);
}

/**
 * A model row's state marks, composed from facts the page already holds:
 * *Price unknown* when the catalog has no entry for the model (the read's
 * `in_catalog`, the resolution lookup's own answer), *Not in the current
 * offer (list from …)* when a live list was fetched this session and the
 * model is absent from it, and *Last call failed: ⟨code⟩ (date)* from the
 * row's newest audit row. No marks, no line — a clean model says nothing.
 */
export function ModelMarks({ model, live }: { model: Model; live: LiveList | undefined }) {
  const t = useTranslation();
  const marks: string[] = [];
  if (!model.in_catalog) {
    marks.push(t("settings.profiles.markNoPrice"));
  }
  if (live !== undefined && !live.ids.includes(model.model)) {
    marks.push(t("settings.profiles.markNotOffered", { date: stamp(live.fetchedAt) }));
  }
  if (model.last_error_at !== null) {
    const named =
      model.last_error_code === null ? undefined : ERROR_CODE_NAMES[model.last_error_code];
    marks.push(
      t("settings.profiles.markLastFailed", {
        code: named === undefined ? t("settings.profiles.errorCode.unknown") : t(named),
        date: stamp(new Date(model.last_error_at)),
      }),
    );
  }
  if (marks.length === 0) return null;
  return (
    <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-label text-muted">
      {marks.map((mark) => (
        <li key={mark}>{mark}</li>
      ))}
    </ul>
  );
}
