"use client";

import { use } from "react";
import { WorldBuilding } from "@/components/studio/WorldBuilding";

export default function WorldbuildingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <WorldBuilding novelId={id} />;
}
