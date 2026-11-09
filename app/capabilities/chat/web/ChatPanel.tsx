import { useEffect, useRef, useState } from "react";

import { announce } from "@shell/lib/announce";
import { client, isModelChange, type Job } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { offerProposal } from "@shell/lib/proposal";
import { readFrames, type Source, type StreamFailure } from "@shell/lib/stream";
import { Button } from "@shell/ui/Button";
import { Field, Input } from "@shell/ui/field";
import { JobStatus } from "@shell/ui/JobStatus";
import { Notice } from "@shell/ui/Notice";
import { ProposalCard } from "@shell/ui/ProposalCard";
import { StreamError } from "@shell/ui/StreamError";

/** One turn of the conversation: the question as asked, the answer as it
 *  streamed, the sources it cited — or the refusal with its way back. A
 *  later ask never rewrites an earlier turn: the list only grows, so the
 *  reader keeps what they already read. */
type Turn = {
  id: number;
  question: string;
  answer: string;
  sources: Source[] | null;
  asking: boolean;
  // The failure the turn's ask died with, when it did: the payload the
  // error frame carried — its code picks the sentence. Empty for the
  // failures that carry no frame (a refusal above, a cut wire);
  // `modelChanged` overrides it with the embedding mismatch's own words.
  failure: StreamFailure | null;
  modelChanged: boolean;
  // The offer card is spent once its answer was offered or dropped; a new
  // question brings a fresh card with its fresh answer.
  offerSpent: boolean;
  /** The cited passage on screen: one chip open at a time. */
  openChunk: string | null;
};

/** The in-flight ask has no polled job behind it — the stream IS the work —
 *  so the progress it shows is a running job with nothing reported yet:
 *  the "Läuft…" line, no bar. The shape is a whole JobRead, not a cast. */
function askingJob(id: number): Job {
  return {
    id: `chat-ask-${id}`,
    kind: "chat-ask",
    status: "running",
    progress: null,
    error: null,
    result: null,
  };
}

/** The dock (and the page) as a conversation: every ask appends a turn —
 *  the question, the progress while it streams, the answer with its source
 *  chips — and a refused turn carries its retry. The same ask endpoint and
 *  the same streaming path as the form before it; only the reading changed. */
