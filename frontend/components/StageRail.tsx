"use client";

import { motion } from "framer-motion";
import type { ChatPhase } from "@/hooks/useCampaignChat";

const STEPS = [
  { key: "setup", label: "Photos & files", emoji: "📸" },
  { key: "goal", label: "Your goal", emoji: "🎯" },
  { key: "questions", label: "Compound", emoji: "🏗️" },
  { key: "photos", label: "Pick photos", emoji: "🖼️" },
  { key: "words", label: "Ad copy", emoji: "✍️" },
  { key: "launch", label: "Launch", emoji: "🚀" },
];

// Map the fine-grained phase to a coarse rail index.
function phaseToIndex(phase: ChatPhase): number {
  switch (phase) {
    case "language":
    case "image":
    case "file_uploads":
    case "budget":
    case "starting":
      return 0;
    case "campaign_target":
      return 1;
    case "questions":
    case "building":
      return 2;
    case "photo_select":
      return 3;
    case "text_review":
      return 4;
    case "done":
    case "publishing":
    case "published":
      return 5;
    default:
      return 0;
  }
}

export default function StageRail({ phase }: { phase: ChatPhase }) {
  const current = phaseToIndex(phase);

  return (
    <div className="mx-auto flex w-full max-w-2xl items-center gap-1.5 px-4">
      {STEPS.map((step, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <div key={step.key} className="flex flex-1 items-center gap-1.5">
            <div className="flex flex-col items-center gap-1">
              <motion.div
                animate={{
                  scale: active ? 1.1 : 1,
                  boxShadow: active
                    ? "0 0 0 1px rgba(99,102,241,0.5), 0 6px 24px -6px rgba(99,102,241,0.8)"
                    : "0 0 0 0 transparent",
                }}
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm transition-colors ${
                  done
                    ? "bg-accent-violet/30 text-white"
                    : active
                    ? "bg-gradient-to-br from-accent-violet to-accent-cyan text-white"
                    : "bg-white/5 text-white/35"
                }`}
              >
                {done ? "✓" : step.emoji}
              </motion.div>
              <span
                className={`hidden text-[10px] font-medium sm:block ${
                  active ? "text-white" : "text-white/35"
                }`}
              >
                {step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className="relative mb-4 h-0.5 flex-1 overflow-hidden rounded-full bg-white/8">
                <motion.div
                  className="absolute inset-y-0 left-0 bg-gradient-to-r from-accent-violet to-accent-cyan"
                  animate={{ width: i < current ? "100%" : "0%" }}
                  transition={{ duration: 0.5 }}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
