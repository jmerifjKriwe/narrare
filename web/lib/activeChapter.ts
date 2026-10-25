/**
 * The active-chapter seam: how a dock surface learns which chapter the
 * workspace is editing without its capability importing the writing one —
 * the proposal bus's shape, for state instead of offers. The workspace owns
 * the selection and publishes it; the Wissen dock (extraction reads the
 * chapter the editor is showing) subscribes.
 *
 * The current value is kept, not just events: a dock mounts after the
 * selection it cares about happened, so reading `activeChapter()` on mount
 * must answer — an event-only bus would make every dock wait for a next
 * selection it may never see. Like the proposal bus, nothing outlives its
 * owner: the workspace publishes null as it goes, and a subscription dies
 * with the component that made it.
 */
export type ActiveChapterListener = (chapterId: string | null) => void;

let current: string | null = null;
const listeners = new Set<ActiveChapterListener>();

/** The chapter the workspace is editing right now, if any. */
export function activeChapter(): string | null {
  return current;
}

/** The workspace's own call: every selection change is published — null
 *  included, because "no chapter open" is a dock-relevant answer too. */
export function publishActiveChapter(chapterId: string | null): void {
  current = chapterId;
  for (const listener of listeners) listener(chapterId);
}

/** Subscribe to selection changes. The return value is the unsubscribe —
 *  the dock calls it on unmount, which is what keeps a selection change
 *  from reaching a surface nobody is looking at. */
export function subscribeActiveChapter(listener: ActiveChapterListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
