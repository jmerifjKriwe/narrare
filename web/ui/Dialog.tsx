import {
  Button,
  Dialog as RacDialog,
  DialogTrigger,
  Heading,
  Modal,
  ModalOverlay,
} from "react-aria-components";
import type { ReactNode } from "react";

import { buttonClass } from "./Button";

const MODAL_CHROME =
  "m-auto w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-overlay";

/** The modal's one painted surface: centered, tokened, titled — shared by
 *  both mountings (trigger-driven and shell-controlled) so they cannot
 *  drift apart. */
function DialogSurface({
  title,
  children,
}: {
  title: string;
  children: (close: () => void) => ReactNode;
}) {
  return (
    <Modal className={MODAL_CHROME}>
      <RacDialog>
        {({ close }) => (
          <>
            {/* Slot "title" is what wires the dialog's aria-labelledby to
                this heading; RAC reads it from context. `level={2}` keeps
                the element a deterministic h2 (#314): the content beneath
                it steps up from here, not from a library default. */}
            <Heading slot="title" level={2} className="text-emph font-semibold">
              {title}
            </Heading>
            {children(close)}
          </>
        )}
      </RacDialog>
    </Modal>
  );
}

/**
 * The shell's dialog: a labelled trigger, a centered modal, nothing else.
 * React-Aria owns the whole focus contract — the trap inside, Escape, the
 * restore to the trigger on close — so this wrapper only paints tokens onto
 * the parts. Content arrives as a function of `close`, because "done" is the
 * caller's decision (a saved form), never the shell's. The overlay scrolls:
 * `m-auto` centers a short dialog and lets a tall one (a form with many
 * fields) reach its buttons instead of clipping them.
 *
 * Controlled mode: with `isOpen` set, the dialog has no trigger of its own —
 * the opener lives elsewhere (the palette's modal slot mounts the dialog
 * already open, the palette row having been the press). The same React-Aria
 * contract stands: Escape and the dismissal close it through
 * `onOpenChange`, and the focus restores to whatever held it before.
 */
export function Dialog({
  title,
  triggerLabel,
  triggerVariant = "secondary",
  triggerAriaLabel,
  children,
  isOpen,
  onOpenChange,
}: {
  title: string;
  /** The visible label of the trigger, in the trigger shape. */
  triggerLabel?: string;
  /** The trigger's paint, through `buttonClass` — the shell button matrix
   *  the RAC trigger child wears (the primitive's <button> cannot sit in
   *  the trigger slot). The default is the quiet secondary: a dialog
   *  trigger is an opener, not the page's action (R37 — the old hardcoded
   *  `bg-primary` painted a filled primary onto every caller). Only a
   *  trigger that is its screen's one primary passes "primary" explicitly. */
  triggerVariant?: "primary" | "secondary";
  /** The accessible name of the trigger, when the visible label is not
   *  enough to tell one trigger from its siblings (a row of identical
   *  "Export" buttons names its novel here; the visible label stays). */
  triggerAriaLabel?: string;
  children: (close: () => void) => ReactNode;
  /** Controlled open, when there is no trigger on this page. Absent keeps
   *  the trigger shape. */
  isOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  if (isOpen !== undefined) {
    return (
      <ModalOverlay
        isDismissable
        isOpen={isOpen}
        onOpenChange={onOpenChange}
        className="fixed inset-0 z-30 flex overflow-y-auto bg-scrim p-4"
      >
        <DialogSurface title={title} children={children} />
      </ModalOverlay>
    );
  }
  return (
    <DialogTrigger>
      {/* RAC's Button, not the shell's: the trigger child must answer the
          press context the DialogTrigger provides (PressResponder warns
          and the trigger dies without it), and the primitive's <button>
          cannot. The paint still comes from the one matrix — `buttonClass`
          is exactly its export for a control that is not the primitive
          (the bar's settings link wears it the same way). */}
      <Button aria-label={triggerAriaLabel} className={buttonClass(triggerVariant, "md")}>
        {triggerLabel}
      </Button>
      <ModalOverlay
        isDismissable
        className="fixed inset-0 z-30 flex overflow-y-auto bg-scrim p-4"
      >
        <DialogSurface title={title} children={children} />
      </ModalOverlay>
    </DialogTrigger>
  );
}
