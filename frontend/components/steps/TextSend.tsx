"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

/**
 * Reusable auto-growing text composer. Enter sends; Shift+Enter = newline.
 * Used for the campaign goal, each question answer, and feedback inputs.
 */
export default function TextSend({
  placeholder,
  sendLabel,
  onSend,
  rtl,
  autoFocusKey,
}: {
  placeholder?: string;
  sendLabel: string;
  onSend: (text: string) => void;
  rtl?: boolean;
  /** change this to refocus/clear when moving to a new question */
  autoFocusKey?: string | number;
}) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setValue("");
    ref.current?.focus();
  }, [autoFocusKey]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [value]);

  const canSend = value.trim().length > 0;
  function submit() {
    if (!canSend) return;
    onSend(value.trim());
    setValue("");
  }

  return (
    <div className="flex w-full items-end gap-2">
      <textarea
        ref={ref}
        rows={1}
        value={value}
        placeholder={placeholder}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        className={`field max-h-40 resize-none ${rtl ? "rtl" : ""}`}
      />
      <motion.button
        whileTap={{ scale: 0.94 }}
        disabled={!canSend}
        onClick={submit}
        className="btn-primary flex-shrink-0 !px-4 !py-3"
        aria-label={sendLabel}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
          <path
            d="M3.4 20.4 21 12 3.4 3.6 3 10l12 2-12 2 .4 6.4Z"
            fill="currentColor"
          />
        </svg>
      </motion.button>
    </div>
  );
}
