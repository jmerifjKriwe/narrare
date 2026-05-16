"use client";

import { use } from "react";
import { WorldBuildingView } from "@/components/workspace/WorldBuildingView";

interface Props {
  params: Promise<{ id: string }>;
}

export default function WorldbuildingPage({ params }: Props) {
  const { id } = use(params);

  return <WorldBuildingView novelId={id} />;
}
