"use client";

import { Toaster as SonnerToaster } from "sonner";

/**
 * Global toast notification provider.
 *
 * Add `<Toaster />` once in the studio layout. Trigger toasts from any
 * component via the `toast` import from "sonner":
 *
 *   import { toast } from "sonner";
 *   toast.success("Saved");
 *   toast.error("Failed", { action: { label: "Retry", onClick: retry } });
 *
 * Theming uses the Narrare design tokens (CSS variables) so dark mode works
 * automatically via the `.dark` class.
 */
export function Toaster() {
  return (
    <SonnerToaster
      position="bottom-right"
      toastOptions={{
        unstyled: true,
        classNames: {
          toast:
            "bg-card border border-border rounded-lg shadow-lg p-4 flex items-center gap-3 w-full font-sans text-sm text-foreground data-[type=success]:border-l-4 data-[type=success]:border-l-green-500 data-[type=error]:border-l-4 data-[type=error]:border-l-destructive data-[type=warning]:border-l-4 data-[type=warning]:border-l-amber-500 data-[type=info]:border-l-4 data-[type=info]:border-l-primary data-[type=loading]:border-l-4 data-[type=loading]:border-l-primary",
          title: "text-sm font-medium text-foreground",
          description: "text-xs text-muted-foreground",
          actionButton:
            "px-3 py-1.5 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:opacity-90 transition-opacity",
          cancelButton:
            "px-3 py-1.5 text-xs font-medium rounded-md bg-muted text-muted-foreground hover:bg-accent transition-colors",
        },
      }}
      duration={4000}
    />
  );
}
