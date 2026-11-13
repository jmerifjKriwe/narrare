import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import { announce } from "@shell/lib/announce";
import { client } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { activeLocale } from "@shell/lib/locale";
import { SaveIndicator, type DocumentDraft, type SaveStatus } from "@shell/lib/save";
import { readFrames, type StreamFailure } from "@shell/lib/stream";
import { countWords } from "@shell/lib/words";
import { Button } from "@shell/ui/Button";
import { MarkdownEditor } from "@shell/ui/markdown-editor";
import { StreamError } from "@shell/ui/StreamError";
import type { Editor } from "@tiptap/core";

import { chapterOrdinal } from "./numberWords";
import { ghostText, showGhost, type GhostHandlers } from "./ghostText";
import { slashPalette } from "./slashPalette";

/**
 * Edit a chapter, with proposals kept as ghost text until accepted. Saving is
 * the page's, not the editor's: it receives the autosave's `status` (shown in
 * the runhead) and `schedule` (fed on every update with the document as
 * Markdown — the storage format — and the field that changed). The runhead's
 * chapter line is the title input: the chapter's name is written where it is
 * read, and `onTitleChange` hands each keystroke to the page, which holds
 * the draft. `body` initializes the editor; remount with a new key when
 * switching chapters.
 *
 * The frame (F4) is the runhead above the text — book · the title input on
 * the left, the chapter's code, then the save state on the right — the
 * chapter headline inside the card (the position written out as the eyebrow,
 * the name in the prose heading's face, the 1 px rule), and the paper's own
 * chrome around the prose: the running head at the card's top (the book and,
 * where the row carries one, its author, in the serif's italic muted voice)
 * and the foot below the prose — the word count and position as before, and
 * the settled autosave line (the success dot and the state in the paper's
 * words, from the same one `status` the runhead's indicator reads). All of
 * it names the writing, so all of it yields at focus depth 2, where only
 * the writing surface remains. The book's name and the author's name arrive
 * as props; without them the frame still carries the title input and the
 * save state, and the footer counts what it has.
 */
