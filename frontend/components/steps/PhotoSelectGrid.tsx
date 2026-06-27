"use client";

import { useState } from "react";
import { motion } from "framer-motion";

/**
 * Multi-select grid for choosing which uploaded unit photos to include in the
 * ad (CHANGE 2). Tap to toggle; all photos start selected.
 */
export default function PhotoSelectGrid({
  images,
  confirmLabel,
  onConfirm,
  rtl,
}: {
  images: string[];
  confirmLabel: string;
  onConfirm: (indices: number[]) => void;
  rtl?: boolean;
}) {
  const [selected, setSelected] = useState<number[]>(images.map((_, i) => i));

  function toggle(i: number) {
    setSelected((prev) => (prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]));
  }

  return (
    <div className={`flex w-full flex-col gap-3 ${rtl ? "rtl" : ""}`}>
      <div className="grid grid-cols-3 gap-2.5 sm:grid-cols-4">
        {images.map((src, i) => {
          const on = selected.includes(i);
          return (
            <motion.button
              key={i}
              type="button"
              whileTap={{ scale: 0.96 }}
              onClick={() => toggle(i)}
              className={`relative overflow-hidden rounded-2xl border-2 transition-all ${
                on ? "border-accent-cyan shadow-glow" : "border-white/10 opacity-60"
              }`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={src} alt={`Unit ${i + 1}`} className="aspect-square w-full object-cover" />
              <span
                className={`absolute right-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                  on ? "bg-accent-cyan text-ink-900" : "bg-black/50 text-white/70"
                }`}
              >
                {on ? "✓" : ""}
              </span>
            </motion.button>
          );
        })}
      </div>
      <button
        onClick={() => onConfirm(selected)}
        disabled={selected.length === 0}
        className="btn-primary w-full"
      >
        {confirmLabel} ({selected.length})
      </button>
    </div>
  );
}
