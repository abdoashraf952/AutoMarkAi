"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";

/** Full-screen image viewer. Click backdrop / ✕ / Esc to collapse. */
export default function Lightbox({
  src,
  open,
  onClose,
  caption,
}: {
  src: string;
  open: boolean;
  onClose: () => void;
  caption?: string;
}) {
  // The lightbox lives inside message bubbles that Framer Motion animates with
  // a CSS `transform`. A transformed ancestor becomes the containing block for
  // `position: fixed`, which would trap this overlay inside the bubble instead
  // of covering the viewport. Rendering through a portal to <body> escapes that
  // ancestor so the modal is truly full-screen.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    // lock background scroll
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!mounted) return null;

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/80 p-4 backdrop-blur-md"
        >
          <button
            onClick={onClose}
            aria-label="Close"
            className="absolute right-5 top-5 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-xl text-white transition hover:bg-white/20"
          >
            ✕
          </button>
          <motion.div
            initial={{ scale: 0.85, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.85, opacity: 0 }}
            transition={{ type: "spring", stiffness: 240, damping: 26 }}
            onClick={(e) => e.stopPropagation()}
            className="flex items-center justify-center"
            style={{ width: "min(94vw, 900px)", height: "min(84vh, 760px)" }}
          >
            {/* object-contain on a full-size box scales the image up to fill
                the popup while preserving aspect ratio */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={src}
              alt={caption || "Preview"}
              className="h-full w-full rounded-2xl object-contain shadow-card"
            />
          </motion.div>
          {caption && (
            <p className="mt-4 text-sm text-white/70">{caption}</p>
          )}
          <p className="mt-1 text-xs text-white/35">Click anywhere or press Esc to close</p>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
}
