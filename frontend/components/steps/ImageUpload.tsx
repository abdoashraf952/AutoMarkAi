"use client";

import { useRef, useState } from "react";
import { motion } from "framer-motion";

const ACCEPT = ["image/jpeg", "image/png", "image/webp"];

/**
 * Multi-photo uploader for real estate unit photos (CHANGE 2). The user can add
 * several photos; thumbnails show what's queued. At least one is required.
 */
export default function ImageUpload({
  onSelect,
  label = "Upload photos of your units 📸",
  invalidMsg = "Please use JPG, PNG, or WebP images.",
  doneLabel = "Continue →",
  rtl,
}: {
  onSelect: (files: File[]) => void;
  label?: string;
  invalidMsg?: string;
  doneLabel?: string;
  rtl?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [files, setFiles] = useState<File[]>([]);

  function add(list?: FileList | null) {
    if (!list) return;
    const incoming = Array.from(list);
    const valid = incoming.filter((f) => ACCEPT.includes(f.type));
    if (valid.length !== incoming.length) setErr(invalidMsg);
    else setErr(null);
    if (valid.length) setFiles((prev) => [...prev, ...valid]);
  }

  function removeAt(i: number) {
    setFiles((prev) => prev.filter((_, idx) => idx !== i));
  }

  return (
    <div className={`w-full ${rtl ? "rtl" : ""}`}>
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
          add(e.dataTransfer.files);
        }}
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
        className={`flex w-full flex-col items-center justify-center gap-2 rounded-3xl border-2 border-dashed px-6 py-8 text-center transition-all ${
          drag
            ? "border-accent-cyan bg-accent-cyan/10"
            : "border-white/15 bg-white/5 hover:border-accent-violet/60 hover:bg-white/8"
        }`}
      >
        <span className="text-3xl">🏗️</span>
        <div className="text-sm font-semibold text-white">{label}</div>
        <div className="text-xs text-white/45">JPG · PNG · WebP · add as many as you like</div>
      </motion.button>

      {err && <p className="mt-2 text-center text-xs text-red-300">{err}</p>}

      {files.length > 0 && (
        <>
          <div className="mt-3 flex flex-wrap gap-2">
            {files.map((f, i) => (
              <div key={i} className="relative h-16 w-16 overflow-hidden rounded-xl border border-white/12">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={URL.createObjectURL(f)} alt={`Unit ${i + 1}`} className="h-full w-full object-cover" />
                <button
                  onClick={() => removeAt(i)}
                  className="absolute right-0.5 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-xs text-white"
                  aria-label="Remove"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
          <button onClick={() => onSelect(files)} className="btn-primary mt-3 w-full">
            {doneLabel}
          </button>
        </>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT.join(",")}
        multiple
        className="hidden"
        onChange={(e) => add(e.target.files)}
      />
    </div>
  );
}
