"use client";

import { use, useMemo } from "react";
import { usePathname } from "next/navigation";
import { WorkspaceSidebar } from "@/components/workspace/WorkspaceSidebar";
import { useEditorStore } from "@/lib/stores/editorStore";

interface NovelLayoutProps {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}

/**
 * Novel workspace layout.
 *
 * Fixed full-screen overlay that covers the (app)/layout.tsx header.
 * Provides its own sidebar with navigation, chapter list, and user avatar.
 */
export default function NovelLayout({ children, params }: NovelLayoutProps) {
  const { id: novelId } = use(params);
  const pathname = usePathname();
  const focusMode = useEditorStore((s) => s.focusMode);

  // Determine which nav tab is active based on the current pathname
  const activeTab = useMemo(() => {
    const segments = pathname.split("/");
    const last = segments.pop() ?? "editor";
    // Valid tabs: editor, worldbuilding, analysis, settings
    if (["editor", "worldbuilding", "analysis", "settings"].includes(last)) {
      return last;
    }
    return "editor";
  }, [pathname]);

  return (
    <div className="fixed inset-0 flex bg-background">
      {/* Sidebar — always visible unless in focus mode */}
      {!focusMode && (
        <WorkspaceSidebar novelId={novelId} activeTab={activeTab} />
      )}

      {/* Main content area */}
      <div className="flex-1 overflow-hidden">
        {children}
      </div>
    </div>
  );
}
