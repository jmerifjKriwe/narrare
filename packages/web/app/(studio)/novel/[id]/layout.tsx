"use client";

import { StudioWorkspaceShell } from "@/components/studio/shell/StudioWorkspaceShell";

export default function NovelLayout({ children }: { children: React.ReactNode }) {
  return <StudioWorkspaceShell>{children}</StudioWorkspaceShell>;
}
