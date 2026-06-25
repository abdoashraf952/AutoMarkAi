"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import Lightbox from "../Lightbox";

/** Gallery shown after max regenerations — enlarge a tile, then click to pick it. */
export default function ImageGrid({
  images,
  onPick,
  disabled,
  hasOriginal,
}: {
  images: string[];
  onPick: (index: number) => void;
  disabled?: boolean;
  hasOriginal?: boolean;
}) {
  const [zoom, setZoom] = useState<number | null>(null);
  const labelFor = (i: number) =>
    hasOriginal && i === 0 ? "Original" : `#${hasOriginal ? i : i + 1}`;

  return (
    <div className="w-full max-w-md">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {images.map((src, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
            className="group relative overflow-hidden rounded-2xl border border-white/12 bg-ink-800"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={src} alt={labelFor(i)} className="aspect-square w-full object-cover" />

            {/* original-photo badge */}
            {hasOriginal && i === 0 && (
              <span className="absolute left-1.5 top-1.5 rounded-full bg-accent-violet/90 px-2 py-0.5 text-[10px] font-semibold text-white">
                Your photo
              </span>
            )}

            {/* zoom button — enlarge without selecting */}
            <button
              onClick={() => setZoom(i)}
              aria-label={`Enlarge option ${i + 1}`}
              className="absolute right-1.5 top-1.5 flex h-7 w-7 items-center justify-center rounded-full bg-black/50 text-white opacity-0 backdrop-blur-sm transition group-hover:opacity-100"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                <path
                  d="M9 3H5a2 2 0 0 0-2 2v4m6 10H5a2 2 0 0 1-2-2v-4M15 3h4a2 2 0 0 1 2 2v4m-6 10h4a2 2 0 0 0 2-2v-4"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </button>

            {/* pick button */}
            <motion.button
              disabled={disabled}
              onClick={() => onPick(i)}
              whileTap={{ scale: 0.97 }}
              className="absolute inset-0 flex items-end justify-center bg-gradient-to-t from-black/70 to-transparent opacity-0 transition-opacity group-hover:opacity-100 disabled:cursor-not-allowed"
            >
              <span className="mb-2 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-ink-900">
                Choose {labelFor(i)}
              </span>
            </motion.button>
          </motion.div>
        ))}
      </div>

      <Lightbox
        src={zoom !== null ? images[zoom] : ""}
        open={zoom !== null}
        onClose={() => setZoom(null)}
        caption={zoom !== null ? labelFor(zoom) : undefined}
      />
    </div>
  );
}
