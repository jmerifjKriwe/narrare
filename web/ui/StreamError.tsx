import type { HTMLAttributes } from "react";

import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { Notice } from "@shell/ui/Notice";

import type { StreamFailure } from "@shell/lib/stream";

/** The one place the settings open: the error sentences point here, in the
 * reader's language. The sentence carries the words as {link}; the component
 * splits the formatted message around them and makes that span the link. */
const PROVIDER_SETTINGS = "/settings/provider";

/** The code → sentence table: the closed wire vocabulary, each with its
 * catalog key. A code outside it — or none at all — reads as the generic. */
const SENTENCES: Record<string, MessageKey> = {
  "model-not-found": "errors.modelNotFound",
  "provider-auth": "errors.providerAuth",
  "key-unavailable": "errors.keyUnavailable",
  "prompt-refused": "errors.promptRefused",
};

/**
 * What a dead stream says: one sentence naming the cause and pointing at the
 * settings, from the error frame's payload. The code picks the sentence —
 * `errors.unknown` when it is missing or not one of the four the kernel
 * sends — and the provider's own message, when the frame carried one, hides
 * behind a details disclosure: technical detail, never the headline.
 */
export function StreamError({ failure, className, ...rest }: {
  failure: StreamFailure;
  className?: string;
} & HTMLAttributes<HTMLDivElement>) {
  const t = useTranslation();
  const link = t("errors.link");
  const message = t(sentenceKey(failure), { link, ...(modelOf(failure) ?? {}) });
  // The formatted sentence carries the link's words exactly once; slicing
  // around them (not replace — `$` in a replacement string would lie) keeps
  // the rest of the sentence verbatim. An empty translation would put the
  // whole sentence in the link's place — legal, just a whole-sentence link.
  const at = link === "" ? -1 : message.indexOf(link);
  const before = at < 0 ? message : message.slice(0, at);
  const after = at < 0 ? "" : message.slice(at + link.length);
  return (
    <Notice tone="danger" live="alert" className={className} {...rest}>
      <div className="min-w-0">
        <p>
          {before}
          <a
            href={PROVIDER_SETTINGS}
            className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
          >
            {link}
          </a>
          {after}
        </p>
        {failure.detail ? (
          // The provider's own message: openable, off by default, and never
          // mistaken for the sentence — the sentence is the one above.
          <details className="mt-1">
            <summary className="cursor-pointer text-label text-muted">
              {t("errors.details")}
            </summary>
            <p className="mt-1 break-words text-label text-muted">{failure.detail}</p>
          </details>
        ) : null}
      </div>
    </Notice>
  );
}

/** The sentence's key: the code's own, or the generic one for a frame that
 * names nothing the app can act on (and a model-less model-not-found, which
 * cannot name the row to fix). */
function sentenceKey(failure: StreamFailure): MessageKey {
  if (failure.code === "model-not-found" && failure.model === undefined) {
    return "errors.unknown";
  }
  if (failure.code === "prompt-refused" && failure.reason === "budget") {
    return "errors.promptRefusedBudget";
  }
  return SENTENCES[failure.code ?? ""] ?? "errors.unknown";
}

/** The model the sentence names, present only where it has one to name. */
function modelOf(failure: StreamFailure): { model: string } | undefined {
  return failure.code === "model-not-found" && failure.model !== undefined
    ? { model: failure.model }
    : undefined;
}
