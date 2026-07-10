"use client";

import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

interface ConfirmDialogProps {
  /** Controlled open state. */
  readonly open: boolean;
  /** Called when the dialog should close (overlay click, escape, cancel). */
  readonly onOpenChange: (open: boolean) => void;
  /** Dialog title (required for accessibility). */
  readonly title: string;
  /** Longer description of what will happen. */
  readonly description?: string;
  /** Label for the confirm button. Defaults to `studio.aiActions.accept`. */
  readonly confirmLabel?: string;
  /** Label for the cancel button. Defaults to `common.cancel`. */
  readonly cancelLabel?: string;
  /** Called when the user confirms the action. */
  readonly onConfirm: () => void;
  /** Visual variant of the confirm button. */
  readonly variant?: "default" | "destructive";
}

/**
 * Accessible confirmation dialog built on Radix AlertDialog.
 *
 * Use for any destructive or irreversible action (delete, reset, etc.).
 * The dialog is controlled — the parent manages `open` state.
 *
 * i18n defaults to `studio.aiActions.accept` (confirm) and `common.cancel`.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  cancelLabel,
  onConfirm,
  variant = "default",
}: ConfirmDialogProps) {
  const tAction = useTranslations("studio.aiActions");
  const tCommon = useTranslations("common");

  const confirmText = confirmLabel ?? tAction("accept");
  const cancelText = cancelLabel ?? tCommon("cancel");

  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
        <AlertDialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border bg-card p-6 shadow-2xl data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95">
          <AlertDialog.Title className="text-lg font-medium text-foreground">
            {title}
          </AlertDialog.Title>
          {description && (
            <AlertDialog.Description className="mt-2 text-sm text-muted-foreground">
              {description}
            </AlertDialog.Description>
          )}
          <div className="mt-6 flex justify-end gap-3">
            <AlertDialog.Cancel asChild>
              <button
                type="button"
                data-testid="confirm-dialog-cancel"
                className="rounded-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground hover:bg-accent transition-colors"
              >
                {cancelText}
              </button>
            </AlertDialog.Cancel>
            <AlertDialog.Action asChild>
              <button
                type="button"
                data-testid="confirm-dialog-confirm"
                onClick={onConfirm}
                className={cn(
                  "rounded-md px-4 py-2 text-sm font-medium shadow-sm transition-opacity hover:opacity-90",
                  variant === "destructive"
                    ? "bg-destructive text-destructive-foreground"
                    : "bg-primary text-primary-foreground",
                )}
              >
                {confirmText}
              </button>
            </AlertDialog.Action>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
