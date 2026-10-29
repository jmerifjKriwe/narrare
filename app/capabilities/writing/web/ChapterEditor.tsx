import { useEffect, useMemo, useRef, useState } from "react";

import { announce } from "@shell/lib/announce";
import { client } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { SaveIndicator, type SaveStatus } from "@shell/lib/save";
import { readFrames } from "@shell/lib/stream";
import { MarkdownEditor } from "@shell/ui/markdown-editor";
import type { Editor } from "@tiptap/core";

import { ghostText, showGhost, type GhostHandlers } from "./ghostText";

/**
 * Edit a chapter, with proposals kept as ghost text until accepted. Saving is
 * the page's, not the editor's: it receives the autosave's `status` (shown
 * beside the text) and `schedule` (fed on every update with the document as
 * Markdown — the storage format). `body` initializes the editor; remount
 * with a new key when switching chapters.
 */
export function ChapterEditor({
  chapterId,
  body,
  status,
  schedule,
  proposal,
  onProposalResolve,
}: {
  chapterId: string;
  body: string;
  status: SaveStatus;
  schedule: (body: string) => void;
  /** A proposal from outside (the proposal bus, later): rendered as a ghost
   *  at the caret. `undefined` leaves the floor to this component's own
   *  continuation stream; `null` is an explicit "no proposal". */
  proposal?: string | null;
  /** Called once per resolved ghost — the bus clears its offer either way. */
  onProposalResolve?: (accepted: boolean) => void;
}) {
  const t = useTranslation();
  const [continuing, setContinuing] = useState(false);
  const [failed, setFailed] = useState(false);
  // What this component's own stream has proposed so far.
  const [streamed, setStreamed] = useState<string | null>(null);
  // The editor instance, handed back by the shared MarkdownEditor once
  // mounted — the ghost machinery drives the view, so it needs the editor,
  // not only the component.
  const [editor, setEditor] = useState<Editor | null>(null);

  const resolve = useRef(onProposalResolve);
  resolve.current = onProposalResolve;
  // The abort line of the in-flight continuation. Leaving the page or
  // switching chapters unmounts the editor: the stream stops at the fetch
  // instead of running unread into a component that is gone — the chat
  // panel's own pattern.
  const continueAbort = useRef<AbortController | null>(null);
  useEffect(() => () => continueAbort.current?.abort(), []);
  // The proposal prop as it stands right now: a stream that fails must
  // judge by the screen the user is looking at, not by the render its
  // click happened in — an offer may have arrived or cleared mid-stream.
  const offered = useRef(proposal);
  offered.current = proposal;
  // The stream run a ghost belongs to: bumping it abandons the loop, so a
  // resolved ghost cannot be resurrected by the deltas still in flight.
  const run = useRef(0);

  // The ghost's handlers run inside ProseMirror, built once with the editor;
  // the ref keeps their closures current across renders.
  const handlers = useRef<GhostHandlers>({ onAccept: () => {}, onDiscard: () => {} });
  handlers.current = {
    onAccept() {
      announce(t("editor.ghostAccepted"));
      setStreamed(null);
      run.current += 1;
      resolve.current?.(true);
    },
    onDiscard() {
      announce(t("editor.ghostDiscarded"));
      setStreamed(null);
      run.current += 1;
      resolve.current?.(false);
    },
  };

  // Ghost text rides the shared editor as an extra extension; nothing about
  // the ghost contract changes with the storage format.
  const extensions = useMemo(() => [ghostText(handlers)], []);

  // The two proposal sources: the prop (the bus drives the same contract) and
  // this component's own stream. The prop wins when it has an opinion.
  const ghost = proposal !== undefined ? proposal : streamed;
  const previous = useRef<string | null>(null);
  // Who owns the ghost on screen: the offer (its text is its identity — the
  // bus is last-wins) or the stream run that grows it. A new text under the
  // same owner is a delta, the stream extending its own words; a change of
  // owner while a ghost is pending is a supersede.
  const owner = useRef<string | number | null>(null);

  useEffect(() => {
    if (!editor) return;
    const text = ghost === "" ? null : ghost;
    const mine = proposal !== undefined ? `offer:${proposal}` : run.current;
    const wasPending = previous.current !== null;
    const arriving = !wasPending && text !== null;
    const superseding = wasPending && text !== null && owner.current !== mine;
    previous.current = text;
    owner.current = text === null ? null : mine;
    if (arriving) {
      // One announcement per ghost, not one per delta.
      announce(t("editor.ghostArrived"));
      // Tab and Esc are the editor's keys; whoever holds focus now (the
      // Weiterschreiben button, the panel that offered) gives the caret back.
      // Synchronously, and through the view: `commands.focus()` waits for the
      // next animation frame, while the click that started the stream already
      // lost the caret to <body> (React disables the focused button). A ghost
      // painted in that gap is a ghost no key can reach — Esc lands on <body>,
      // and the workbench's own Esc handler sees nothing to stop. view.focus()
      // focuses and restores the caret from the state in the same task that
      // paints the ghost, so "ghost on screen" and "the editor owns the
      // keyboard" are never two different moments. The frame the command also
      // used to scroll the caret into view is not owed here: an arrival does
      // not move the caret.
      editor.view.focus();
    } else if (superseding) {
      // One announcement per supersede: a new offer or a fresh run replaced
      // the pending ghost — the deltas that grow a ghost say nothing.
      announce(t("editor.ghostReplaced"));
    }
    showGhost(editor, text);
  }, [editor, ghost, t]);

  /** Stream a continuation into the ghost; report request and stream failures in the editor. */
  async function continueWriting() {
    if (!editor) return;
    const mine = ++run.current;
    const controller = new AbortController();
    continueAbort.current = controller;
    setContinuing(true);
    setFailed(false);
    try {
      // parseAs "stream": the frames are read from the body while they arrive,
      // so the client must not buffer the response first.
      const { response } = await client.POST(
        "/api/writing/chapters/{chapter_id}/continue",
        {
          params: { path: { chapter_id: chapterId } },
          parseAs: "stream",
          signal: controller.signal,
        },
      );
      if (!response.ok) {
        setFailed(true);
        // The refusal is the stream's own story only while no offer from
        // outside owns the ghost on screen — that offer did not fail, and
        // the alert above already names the refused request either way.
        if (offered.current === undefined) announce(t("editor.ghostFailed"));
        return;
      }
      let draft = "";
      for await (const frame of readFrames(response)) {
        // The editor went away with this continuation still streaming: write
        // nothing more into it. A ghost taken or dropped mid-stream stops
        // the feed the same way.
        if (mine !== run.current || controller.signal.aborted) return;
        // An error frame replaces the done frame: the provider died, and a
        // silent end would look like a finished continuation. The failure
        // is announced as what it is — the user did not discard anything.
        if (frame.error) {
          setFailed(true);
          setStreamed(null);
          // The ghost this failure may speak of is the stream's own only
          // while no offer owns the screen: the offer still showing is
          // not the ghost that just died, and hearing "failed" about it
          // would be a lie about the one ghost the user can see.
          if (offered.current === undefined) announce(t("editor.ghostFailed"));
          return;
        }
        if (!frame.delta) continue;
        // The stream grows the ghost, never the document: the text is the
        // user's only when they take it.
        draft += frame.delta;
        setStreamed(draft);
      }
    } catch {
      // A rejected request — the API down, the wire cut — is a failure the
      // editor must name, exactly like a refusal; the abort of a departed
      // editor is the user's doing, and there is no editor left to tell.
      if (!controller.signal.aborted) {
        setFailed(true);
        if (offered.current === undefined) announce(t("editor.ghostFailed"));
      }
    } finally {
      // The cleanup owns only its own continuation: a later run that began
      // while this one settles has replaced the ref, and nulling it now
      // would take the unmount abort away from the stream still in flight.
      if (continueAbort.current === controller) continueAbort.current = null;
      setContinuing(false);
    }
  }

  return (
    <div className="mt-8">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={continueWriting}
          disabled={continuing}
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {t("chapters.continue")}
        </button>
        <SaveIndicator status={status} />
      </div>
      {failed ? (
        <p role="alert" className="mt-2 text-sm text-danger">
          {t("chapters.continueError")}
        </p>
      ) : null}
      <MarkdownEditor
        className="mt-6"
        label={t("chapters.editorLabel")}
        value={body}
        onChange={schedule}
        extensions={extensions}
        onReady={setEditor}
      />
    </div>
  );
}
