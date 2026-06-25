"use client";

import { useRef, useState } from "react";
import { motion } from "framer-motion";

const ACCEPT = ["image/jpeg", "image/png", "image/webp"];

export default function ImageUpload({ onSelect }: { onSelect: (file: File) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function handle(file?: File | null) {
    if (!file) return;
    if (!ACCEPT.includes(file.type)) {
      setErr("Please use a JPG, PNG, or WebP image.");
      return;
    }
    setErr(null);
    onSelect(file);
  }

  return (
    <div className="w-full">
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
        className={`flex w-full flex-col items-center justify-center gap-2 rounded-3xl border-2 border-dashed px-6 py-9 text-center transition-all ${
          drag
            ? "border-accent-cyan bg-accent-cyan/10"
            : "border-white/15 bg-white/5 hover:border-accent-violet/60 hover:bg-white/8"
        }`}
      >
        <motion.div
          animate={{ y: drag ? -4 : [0, -5, 0] }}
          transition={{ duration: 2.4, repeat: Infinity }}
          className="text-3xl"
        >
          🖼️
        </motion.div>
        <div className="text-sm font-semibold text-white">
          Drop your photo here, or click to browse
        </div>
        <div className="text-xs text-white/45">JPG · PNG · WebP</div>
      </motion.button>

      {err && <p className="mt-2 text-center text-xs text-red-300">{err}</p>}

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT.join(",")}
        className="hidden"
        onChange={(e) => handle(e.target.files?.[0])}
      />
    </div>
  );
}
