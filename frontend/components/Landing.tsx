"use client";

import { motion } from "framer-motion";

/** Homepage / hero. Entry point and the destination after "End". */
export default function Landing({ onStart }: { onStart: () => void }) {
  return (
    <main className="flex h-[100dvh] flex-col items-center justify-center px-6 text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.9, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 200, damping: 22 }}
        className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-accent-violet to-accent-cyan text-4xl shadow-glow"
      >
        ✦
      </motion.div>

      <motion.h1
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="max-w-2xl text-4xl font-bold leading-tight sm:text-5xl"
      >
        Your real estate ad, <span className="accent-gradient-text">ready to go</span> — just
        upload photos and answer a few questions.
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="mt-5 max-w-xl text-base text-white/60"
      >
        Meet <span className="font-semibold text-white">Mark</span>, your real estate campaign
        assistant. Upload your unit photos, share your compound details, and Mark builds a
        professional Meta ad campaign for you — in plain language, no marketing experience needed.
      </motion.p>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="mt-7 flex flex-wrap items-center justify-center gap-2"
      >
        {["🏗️ Built for real estate", "📸 Your actual unit photos", "✍️ Ad copy that converts", "🚀 Publish to Meta in one tap"].map((c) => (
          <span key={c} className="chip">
            {c}
          </span>
        ))}
      </motion.div>

      <motion.button
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        whileHover={{ scale: 1.03 }}
        whileTap={{ scale: 0.97 }}
        onClick={onStart}
        className="btn-primary mt-9 px-8 py-4 text-base"
      >
        Create my real estate campaign →
      </motion.button>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.55 }}
        className="mt-4 text-xs text-white/40"
      >
        Takes about 2 minutes · Nothing goes live until you say so
      </motion.p>
    </main>
  );
}
