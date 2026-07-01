"use client";

import { AuthGate } from "@/components/studio/shell/AuthGate";

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  return <AuthGate>{children}</AuthGate>;
}
