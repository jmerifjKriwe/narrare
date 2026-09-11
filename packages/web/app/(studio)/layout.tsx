"use client";

import { QuickCaptureProvider } from "@/components/notes/QuickCaptureProvider";
import { AuthGate } from "@/components/studio/shell/AuthGate";

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  return (
    // QuickCaptureProvider mounts ONCE here — inside AuthGate and the root
    // layout's QueryProvider — so quick capture (Ctrl/⌘+Shift+U) is live on
    // every studio page: shell-mounted (novel workspace) AND non-shell
    // (/scratchpad renders ScratchpadWorkspace directly, no shell). A second
    // mount in the shell would double-fire the shortcut and double-render
    // panels (NOTES-001 §7, T29b).
    <AuthGate>
      <QuickCaptureProvider>{children}</QuickCaptureProvider>
    </AuthGate>
  );
}
