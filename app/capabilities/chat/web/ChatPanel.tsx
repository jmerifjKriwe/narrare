import { useState } from "react";

import { client, isModelChange } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { offerProposal } from "@shell/lib/proposal";
import { readFrames, type Source } from "@shell/lib/stream";
import { ProposalCard } from "@shell/ui/ProposalCard";

/** One question, one streamed answer, the sources it cites — the flow both
 * surfaces share: the standalone page and the workspace dock. */
export function ChatPanel({ canOffer = false }: { canOffer?: boolean }) {
  const t = useTranslation();
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<Source[] | null>(null);
  const [asking, setAsking] = useState(false);
  const [failed, setFailed] = useState(false);
  const [modelChanged, setModelChanged] = useState(false);
  // The offer card is spent once its answer was offered or dropped; a new
  // question brings a fresh card with its fresh answer.
  const [offerSpent, setOfferSpent] = useState(false);

  async function ask(event: React.FormEvent) {
    event.preventDefault();
    if (question.trim() === "") return;
    setAsking(true);
    setAnswer("");
    setSources(null);
    setFailed(false);
    setModelChanged(false);
    setOfferSpent(false);
    try {
      // parseAs "stream": the answer arrives as frames while it is written.
      const limit = 5; // the server's own default, pinned here by the request type
      const { error, response } = await client.POST("/api/chat/ask", {
        body: { question, limit },
        parseAs: "stream",
      });
      if (!response.ok) {
        // The mismatch refusal names its fix; every other failure stays generic.
        setModelChanged(isModelChange(error));
        setFailed(true);
        return;
      }
      for await (const frame of readFrames(response)) {
        if (frame.sources) setSources(frame.sources);
        if (frame.delta) setAnswer((current) => current + frame.delta);
        // An error frame replaces the done frame: the provider died, and a
        // silent end would look like a complete answer.
        if (frame.error) {
          setFailed(true);
          return;
        }
      }
    } finally {
      setAsking(false);
    }
  }

  return (
    <>
      <form onSubmit={ask} className="flex flex-col gap-2">
        <label className="flex flex-col gap-1 text-sm font-medium">
          {t("chat.questionLabel")}
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            className="rounded-md border border-border bg-card px-3 py-2 text-base font-normal focus:border-primary focus:outline-none"
          />
        </label>
        <button
          type="submit"
          disabled={asking}
          className="self-start rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {t("chat.ask")}
        </button>
      </form>
      <section aria-label={t("chat.answerLabel")} className="mt-8">
        <p className="whitespace-pre-wrap leading-relaxed">{answer}</p>
        {failed ? (
          <p role="alert" className="mt-2 text-sm text-danger">
            {modelChanged ? t("chat.modelChanged") : t("chat.error")}
          </p>
        ) : null}
        {/* The dock's own follow-through: a complete answer can be handed
            to the editor beside it — as a ghost there, never as text
            without the writer's keypress. The standalone page has no
            editor to offer into, so it never shows the card. */}
        {canOffer && !asking && !failed && answer !== "" && !offerSpent ? (
          <ProposalCard
            titleKey="chat.offerAsVariant"
            body={answer}
            onAccept={() => {
              setOfferSpent(true);
              offerProposal(answer);
            }}
            onDiscard={() => setOfferSpent(true)}
          />
        ) : null}
      </section>
      {sources === null ? null : (
        <section aria-label={t("chat.sources")} className="mt-8">
          {sources.length === 0 ? (
            <p className="text-sm text-muted">{t("chat.noSources")}</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {sources.map((source) => (
                <li key={source.chunk_id} className="rounded-lg border border-border bg-card p-4">
                  <strong className="text-sm font-semibold">{source.document_title}</strong>
                  <p className="mt-1 text-sm leading-relaxed text-muted">{source.text}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </>
  );
}
