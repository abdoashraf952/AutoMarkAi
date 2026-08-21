"use client";

import { motion } from "framer-motion";
import type { Language, TargetOption } from "@/lib/types";

/**
 * The campaign-target question (the one fixed question, always asked first).
 * Renders the AI's ranked goal options as selectable cards — the recommended
 * one is visually highlighted with a warm "Recommended" badge and glow.
 */
export default function CampaignTargetCards({
  options,
  onPick,
  lang,
}: {
  options: TargetOption[];
  onPick: (goal: string, label: string) => void;
  lang?: Language;
}) {
  const rtl = lang === "ar";
  const recLabel = rtl ? "موصى به" : "Recommended";

  return (
    <div className={`grid w-full gap-2.5 ${rtl ? "rtl" : ""}`}>
      {options.map((opt, i) => (
        <motion.button
          key={opt.label + i}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.06, type: "spring", stiffness: 240, damping: 22 }}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => onPick(opt.goal, opt.label)}
          className={`group relative flex items-center gap-3 rounded-2xl px-4 py-3.5 text-left transition-all ${
            opt.recommended
              ? "border border-accent-amber/50 bg-accent-amber/10 shadow-glow-amber hover:bg-accent-amber/15"
              : "glass hover:border-accent-violet/60 hover:shadow-glow"
          }`}
        >
          <span
            className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl text-lg ${
              opt.recommended ? "bg-accent-amber/20" : "bg-white/5"
            }`}
          >
            {opt.recommended ? "⭐" : "🎯"}
          </span>
          <span className="flex-1">
            <span className="flex items-center gap-2">
              <span className="text-sm font-semibold text-white">{opt.label}</span>
              {opt.recommended && <span className="badge-rec">{recLabel}</span>}
            </span>
            {opt.description && (
              <span className="mt-0.5 block text-xs text-white/55">{opt.description}</span>
            )}
          </span>
          <span
            className={`transition-transform group-hover:translate-x-0.5 ${
              opt.recommended ? "text-accent-amber" : "text-white/30 group-hover:text-accent-cyan"
            }`}
          >
            →
          </span>
        </motion.button>
      ))}
    </div>
  );
}
