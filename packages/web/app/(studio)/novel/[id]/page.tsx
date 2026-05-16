"use client";

import { use } from "react";
import { EditorView } from "@/components/studio/EditorView";

export default function EditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <EditorView novelId={id} />;
}
