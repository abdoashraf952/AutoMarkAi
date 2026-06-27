"use client";

import { useRef, useState } from "react";
import { motion } from "framer-motion";

/**
 * One step in the sequential client-asset upload flow (CHANGE 4). Shows a
 * title, a short "why it helps" line, a dropzone, and (for optional assets) a
 * Skip button.
 */
export default function FileUploadStep({
  title,
  why,
  required,
  skipLabel,
  onSelect,
  onSkip,
  rtl,
}: {
  title: string;
  why: string;
  required: boolean;
  skipLabel: string;
  onSelect: (file: File) => void;
  onSkip: () => void;
  rtl?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);

  function handle(file?: File | null) {
    if (file) onSelect(file);
  }

  return (
    <div className={`w-full ${rtl ? "rtl" : ""}`}>
      <div className="mb-2 text-center">
        <div className="text-sm font-semibold text-white">{title}</div>
        <div className="text-xs text-white/45">{why}</div>
      </div>

      <motion.button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          handle(e.dataTransfer.files?.[0]);
        }}
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
        className={`flex w-full flex-col items-center justify-center gap-1.5 rounded-3xl border-2 border-dashed px-6 py-7 text-center transition-all ${
          drag
            ? "border-accent-cyan bg-accent-cyan/10"
            : "border-white/15 bg-white/5 hover:border-accent-violet/60 hover:bg-white/8"
        }`}
      >
        <span className="text-2xl">📎</span>
        <div className="text-xs font-semibold text-white">
          Drop a file here, or click to browse
        </div>
        <div className="text-[11px] text-white/40">PDF · JPG · PNG</div>
      </motion.button>

      {!required && (
        <div className="mt-3 flex items-center justify-center">
          <motion.button
            type="button"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={onSkip}
            className="btn-ghost !py-2 text-xs"
          >
            {skipLabel}
          </motion.button>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,application/pdf"
        className="hidden"
        onChange={(e) => handle(e.target.files?.[0])}
      />
    </div>
  );
}
