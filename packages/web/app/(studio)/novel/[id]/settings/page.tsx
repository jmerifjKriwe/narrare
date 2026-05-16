"use client";

import { use } from "react";
import { SettingsView } from "@/components/studio/SettingsView";

export default function SettingsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <SettingsView novelId={id} />;
}
