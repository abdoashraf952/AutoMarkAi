"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import Lightbox from "../Lightbox";

/** A single generated/uploaded ad visual, revealed with a soft zoom.
 *  Click (or the expand button) to maximize it in a full-screen viewer. */
export default function ImageCard({
  src,
  caption,
}: {
  src: string;
  caption?: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="glass max-w-xs overflow-hidden rounded-3xl p-2 shadow-card">
      <div className="group relative overflow-hidden rounded-2xl bg-ink-800">
        {src ? (
          <>
            <motion.img
              initial={{ opacity: 0, scale: 1.06 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              src={src}
              alt={caption || "Ad visual"}
              onClick={() => setOpen(true)}
              className="h-auto w-full cursor-zoom-in object-cover"
            />
            <button
              onClick={() => setOpen(true)}
              aria-label="Maximize image"
              className="absolute right-2 top-2 flex h-9 w-9 items-center justify-center rounded-full bg-black/45 text-white opacity-0 backdrop-blur-sm transition-opacity duration-200 hover:bg-black/65 group-hover:opacity-100"
            >
              {/* expand icon */}
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path
                  d="M9 3H5a2 2 0 0 0-2 2v4m6 10H5a2 2 0 0 1-2-2v-4M15 3h4a2 2 0 0 1 2 2v4m-6 10h4a2 2 0 0 0 2-2v-4"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </>
        ) : (
          <div className="flex h-56 items-center justify-center text-sm text-white/40">
            No image available
          </div>
        )}
      </div>
      {caption && (
        <p className="px-2 py-2 text-center text-xs font-medium text-white/55">
          {caption} · <span className="text-accent-cyan">tap to enlarge</span>
        </p>
      )}

      <Lightbox src={src} open={open} onClose={() => setOpen(false)} caption={caption} />
    </div>
  );
}
