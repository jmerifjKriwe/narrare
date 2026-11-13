import type { Chapter } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import type { DocumentDraft, SaveStatus } from "@shell/lib/save";
import { shortcutKeycap } from "@shell/lib/shortcuts";
import { Button } from "@shell/ui/Button";
import { ActionMenu } from "@shell/ui/Menu";
import { Notice } from "@shell/ui/Notice";

import { ChapterEditor } from "../ChapterEditor";
import type { FocusStep } from "../routes";
import { PromptBar } from "./PromptBar";

export function EditorColumn({
  railOverlay,
  dockOverlay,
  pending,
  failed,
  refreshFailed,
  orderFailed,
  showRail,
  current,
  chapterTotal,
  currentIndex,
  draftTitle,
  status,
  offer,
  bookTitle,
  bookAuthor,
  focus,
  railFilter,
  retry,
  onTitleChange,
  schedule,
  onProposalResolve,
  onRenameOpen,
  onDeleteOpen,
  onMove,
}: {
  railOverlay: boolean;
  dockOverlay: boolean;
  pending: boolean;
  failed: boolean;
  refreshFailed: boolean;
  orderFailed: boolean;
  showRail: boolean;
  current: Chapter | null;
  chapterTotal: number;
  currentIndex: number;
  draftTitle: string;
  status: SaveStatus;
  offer: string | null;
  bookTitle: string | undefined;
  /** The book's author, as the row holds it — the paper running head's
   *  second name; `undefined` leaves the head naming the book alone. */
  bookAuthor: string | undefined;
  focus: FocusStep;
  railFilter: string | null;
  retry: () => void;
  onTitleChange: (value: string) => void;
  schedule: (draft: DocumentDraft, changed: keyof DocumentDraft) => void;
  onProposalResolve: () => void;
  onRenameOpen: () => void;
  onDeleteOpen: () => void;
  onMove: (chapterId: string, delta: -1 | 1) => Promise<void>;
}) {
  const t = useTranslation();
  return (
    <section
      className="flex min-w-0 flex-1 flex-col items-center lg:pr-4"
      inert={railOverlay || dockOverlay || undefined}
    >
      {/* The writing surface is the card (F18): ChapterEditor paints it,
          the page only leaves it the column. The arithmetic is the
          workspace's: rail 224 + column 608 + dock 336 = the container's
          1168; the column is fluid around the card's 576 and keeps the
          16 px the focus ring needs, so the ring never lands on the dock's
          seam. The measure stays 544 inside the card, wherever the dock
          is. */}
      <div className="w-full py-6">
        <div className="mx-auto w-full max-w-[576px]">
          {pending ? (
          // The page has asked and is waiting — a named state, not a blank
          // or empty-looking book. Quiet and polite: nothing is wrong.
          <Notice tone="quiet" live="status" className="mt-6">
            {t("chapters.loading")}
          </Notice>
        ) : failed ? (
          // The book could not be loaded — refused or unreachable, with
          // nothing on screen to keep. The failure is named where the
          // retry is one press away (the shelf's outage shape).
          <Notice
            tone="danger"
            live="alert"
            className="mt-6"
            action={
              <Button variant="secondary" onClick={retry}>
                {t("chapters.retry")}
              </Button>
            }
          >
            {t("chapters.errorLoad")}
          </Notice>
        ) : (
          <>
            {refreshFailed ? (
              // The refresh failed, but the chapters on screen are the
              // last loaded ones: a quiet note beside the work, not the
              // outage's louder clothes — the editor and the rail stay,
              // and the retry asks again. The shelf's derived-boolean
              // pattern: one Notice, `live="status"` keeps it from being
              // silent to a screen reader — background speech about work
              // that stays, not an alert about work that is gone.
              <Notice
                tone="quiet"
                live="status"
                className="mt-6"
                action={
                  <Button variant="secondary" onClick={retry}>
                    {t("chapters.retry")}
                  </Button>
                }
              >
                {t("chapters.refreshFailed")}
              </Notice>
            ) : null}
            {orderFailed && !showRail ? (
              // The same refusal the rail's aside names, for the
              // states that have no rail to name it: the runhead's
              // move items render at a focus depth that hides the
              // rail and with the column collapsed, and a 409 there
              // would revert silently. One of the two notices is
              // mounted at any time — `showRail` partitions them —
              // so the alert is announced once, from the surface
              // that is on screen.
              <Notice tone="danger" live="alert" className="mt-6">
                {t("chapters.orderFailed")}
              </Notice>
            ) : null}
            {current ? (
              <ChapterEditor
                key={current.id}
                chapterId={current.id}
                body={current.body}
                title={draftTitle}
                onTitleChange={onTitleChange}
                status={status}
                schedule={schedule}
                proposal={offer ?? undefined}
                onProposalResolve={onProposalResolve}
                bookTitle={bookTitle}
                bookAuthor={bookAuthor}
                chapterNumber={current.position + 1}
                chapterTotal={chapterTotal}
                focusDepth={focus}
                // The drafted floating prompt bar, below the card: the
                // editor's slot hands the column the trigger and the
                // stream's busy state, the bar is the column's to mount.
                promptBar={(controls) => <PromptBar {...controls} />}
                actions={
                  <ActionMenu
                    label={t("chapters.actions")}
                    // The trigger names the chapter as the page holds
                    // it — the draft, not the cache row — so a typed
                    // title reaches the button's name before the save
                    // lands (the row catches up on the refetch).
                    triggerAriaLabel={t("chapters.actionsFor", {
                      title:
                        draftTitle ||
                        t("chapters.defaultTitle", { n: current.position + 1 }),
                    })}
                    items={[
                      {
                        id: "rename",
                        label: t("chapters.rename"),
                        onSelect: () => onRenameOpen(),
                      },
                      {
                        id: "moveUp",
                        // The ends are their own no-ops, offered but
                        // disabled: the shortcut the hint names is the
                        // rail's own reorder key from the shell registry
                        // (D6), discoverable exactly where the action
                        // lives — the platform's own keycap, not a
                        // literal. A filter disables the move wherever
                        // the row sits — a filtered list has no
                        // unambiguous neighbour — and the label itself
                        // says why, so the reason travels with the item
                        // to readers and screens alike.
                        label:
                          railFilter === null
                            ? t("chapters.moveUp")
                            : t("chapters.moveUpFiltered"),
                        shortcut: shortcutKeycap("rail.moveUp"),
                        disabled: railFilter !== null || currentIndex <= 0,
                        onSelect: () => void onMove(current.id, -1),
                      },
                      {
                        id: "moveDown",
                        label:
                          railFilter === null
                            ? t("chapters.moveDown")
                            : t("chapters.moveDownFiltered"),
                        shortcut: shortcutKeycap("rail.moveDown"),
                        disabled:
                          railFilter !== null || currentIndex >= chapterTotal - 1,
                        onSelect: () => void onMove(current.id, 1),
                      },
                      {
                        id: "delete",
                        label: t("chapters.delete"),
                        onSelect: () => onDeleteOpen(),
                      },
                    ]}
                  />
                }
              />
            ) : null}
          </>
        )}
        </div>
      </div>
    </section>
  );
}
