"use client";

import { useCampaignChat } from "@/hooks/useCampaignChat";
import ChatWindow from "@/components/ChatWindow";
import Composer from "@/components/Composer";
import StageRail from "@/components/StageRail";

/** The full chat surface. Mounted only while the campaign is active, so
 *  "End" can unmount it (tearing down the session) and return to the home. */
export default function ChatExperience({ onEnd }: { onEnd: () => void }) {
  const chat = useCampaignChat();

  return (
    <main className="flex h-[100dvh] flex-col">
      <header className="flex items-center justify-between px-5 py-4">
        <button onClick={onEnd} className="flex items-center gap-2.5" aria-label="Home">
          <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-gradient-to-br from-accent-violet to-accent-cyan text-lg shadow-glow">
            ✦
          </div>
          <div className="text-left leading-tight">
            <h1 className="text-sm font-semibold accent-gradient-text">AutoMark AI</h1>
            <p className="text-[11px] text-white/40">Conversational Campaign Studio</p>
          </div>
        </button>
        <span className="chip">
          <span className="h-1.5 w-1.5 rounded-full bg-accent-lime" />
          Mark · online
        </span>
      </header>

      <div className="pb-2">
        <StageRail phase={chat.phase} />
      </div>

      <ChatWindow chat={chat} />

      <div className="px-4 pb-5 pt-2">
        <div className="glass-strong mx-auto w-full max-w-2xl rounded-3xl p-3 shadow-card">
          <Composer chat={chat} onEnd={onEnd} />
        </div>
      </div>
    </main>
  );
}
