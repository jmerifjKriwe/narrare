"use client";

import { motion } from "motion/react";
import { listContainerVariants, listItemVariants } from "@/lib/motion-variants";
import type { Message } from "./ChatMessage";
import { ChatMessage } from "./ChatMessage";

interface SessionMessageListProps {
  readonly messages: Message[];
  readonly addedIds: Set<string>;
  readonly onAddToDraft: (messageId: string, prose: string) => void;
  readonly aiDraftBadge: string;
  readonly addToDraftLabel: string;
  readonly addedToDraftLabel: string;
}

export function SessionMessageList({
  messages,
  addedIds,
  onAddToDraft,
  aiDraftBadge,
  addToDraftLabel,
  addedToDraftLabel,
}: SessionMessageListProps) {
  return (
    <motion.div
      variants={listContainerVariants}
      initial="hidden"
      animate="visible"
      className="flex flex-col gap-3"
    >
      {messages.map((msg) => (
        <motion.div key={msg.id} variants={listItemVariants}>
          <ChatMessage
            message={msg}
            isAdded={addedIds.has(msg.id)}
            onAddToDraft={(prose) => onAddToDraft(msg.id, prose)}
            aiDraftBadge={aiDraftBadge}
            addToDraftLabel={addToDraftLabel}
            addedToDraftLabel={addedToDraftLabel}
          />
        </motion.div>
      ))}
    </motion.div>
  );
}
