"use client";

import { use } from "react";
import { AnalysisPanel } from "@/components/studio/AnalysisPanel";

export default function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <AnalysisPanel novelId={id} />;
}
