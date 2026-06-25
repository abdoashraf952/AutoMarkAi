"use client";

import { useEffect, useRef } from "react";
import { AnimatePresence } from "framer-motion";
import type { CampaignChat } from "@/hooks/useCampaignChat";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";

export default function ChatWindow({ chat }: { chat: CampaignChat }) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const showTyping = chat.loading.active;
  const pickDisabled = chat.phase !== "max_regen";
  const textDisabled = chat.phase !== "text_review";

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chat.messages.length, showTyping]);

  return (
    <div className="scroll-area mx-auto flex w-full max-w-2xl flex-1 flex-col gap-4 overflow-y-auto px-4 py-6">
      <AnimatePresence initial={false}>
        {chat.messages.map((m) => (
          <MessageBubble
            key={m.id}
            message={m}
            onPickImage={chat.pickImage}
            pickDisabled={pickDisabled}
            onConfirmText={chat.submitText}
            textDisabled={textDisabled}
            lang={chat.lang}
          />
        ))}
      </AnimatePresence>

      <AnimatePresence>{showTyping && <TypingIndicator key="typing" />}</AnimatePresence>

      <div ref={bottomRef} />
    </div>
  );
}
