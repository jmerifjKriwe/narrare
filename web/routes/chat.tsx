import { createRoute, Link } from "@tanstack/react-router";
import { useState } from "react";

import { client, isModelChange } from "../lib/api/client";
import { t } from "../lib/i18n";
import { readFrames, type Source } from "../lib/stream";
import { rootRoute } from "./__root";

function ChatPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<Source[] | null>(null);
  const [asking, setAsking] = useState(false);
  const [failed, setFailed] = useState(false);
  const [modelChanged, setModelChanged] = useState(false);

  async function ask(event: React.FormEvent) {
    event.preventDefault();
    if (question.trim() === "") return;
    setAsking(true);
    setAnswer("");
    setSources(null);
    setFailed(false);
    setModelChanged(false);
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
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">{t("chat.heading")}</h1>
      <p className="mt-2 text-sm text-muted">
        <Link to="/" className="underline-offset-4 hover:underline">
          {t("nav.back")}
        </Link>
      </p>
      <form onSubmit={ask} className="mt-6 flex flex-col gap-2">
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
    </main>
  );
}

export const chatRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/chat",
  component: ChatPage,
});