export function ChapterEditor({
  chapterId,
  body,
  title,
  onTitleChange,
  status,
  schedule,
  proposal,
  onProposalResolve,
  bookTitle,
  bookAuthor,
  chapterNumber,
  chapterTotal,
  focusDepth = 0,
  actions,
  promptBar,
}: {
  chapterId: string;
  body: string;
  /** The chapter's own name, as the page's draft holds it — editable here. */
  title: string;
  /** Each keystroke on the title, handed to the page's draft. */
  onTitleChange: (value: string) => void;
  status: SaveStatus;
  schedule: (draft: DocumentDraft, changed: keyof DocumentDraft) => void;
  /** A proposal from outside (the proposal bus, later): rendered as a ghost
   *  at the caret. `undefined` leaves the floor to this component's own
   *  continuation stream; `null` is an explicit "no proposal". */
  proposal?: string | null;
  /** Called once per resolved ghost — the bus clears its offer either way. */
  onProposalResolve?: (accepted: boolean) => void;
  /** The frame's left name: the book's title, muted before the chapter's. */
  bookTitle?: string;
  /** The paper running head's second name: the book's author, as the
   *  novel's row holds it. `undefined` (or empty) leaves the head naming
   *  the book alone — no dangling dash. */
  bookAuthor?: string;
  /** The chapter's one-based position, for the footer's "n von m" and the
   *  title input's placeholder when the chapter is unnamed. */
  chapterNumber?: number;
  /** The book's chapter count; absent or zero leaves the position unsaid. */
  chapterTotal?: number;
  /** The workbench's focus depth: at 2 the frame yields to the text. */
  focusDepth?: 0 | 1 | 2;
  /** The chapter's actions, rendered in the runhead's right side beside
   *  the save state — the menu the page builds (rename, move, delete),
   *  passed as a node because the actions are the page's story, not the
   *  editor's. Yields with the frame at depth 2. */
  actions?: ReactNode;
  /** The floating prompt bar, mounted by the column below the card. A
   *  render prop, because both of the bar's inputs live here: the trigger
   *  is this component's own continuation stream, and `disabled` is that
   *  stream's in-flight state. Chrome, like the frame — it yields at
   *  focus depth 2. `undefined` mounts nothing (the editor's own tests
   *  stay bar-free unless they ask). */
  promptBar?: (controls: { onContinue: () => void; disabled: boolean }) => ReactNode;
}) {
  const t = useTranslation();
  // The eyebrow's number words follow the catalog's language; the
  // subscription is useTranslation's (a locale change re-renders, and this
  // read happens in that render), so no second store subscription here.
  const locale = activeLocale();
  // The headline's title line: the same name the runhead's input holds, read
  // only. An unnamed chapter wears the placeholder's default name — a
  // rendering, never a stored value, exactly like the input's placeholder —
  // and without a chapter position and a name there is no headline at all.
  const headlineTitle =
    title !== ""
      ? title
      : chapterNumber !== undefined
        ? t("chapters.defaultTitle", { n: chapterNumber })
        : null;
  const [continuing, setContinuing] = useState(false);
  // The failure the stream or its request died with, when one did: the
  // payload the error frame carried — its code picks the sentence. Empty for
  // the request-level failures (a refusal, a cut wire): they carry no frame.
  const [failure, setFailure] = useState<StreamFailure | null>(null);
  // What this component's own stream has proposed so far.
  const [streamed, setStreamed] = useState<string | null>(null);
  // The frame's live count: the shared rule applied to the document as it
  // stands — the same Markdown string the autosave will carry — so the
  // footer moves with the writing, not with the last save.
  const [words, setWords] = useState(() => countWords(body));
  const scheduleAndCount = useCallback(
    (markdown: string) => {
      setWords(countWords(markdown));
      schedule({ title, body: markdown }, "body");
    },
    [schedule, title],
  );
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
  // the ghost contract changes with the storage format. The slash door rides
  // beside it: `/` in an empty paragraph opens the palette, anywhere else it
  // stays a literal slash.
  const extensions = useMemo(() => [ghostText(handlers), slashPalette()], []);

  // The two proposal sources: the prop (the bus drives the same contract) and
  // this component's own stream. The prop wins when it has an opinion.
  const ghost = proposal !== undefined ? proposal : streamed;
  const previous = useRef<string | null>(null);
  // Who owns the ghost on screen: the offer (its text is its identity — the
  // bus is last-wins) or the stream run that grows it. A new text under the
  // same owner is a delta, the stream extending its own words; a change of
  // owner while a ghost is pending is a supersede.
  const owner = useRef<string | number | null>(null);

  // biome-ignore lint/correctness/useExhaustiveDependencies: `proposal` reaches this effect through `ghost`, a dependency; the owner identity must be the proposal that painted that same text, not a possibly newer render's.
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
    setFailure(null);
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
        setFailure({});
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
        // silent end would look like a finished continuation. The frame's
        // payload — code, model, detail — is what the notice speaks; the
        // failure is announced as what it is, the user did not discard.
        if (frame.error) {
          setFailure(frame.error);
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
        setFailure({});
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
    <div>
      {focusDepth < 2 ? (
        <header className="flex items-center justify-between gap-3">
          {/* A paragraph, not a heading: its accessible name carries the
              book's title too, and a second heading that contains it turns
              every "heading <book>" query into a coin toss — the runhead is
              the page's label, not a node of its outline. The chapter's own
              name is written here, in the input that wears the emph step's
              600 face at the drafted 15 px (the drafted ribbon's title
              voice): empty is legal (the placeholder names the position,
              and the placeholder is a rendering, never a stored value), the
              server's 200-character ceiling held client-side. The input
              takes the line's free width, so the cluster reads as the draft
              draws its ribbon: book · title · code — then the hairline, the
              save state, the menu.
              The runhead stands above the card on purpose: its input and
              its menu are controls, and the card's focus ring means "the
              text has the caret" — a control inside it would blur that. */}
          <p className="flex min-w-0 flex-1 items-center text-emph">
            {bookTitle !== undefined ? (
              <span className="font-normal text-muted">{bookTitle} · </span>
            ) : null}
            <input
              type="text"
              aria-label={t("chapters.titleLabel")}
              maxLength={200}
              value={title}
              onChange={(event) => onTitleChange(event.target.value)}
              placeholder={
                chapterNumber !== undefined
                  ? t("chapters.defaultTitle", { n: chapterNumber })
                  : undefined
              }
              className="min-w-0 flex-1 basis-32 border-0 bg-transparent p-0 font-semibold text-inherit caret-current placeholder:font-normal placeholder:text-muted focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
            />
            {chapterNumber !== undefined ? (
              // The drafted chapter code ("KAP-01"): the catalog supplies
              // the prefix (de KAP, en/fr CH) and the position is
              // zero-padded — never a hard-coded string. Mono face,
              // tabular figures; chrome of the runhead line, outside the
              // paper the code names.
              <span className="ml-2 shrink-0 rounded-[var(--radius)] bg-secondary-container px-1.5 py-0.5 font-mono text-eyebrow tabular-nums text-secondary-container-foreground">
                {t("chapters.chapterCode", { n: String(chapterNumber).padStart(2, "0") })}
              </span>
            ) : null}
          </p>
          {/* The drafted line's 1 px hairline between the writer's words
              (book · title · code) and the document's state: the vertical
              rule the draft draws inside its ribbon. */}
          <span aria-hidden="true" className="h-3.5 w-px shrink-0 bg-rule" data-runhead-rule />
          {/* The runhead's right side: the save state and the chapter's
              actions, one group — the frame's own words (book · title on
              the left, the document's state and its deeds on the right). */}
          <div className="flex shrink-0 items-center gap-2">
            <SaveIndicator status={status} />
            {actions}
          </div>
        </header>
      ) : null}
      {/* The action stands above the sheet, never inside it: the card's
          focus ring must not enclose a control — the button is its own
          focus target, and the ring means "the text has the caret". */}
      <div className="mt-4 mb-4 flex items-center gap-3">
        {/* The workspace's one filled primary (R46): through the primitive,
            so the fill, the ring and the disabled state ride buttonClass.
            The hook is this button's own address: the prompt bar repeats
            the same words below the card, so a name locator matches two —
            the suites click this one by `data-continue-button`, not by
            position. */}
        <Button variant="primary" data-continue-button onClick={continueWriting} disabled={continuing}>
          {t("chapters.continue")}
        </Button>
      </div>
      {failure ? <StreamError failure={failure} className="mb-4" /> : null}
      {/* The writing surface is a card (F18): the focus ring sits on its
          edge, 16 px from the glyphs, instead of flush on them. The 1 px
          edge plus the 15 px pad is that 16 px; a 16 px pad would eat 2 px
          of the measure, which is fixed at 544. The card never grows past
          576: a wider card would leave the 544 px measure flush left. Below
          576 the column is narrower than the card, so the card cancels the
          page's 16 px gutter and bleeds to the viewport (the 360 px visit
          keeps the prose floor); the ring is inset there because an outside
          ring would fall off the screen. */}
      <div
        data-editor-card
        className="rounded-[var(--radius-lg)] border border-rule bg-card p-[15px] focus-within:ring-2 focus-within:ring-focus max-[36rem]:-mx-4 max-[36rem]:rounded-none max-[36rem]:border-x-0 max-[36rem]:focus-within:ring-inset"
      >
        {/* The paper's running head (the draft's page header): the book and,
            where the row carries one, its author — `book — author` — in the
            serif's italic muted voice. A rendering, like the headline: the
            names are the row's, nothing stored here. Without an author the
            head names the book alone, without a dangling dash. The drafted
            folio stays off until the app has pages to count:
            interim: no pagination — #820 */}
        {focusDepth < 2 && bookTitle !== undefined ? (
          <p data-paper-runhead className="paper-runhead mb-4 select-none text-body">
            {bookAuthor ? `${bookTitle} — ${bookAuthor}` : bookTitle}
          </p>
        ) : null}
        {/* The chapter headline, the draft's article header: the position
            written out as the eyebrow ("Kapitel Eins" — owner decision
            D-3), the chapter's name beneath it in the prose heading's own
            face, and the 1 px sepia rule that closes the block. It is text,
            never a control, so the card's focus ring still means "the text
            has the caret". A heading (level two: the book above owns the
            page's h1) — the paper's one outline node, unlike the runhead's
            styled paragraph. It is the frame's last piece, and it yields
            with the frame at focus depth 2, where the draft's paper is the
            prose alone. */}
        {focusDepth < 2 && headlineTitle !== null ? (
          <header className="flex flex-col items-center text-center">
            {chapterNumber !== undefined ? (
              <span className="mb-2 text-eyebrow uppercase text-area-writing">
                {t("chapters.chapterOrdinalLabel", { ordinal: chapterOrdinal(chapterNumber, locale) })}
              </span>
            ) : null}
            <h2 className="prose-headline">
              {headlineTitle}
            </h2>
            <div
              aria-hidden="true"
              className="mt-4 h-px w-12 rounded-full bg-cover-sepia/30"
              data-headline-rule
            />
          </header>
        ) : null}
        {/* The runhead (book · title input · save state · actions) stands
            above the card: its controls are their own focus targets, and
            the card's focus-within ring stays the text's own signal. The
            card holds the headline, the sheet and its ledger alone. */}
        <MarkdownEditor
          className="mt-4 drop-cap"
          focusRing={false}
          label={t("chapters.editorLabel")}
          value={body}
          onChange={scheduleAndCount}
          extensions={extensions}
          onReady={setEditor}
        />
        {focusDepth < 2 ? (
          <footer className="mt-4 flex items-baseline justify-between gap-4 text-meta text-muted">
            <span className="tabular-nums">{t("chapters.wordCount", { count: words })}</span>
            <span className="flex items-baseline gap-4">
              {chapterTotal ? (
                <span className="tabular-nums">
                  {t("chapters.position", { n: chapterNumber ?? 0, m: chapterTotal })}
                </span>
              ) : null}
              {/* The paper's settled autosave line (the draft's foot): the
                  success dot and the state in the paper's own words. It
                  reads the same one `status` the runhead's SaveIndicator
                  reads — two renderings, one owner — and stands only while
                  the text on screen is the server's (the band chip's rule:
                  idle counts as saved), so a pending or failed write is
                  named once, beside the text. No live region here: the
                  runhead's indicator is the state's announcement. The
                  draft's page marker stays off:
                  interim: no pagination — #820 */}
              {status === "idle" || status === "saved" ? (
                <span data-paper-foot-state className="flex items-center gap-1.5">
                  <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-success" />
                  {t("save.autosaved")}
                </span>
              ) : null}
            </span>
          </footer>
        ) : null}
      </div>
      {/* The drafted floating prompt bar stands below the card, in the
          column's flow — whatever the column mounted through the slot,
          fed from the one continuation this component owns. Chrome, like
          the frame: at depth 2 only the writing surface remains. */}
      {focusDepth < 2 && promptBar !== undefined ? (
        <>{promptBar({ onContinue: continueWriting, disabled: continuing })}</>
      ) : null}
    </div>
  );
}
