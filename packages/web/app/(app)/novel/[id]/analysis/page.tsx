"use client";

import { use } from "react";
import { AnalysisView } from "@/components/workspace/AnalysisView";

interface Props {
  params: Promise<{ id: string }>;
}

export default function AnalysisPage({ params }: Props) {
  const { id } = use(params);

  return <AnalysisView novelId={id} />;
}
