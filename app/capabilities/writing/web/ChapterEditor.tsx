import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useMemo, useRef, useState } from "react";

import { announce } from "@shell/lib/announce";
import { client } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { SaveIndicator, useAutosave } from "@shell/lib/save";
import { readFrames } from "@shell/lib/stream";

import { ghostText, showGhost, type GhostHandlers } from "./ghostText";

export function ChapterEditor({
  chapterId,
  body,
  onSaved,
  proposal,
  onProposalResolve,
}: {
  chapterId: string;
  body: string;
  onSaved?: (chapterId: string, body: string) => void;
  /** A proposal from outside (the proposal bus, later): rendered as a ghost
   *  at the caret. `undefined` leaves the floor to this component's own
   *  continuation stream; `null` is an explicit "no proposal". */
  proposal?: string | null;
  /** Called once per resolved ghost — the bus clears its offer either way. */
  onProposalResolve?: (accepted: boolean) => void;
}) {
  const t = useTranslation();
  const { status, schedule } = useAutosave(chapterId, onSaved);
  const [continuing, setContinuing] = useState(false);
  const [failed, setFailed] = useState(false);
  // What this component's own stream has proposed so far.
  const [streamed, setStreamed] = useState<string | null>(null);

  const resolve = useRef(onProposalResolve);
  resolve.current = onProposalResolve;
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

  const extensions = useMemo(() => [StarterKit, ghostText(handlers)], []);
  const editor = useEditor({
    extensions,
    content: body,
    immediatelyRender: false,
    onUpdate: ({ editor: instance }) => schedule(instance.getHTML()),
    editorProps: {
      attributes: {
        class: "prose",
        // @tiptap/core injects role="textbox" in createView, but the React
        // binding strips it again: EditorContent.init() re-parents the view
        // and setOptions({element}) re-props it from the raw editorProps.
        // The explicit role keeps aria-label valid here — axe computes
        // "generic" for the roleless div and flags aria-prohibited-attr
        // deterministically while the editor is empty (it defers the rule
        // once text exists).
        role: "textbox",
        "aria-multiline": "true",
        "aria-label": t("chapters.editorLabel"),
      },
    },
  });

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
      editor.commands.focus();
    } else if (superseding) {
      // One announcement per supersede: a new offer or a fresh run replaced
      // the pending ghost — the deltas that grow a ghost say nothing.
      announce(t("editor.ghostReplaced"));
    }
    showGhost(editor, text);
  }, [editor, ghost, t]);

  async function continueWriting() {
    if (!editor) return;
    const mine = ++run.current;
    setContinuing(true);
    setFailed(false);
    try {
      // parseAs "stream": the frames are read from the body while they arrive,
      // so the client must not buffer the response first.
      const { response } = await client.POST(
        "/api/writing/chapters/{chapter_id}/continue",
        { params: { path: { chapter_id: chapterId } }, parseAs: "stream" },
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
        // The ghost was taken or dropped mid-stream: stop feeding it.
        if (mine !== run.current) return;
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
    } finally {
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
      <EditorContent editor={editor} className="mt-6" />
    </div>
  );
}