export function ChatPanel({ canOffer = false }: { canOffer?: boolean }) {
  const t = useTranslation();
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  // The turn counter lives beside the abort line: both outlive any one ask.
  const nextId = useRef(0);
  // The abort line of the in-flight ask. Closing the dock — or leaving the
  // page, same unmount — stops the answer at the fetch instead of streaming
  // it into a panel that is gone.
  const askAbort = useRef<AbortController | null>(null);
  useEffect(() => () => askAbort.current?.abort(), []);

  function patchTurn(id: number, patch: Partial<Turn>) {
    setTurns((current) =>
      current.map((turn) => (turn.id === id ? { ...turn, ...patch } : turn)),
    );
  }

  /** Replace the previous answer with a streamed reply; show failures unless unmount aborted it. */
  async function runAsk(id: number, asked: string) {
    // A second ask while one streams supersedes it: abort the in-flight
    // fetch so its late deltas can never write into this ask's fresh
    // answer — and a superseded ask never announces, its loop returning
    // before the completion line below.
    askAbort.current?.abort();
    const controller = new AbortController();
    askAbort.current = controller;
    // The new turn opens asking with a clean slate; a still-asking older
    // turn settles here — superseded, not failed: it keeps the partial
    // answer it streamed, silently.
    setTurns((current) =>
      current.map((turn) =>
        turn.id === id
          ? {
              ...turn,
              asking: true,
              answer: "",
              sources: null,
              failure: null,
              modelChanged: false,
              offerSpent: false,
              openChunk: null,
            }
          : turn.asking
            ? { ...turn, asking: false }
            : turn,
      ),
    );
    // Whether this ask actually wrote words: an empty-but-clean stream has
    // no answer to call ready, so it stays silent with its empty turn.
    let sawDelta = false;
    try {
      // parseAs "stream": the answer arrives as frames while it is written.
      const limit = 5; // the server's own default, pinned here by the request type
      const { error, response } = await client.POST("/api/chat/ask", {
        body: { question: asked, limit },
        parseAs: "stream",
        signal: controller.signal,
      });
      if (!response.ok) {
        // The mismatch refusal names its fix; every other failure stays generic.
        patchTurn(id, { modelChanged: isModelChange(error), failure: {} });
        return;
      }
      for await (const frame of readFrames(response)) {
        // The panel went away with this ask's answer still streaming: write
        // nothing more into it.
        if (controller.signal.aborted) return;
        if (frame.sources) patchTurn(id, { sources: frame.sources });
        if (frame.delta) {
          sawDelta = true;
          const delta = frame.delta;
          setTurns((current) =>
            current.map((turn) =>
              turn.id === id ? { ...turn, answer: turn.answer + delta } : turn,
            ),
          );
        }
        // An error frame replaces the done frame: the provider died, and a
        // silent end would look like a complete answer. The frame's payload
        // — code, model, detail — is what the notice speaks.
        if (frame.error) {
          patchTurn(id, { failure: frame.error });
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
      // failure belongs on the turn, exactly like a refusal does.
      if (!controller.signal.aborted) patchTurn(id, { failure: {} });
    } finally {
      // The cleanup owns only its own ask: a later ask that began while
      // this one settles has replaced the ref, and nulling it now would
      // take the unmount abort away from the ask still streaming — the
      // very zombie the ref exists to prevent.
      if (askAbort.current === controller) askAbort.current = null;
      if (!controller.signal.aborted) patchTurn(id, { asking: false });
    }
  }

  async function ask(event: React.FormEvent) {
    event.preventDefault();
    if (question.trim() === "") return;
    const id = nextId.current;
    nextId.current += 1;
    const asked = question;
    setTurns((current) => [
      ...current,
      {
        id,
        question: asked,
        answer: "",
        sources: null,
        asking: false,
        failure: null,
        modelChanged: false,
        offerSpent: false,
        openChunk: null,
      },
    ]);
    await runAsk(id, asked);
  }

  /** The refusal's way back: the same ask, on the same turn — the list
   *  grows only for new questions, never for another attempt. */
  function retryTurn(id: number, asked: string) {
    void runAsk(id, asked);
  }

  // The one turn still streaming, for the ask button's disabled state: the
  // button stays the panel's one primary while an answer is on its way.
  const asking = turns.some((turn) => turn.asking);

  return (
    <>
      {/* The ask on one row (§8.7's chat row, the one surface row that
          says so): the field grows, the button holds its label's width and
          sits on the input's line — down to the dock's 352 px and a 360 px
          viewport, where `min-w-0` lets the field shrink first. The fill
          follows the surface (L1, R46): on the standalone page the ask is
          its screen's one filled primary; in the workspace dock it defers
          to the editor's Weiterschreiben (`canOffer` is the dock's mark).
          The offer card's decisions beside the answer are a pair of
          equals, neither of them a fill. */}
      <form onSubmit={ask} className="flex items-end gap-2">
        <Field label={t("chat.questionLabel")} className="min-w-0 flex-1">
          <Input value={question} onChange={(event) => setQuestion(event.target.value)} />
        </Field>
        <Button
          type="submit"
          variant={canOffer ? "secondary" : "primary"}
          disabled={asking}
          className="shrink-0"
        >
          {t("chat.ask")}
        </Button>
      </form>
      {turns.length === 0 ? null : (
        <section aria-label={t("chat.answerLabel")} className="mt-6">
          {/* The conversation, oldest first: the question, the progress
              while its answer streams, the answer with its source chips.
              One list, never rewritten — a superseded turn keeps the half
              answer it managed, below it the new turn starts. */}
          <ol className="flex flex-col gap-6">
            {turns.map((turn) => (
              <li key={turn.id} data-turn={turn.id}>
                <p className="text-label font-semibold">{turn.question}</p>
                {turn.asking ? (
                  <div className="mt-2">
                    <JobStatus job={askingJob(turn.id)} />
                  </div>
                ) : null}
                {turn.answer === "" ? null : (
                  <p className="mt-2 whitespace-pre-wrap text-body leading-relaxed">
                    {turn.answer}
                  </p>
                )}
                {turn.failure ? (
                  <>
                    {turn.modelChanged ? (
                      <Notice tone="danger" live="alert" className="mt-2">
                        {t("chat.modelChanged")}
                      </Notice>
                    ) : (
                      <StreamError failure={turn.failure} className="mt-2" />
                    )}
                    <Button
                      variant="secondary"
                      size="sm"
                      className="mt-2"
                      onClick={() => retryTurn(turn.id, turn.question)}
                    >
                      {t("settings.retry")}
                    </Button>
                  </>
                ) : null}
                {turn.sources === null ? null : turn.sources.length === 0 ? (
                  <Notice tone="quiet" className="mt-2">
                    {t("chat.noSources")}
                  </Notice>
                ) : (
                  // The citations are chips, not rows: each chip wears the
                  // cited document's title — the citation target, never a
                  // bare URL — and opens its quoted passage underneath. One chip
                  // open at a time; the answer above already quotes the
                  // passage, so nothing hides behind a closed chip.
                  <ul className="mt-2 flex flex-wrap gap-2">
                    {turn.sources.map((source) => (
                      <li key={source.chunk_id}>
                        <Button
                          variant="secondary"
                          size="sm"
                          aria-expanded={turn.openChunk === source.chunk_id}
                          onClick={() =>
                            patchTurn(turn.id, {
                              openChunk:
                                turn.openChunk === source.chunk_id ? null : source.chunk_id,
                            })
                          }
                        >
                          {source.document_title}
                        </Button>
                        {turn.openChunk === source.chunk_id ? (
                          <p className="mt-1 whitespace-pre-wrap text-body leading-relaxed text-muted">
                            {source.text}
                          </p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
                {/* The dock's own follow-through: a complete answer can be handed
                    to the editor beside it — as a ghost there, never as text
                    without the writer's keypress. The standalone page has no
                    editor to offer into, so it never shows the card. */}
                {canOffer && !turn.asking && turn.failure === null && turn.answer !== "" && !turn.offerSpent ? (
                  <ProposalCard
                    titleKey="chat.offerAsVariant"
                    body={turn.answer}
                    onAccept={() => {
                      patchTurn(turn.id, { offerSpent: true });
                      offerProposal(turn.answer);
                    }}
                    onDiscard={() => patchTurn(turn.id, { offerSpent: true })}
                  />
                ) : null}
              </li>
            ))}
          </ol>
        </section>
      )}
    </>
  );
}
