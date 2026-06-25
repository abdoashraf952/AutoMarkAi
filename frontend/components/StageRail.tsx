"use client";

import { motion } from "framer-motion";
import type { ChatPhase } from "@/hooks/useCampaignChat";

const STEPS = [
  { key: "setup", label: "Setup", emoji: "⚙️" },
  { key: "questions", label: "Q&A", emoji: "💬" },
  { key: "visual", label: "Visual", emoji: "🎨" },
  { key: "copy", label: "Copy", emoji: "✍️" },
  { key: "publish", label: "Publish", emoji: "🚀" },
];

// Map the fine-grained phase to a coarse rail index.
function phaseToIndex(phase: ChatPhase): number {
  switch (phase) {
    case "language":
    case "marketing_type":
    case "image":
    case "image_mode":
    case "budget":
    case "goal":
    case "starting":
      return 0;
    case "questions":
    case "building":
      return 1;
    case "image_review":
    case "image_regenerating":
    case "max_regen":
      return 2;
    case "text_review":
    case "text_editing":
      return 3;
    case "done":
    case "publishing":
    case "published":
      return 4;
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
                    ? "0 0 0 1px rgba(124,92,255,0.5), 0 6px 24px -6px rgba(124,92,255,0.8)"
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
