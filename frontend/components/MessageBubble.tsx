"use client";

import { motion } from "framer-motion";
import type { ChatMessage } from "@/hooks/useCampaignChat";
import MarkdownLite from "./MarkdownLite";
import ImageCard from "./cards/ImageCard";
import ImageGrid from "./cards/ImageGrid";
import CopyCard from "./cards/CopyCard";
import DoneCard from "./cards/DoneCard";
import PublishCard from "./cards/PublishCard";
import type { Language } from "@/lib/types";

export default function MessageBubble({
  message,
  onPickImage,
  pickDisabled,
  onConfirmText,
  textDisabled,
  lang,
}: {
  message: ChatMessage;
  onPickImage: (index: number) => void;
  pickDisabled?: boolean;
  onConfirmText?: (copyIndex: number, headlineIndex: number, copyText: string, headlineText: string) => void;
  textDisabled?: boolean;
  lang?: Language;
}) {
  const isUser = message.role === "user";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 24 }}
      className={`flex w-full ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div className={`flex max-w-[88%] gap-2.5 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
        {!isUser && message.kind === "text" && <BotAvatar />}
        <Content
          message={message}
          onPickImage={onPickImage}
          pickDisabled={pickDisabled}
          onConfirmText={onConfirmText}
          textDisabled={textDisabled}
          lang={lang}
        />
      </div>
    </motion.div>
  );
}

function Content({
  message,
  onPickImage,
  pickDisabled,
  onConfirmText,
  textDisabled,
  lang,
}: {
  message: ChatMessage;
  onPickImage: (index: number) => void;
  pickDisabled?: boolean;
  onConfirmText?: (copyIndex: number, headlineIndex: number, copyText: string, headlineText: string) => void;
  textDisabled?: boolean;
  lang?: Language;
}) {
  const isUser = message.role === "user";

  switch (message.kind) {
    case "text":
      return (
        <div
          className={
            isUser
              ? "rounded-2xl rounded-br-md bg-gradient-to-br from-accent-violet to-[#4f46e5] px-4 py-2.5 text-sm text-white shadow-glow"
              : "glass rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed text-white/90"
          }
        >
          <MarkdownLite text={message.text || ""} />
        </div>
      );

    case "user-image":
      return (
        <div className="overflow-hidden rounded-2xl rounded-br-md border border-white/12 shadow-glow">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={message.imageSrc} alt="Uploaded" className="max-h-52 w-auto object-cover" />
        </div>
      );

    case "image-card":
      return <ImageCard src={message.imageSrc || ""} caption={message.imageCaption} />;

    case "image-grid":
      return (
        <ImageGrid
          images={message.images || []}
          onPick={onPickImage}
          disabled={pickDisabled}
          hasOriginal={message.hasOriginal}
        />
      );

    case "copy-card":
      return (
        <CopyCard
          copies={message.copy?.copies || []}
          headlines={message.copy?.headlines || []}
          cta={message.copy?.cta || ""}
          lang={lang}
          onConfirm={onConfirmText}
          disabled={textDisabled}
        />
      );

    case "done-card":
      return <DoneCard bundle={message.bundle || {}} image={message.finalImage || ""} />;

    case "publish-card":
      return (
        <PublishCard
          result={message.publish?.result || null}
          error={message.publish?.error || null}
          sim={message.publish?.sim ?? true}
        />
      );

    default:
      return null;
  }
}

function BotAvatar() {
  return (
    <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent-violet to-accent-cyan text-sm shadow-glow">
      ✦
    </div>
  );
}
