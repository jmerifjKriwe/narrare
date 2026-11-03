import { useEffect, useRef, useState } from "react";

import { announce } from "@shell/lib/announce";
import { client, isModelChange } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { offerProposal } from "@shell/lib/proposal";
import { readFrames, type Source } from "@shell/lib/stream";
import { Button } from "@shell/ui/Button";
import { Field, Input } from "@shell/ui/field";
import { Notice } from "@shell/ui/Notice";
import { Row } from "@shell/ui/Row";
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
  // The abort line of the in-flight ask. Closing the dock — or leaving the
  // page, same unmount — stops the answer at the fetch instead of streaming
  // it into a panel that is gone.
  const askAbort = useRef<AbortController | null>(null);
  useEffect(() => () => askAbort.current?.abort(), []);

  /** Replace the previous answer with a streamed reply; show failures unless unmount aborted it. */
  async function ask(event: React.FormEvent) {
    event.preventDefault();
    if (question.trim() === "") return;
    // A second ask while one streams supersedes it: abort the in-flight
    // fetch so its late deltas can never write into this ask's fresh
    // answer — and a superseded ask never announces, its loop returning
    // before the completion line below.
    askAbort.current?.abort();
    const controller = new AbortController();
    askAbort.current = controller;
    setAsking(true);
    setAnswer("");
    setSources(null);
    setFailed(false);
    setModelChanged(false);
    setOfferSpent(false);
    // Whether this ask actually wrote words: an empty-but-clean stream has
    // no answer to call ready, so it stays silent with its empty region.
    let sawDelta = false;
    try {
      // parseAs "stream": the answer arrives as frames while it is written.
      const limit = 5; // the server's own default, pinned here by the request type
      const { error, response } = await client.POST("/api/chat/ask", {
        body: { question, limit },
        parseAs: "stream",
        signal: controller.signal,
      });
      if (!response.ok) {
        // The mismatch refusal names its fix; every other failure stays generic.
        setModelChanged(isModelChange(error));
        setFailed(true);
        return;
      }
      for await (const frame of readFrames(response)) {
        // The panel went away with this ask's answer still streaming: write
        // nothing more into it.
        if (controller.signal.aborted) return;
        if (frame.sources) setSources(frame.sources);
        if (frame.delta) {
          sawDelta = true;
          setAnswer((current) => current + frame.delta);
        }
        // An error frame replaces the done frame: the provider died, and a
        // silent end would look like a complete answer.
        if (frame.error) {
          setFailed(true);
          return;
        }
      }
      // F16: the stream ended clean and wrote an answer — that fact is
      // spoken once, here. The deltas streamed silently; the reader hears
      // one sentence, not a murmur per token. The failure paths above and
      // below return without announcing: their alerts speak instead. The
      // `t` here is the live module function (useTranslation returns it
      // unchanged), so the string resolves in the locale active at announce
      // time — a language switched mid-stream announces in the new one.
      if (sawDelta) announce(t("chat.answerReady"));
    } catch {
      // The abort of a departed panel is the user's doing, not a failure —
      // the fetch rejects with it, and there is no panel left to tell.
      // Everything else is the wire dying mid-answer: a rethrow would leave
      // a half answer looking finished beside an unhandled rejection. The
      // failure belongs on the panel, exactly like a refusal does.
      if (!controller.signal.aborted) setFailed(true);
    } finally {
      // The cleanup owns only its own ask: a later ask that began while
      // this one settles has replaced the ref, and nulling it now would
      // take the unmount abort away from the ask still streaming — the
      // very zombie the ref exists to prevent.
      if (askAbort.current === controller) askAbort.current = null;
      if (!controller.signal.aborted) setAsking(false);
    }
  }

  return (
    <>
      {/* The ask on one row (§8.7's chat row, the one surface row that
          says so): the field grows, the button holds its label's width and
          sits on the input's line — down to the dock's 384 px and a 360 px
          viewport, where `min-w-0` lets the field shrink first. This is
          the screen's one filled primary (L1); the offer card's decisions
          beside the answer are a pair of equals, neither of them a fill. */}
      <form onSubmit={ask} className="flex items-end gap-2">
        <Field label={t("chat.questionLabel")} className="min-w-0 flex-1">
          <Input value={question} onChange={(event) => setQuestion(event.target.value)} />
        </Field>
        <Button type="submit" variant="primary" disabled={asking} className="shrink-0">
          {t("chat.ask")}
        </Button>
      </form>
      <section aria-label={t("chat.answerLabel")} className="mt-6">
        <p className="whitespace-pre-wrap text-body leading-relaxed">{answer}</p>
        {failed ? (
          <Notice tone="danger" live="alert" className="mt-2">
            {modelChanged ? t("chat.modelChanged") : t("chat.error")}
          </Notice>
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
        <section aria-label={t("chat.sources")} className="mt-6">
          {sources.length === 0 ? (
            <Notice tone="quiet">{t("chat.noSources")}</Notice>
          ) : (
            // The sources are a real list (assistive tech announces the
            // count); each entry is a row on the rule — the document's
            // title, the quoted passage under it. The last row drops its
            // rule: the list ends, it does not dangle a separator. (The
            // `last:` variant wins over `rowClass`'s `border-b` by
            // specificity; a same-weight extension like a bare `gap-1`
            // would lose the compiled order — see the report.)
            <ul className="flex flex-col">
              {sources.map((source) => (
                <li key={source.chunk_id}>
                  <Row
                    as="div"
                    className="h-auto flex-col items-stretch py-2 last:border-b-0"
                  >
                    <span className="text-label font-semibold">{source.document_title}</span>
                    <span className="text-body leading-relaxed text-muted">{source.text}</span>
                  </Row>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </>
  );
}
