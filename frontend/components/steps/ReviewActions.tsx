"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import TextSend from "./TextSend";

/**
 * Approve / request-changes control used for both image and text review.
 * When the user asks for changes, a feedback composer slides in.
 */
export default function ReviewActions({
  approveLabel,
  changeLabel,
  feedbackPlaceholder,
  onApprove,
  onChange,
  rtl,
  approveOnly,
}: {
  approveLabel: string;
  changeLabel: string;
  feedbackPlaceholder: string;
  onApprove: () => void;
  onChange: (feedback: string) => void;
  rtl?: boolean;
  approveOnly?: boolean;
}) {
  const [mode, setMode] = useState<"idle" | "feedback">("idle");

  return (
    <div className="w-full space-y-3">
      <AnimatePresence mode="wait">
        {mode === "feedback" ? (
          <motion.div
            key="fb"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="space-y-2"
          >
            <TextSend
              placeholder={feedbackPlaceholder}
              sendLabel={changeLabel}
              onSend={onChange}
              rtl={rtl}
            />
            <button
              onClick={() => setMode("idle")}
              className="text-xs text-white/40 hover:text-white/70"
            >
              ← back
            </button>
          </motion.div>
        ) : (
          <motion.div
            key="buttons"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex flex-wrap gap-2.5"
          >
            <button onClick={onApprove} className="btn-primary flex-1">
              ✓ {approveLabel}
            </button>
            {!approveOnly && (
              <button onClick={() => setMode("feedback")} className="btn-ghost flex-1">
                ✎ {changeLabel}
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
