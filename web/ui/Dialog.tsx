import {
  Button,
  Dialog as RacDialog,
  DialogTrigger,
  Heading,
  Modal,
  ModalOverlay,
} from "react-aria-components";
import type { ReactNode } from "react";

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
                this heading; RAC reads it from context. */}
            <Heading slot="title" className="text-lg font-semibold">
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
  triggerAriaLabel,
  children,
  isOpen,
  onOpenChange,
}: {
  title: string;
  /** The visible label of the trigger, in the trigger shape. */
  triggerLabel?: string;
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
      <Button
        aria-label={triggerAriaLabel}
        className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground data-focus-visible:outline-none data-focus-visible:ring-2 data-focus-visible:ring-focus"
      >
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
