import {
  Button,
  Dialog as RacDialog,
  DialogTrigger,
  Heading,
  Modal,
  ModalOverlay,
} from "react-aria-components";
import type { ReactNode } from "react";

/**
 * The shell's dialog: a labelled trigger, a centered modal, nothing else.
 * React-Aria owns the whole focus contract — the trap inside, Escape, the
 * restore to the trigger on close — so this wrapper only paints tokens onto
 * the parts. Content arrives as a function of `close`, because "done" is the
 * caller's decision (a saved form), never the shell's. The overlay scrolls:
 * `m-auto` centers a short dialog and lets a tall one (a form with many
 * fields) reach its buttons instead of clipping them.
 */
export function Dialog({
  title,
  triggerLabel,
  children,
}: {
  title: string;
  triggerLabel: string;
  children: (close: () => void) => ReactNode;
}) {
  return (
    <DialogTrigger>
      <Button className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground data-focus-visible:outline-none data-focus-visible:ring-2 data-focus-visible:ring-focus">
        {triggerLabel}
      </Button>
      <ModalOverlay
        isDismissable
        className="fixed inset-0 z-30 flex overflow-y-auto bg-scrim p-4"
      >
        <Modal className="m-auto w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-overlay">
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
      </ModalOverlay>
    </DialogTrigger>
  );
}
