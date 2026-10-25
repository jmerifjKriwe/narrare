/**
 * The proposal bus: how a dock surface offers text into the workspace editor
 * without its capability importing the writing one. The shell file is the
 * only shared point — the offering panel calls `offerProposal`, the
 * workspace subscribes and feeds its editor's proposal props.
 *
 * One pending offer at a time, and last-wins: a new offer replaces the one
 * before it WITHOUT resolving it — the editor swaps the superseded ghost's
 * text in place, keeping the old ghost's position, by its own contract (the
 * Task-1 parked note). An offer is spent when the editor resolves it, Tab or
 * Esc either way, and the workspace clears its slot then. And an offer never
 * outlives the editor it was made to: the subscription dies with the
 * workspace, and a fresh mount hears nothing until a new offer — a stale
 * ghost must not follow the user across navigation.
 */
export type ProposalListener = (text: string) => void;

const listeners = new Set<ProposalListener>();

/** Offer text into the editor. Every subscriber's pending offer is replaced
 *  by this one; the newest offer is the only one alive. */
export function offerProposal(text: string): void {
  for (const listener of listeners) listener(text);
}

/** Subscribe to offers. The return value is the unsubscribe — the workspace
 *  calls it on unmount, which is what keeps an offer from surviving a
 *  departure. */
export function subscribeProposal(listener: ProposalListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
