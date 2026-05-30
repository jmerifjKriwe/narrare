"use client";

import { use } from "react";
import { ChatPanel } from "@/components/studio/editor/ChatPanel";

export default function ChatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <div className="flex h-full">
      <ChatPanel projectId={id} onClose={() => {}} />
    </div>
  );
}
