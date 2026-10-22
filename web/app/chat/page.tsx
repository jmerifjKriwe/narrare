"use client";

import Link from "next/link";
import { useState } from "react";

import { client, isModelChange } from "../../lib/api/client";
import { t } from "../../lib/i18n";
import { readFrames, type Source } from "../../lib/stream";

export default function ChatPage() {
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
    <main>
      <h1>{t("chat.heading")}</h1>
      <p>
        <Link href="/">{t("nav.back")}</Link>
      </p>
      <form onSubmit={ask}>
        <label>
          {t("chat.questionLabel")}
          <input value={question} onChange={(event) => setQuestion(event.target.value)} />
        </label>
        <button type="submit" disabled={asking}>
          {t("chat.ask")}
        </button>
      </form>
      <section aria-label={t("chat.answerLabel")}>
        <p>{answer}</p>
        {failed ? (
          <p role="alert">
            {modelChanged ? t("chat.modelChanged") : t("chat.error")}
          </p>
        ) : null}
      </section>
      {sources === null ? null : (
        <section aria-label={t("chat.sources")}>
          {sources.length === 0 ? (
            <p>{t("chat.noSources")}</p>
          ) : (
            <ul>
              {sources.map((source) => (
                <li key={source.chunk_id}>
                  <strong>{source.document_title}</strong>
                  <p>{source.text}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </main>
  );
}
