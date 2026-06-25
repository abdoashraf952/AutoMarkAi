"use client";

import { motion } from "framer-motion";
import type { LoaderKind } from "@/hooks/useCampaignChat";

/**
 * Artistic, stage-specific loaders shown while the backend works.
 * Each kind has its own bespoke animation so a wait never feels generic.
 */
export default function LoadingArt({
  kind,
  caption,
}: {
  kind: LoaderKind;
  caption: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="glass-strong mx-auto flex w-full max-w-md flex-col items-center gap-5 rounded-3xl px-8 py-9 shadow-card"
    >
      <Animation kind={kind} />
      <motion.p
        key={caption}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center text-sm font-medium text-white/80"
      >
        {caption}
      </motion.p>
      <DotPulse />
    </motion.div>
  );
}

function DotPulse() {
  return (
    <div className="flex items-center gap-1.5">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-accent-violet"
          animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.2, 0.8] }}
          transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.18 }}
        />
      ))}
    </div>
  );
}

function Animation({ kind }: { kind: LoaderKind }) {
  switch (kind) {
    case "analyze":
      return <AnalyzeArt />;
    case "build":
      return <BuildArt />;
    case "image":
      return <ImageArt />;
    case "publish":
      return <PublishArt />;
  }
}

/* ---- Analyze: a scanning lens orbiting a product dot ---------------- */
function AnalyzeArt() {
  return (
    <div className="relative h-28 w-28">
      <div className="absolute inset-0 animate-spin-slow rounded-full border border-dashed border-accent-violet/40" />
      <motion.div
        className="absolute inset-3 rounded-full border-2 border-accent-cyan/50"
        animate={{ rotate: -360 }}
        transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
      >
        <div className="absolute -top-1 left-1/2 h-2 w-2 -translate-x-1/2 rounded-full bg-accent-cyan shadow-glow-cyan" />
      </motion.div>
      <motion.div
        className="absolute inset-0 flex items-center justify-center text-2xl"
        animate={{ scale: [1, 1.12, 1] }}
        transition={{ duration: 1.6, repeat: Infinity }}
      >
        🔎
      </motion.div>
      <div className="absolute inset-0 -z-10 rounded-full bg-accent-violet/20 blur-2xl" />
    </div>
  );
}

/* ---- Build: stacking bars assembling a plan ------------------------- */
function BuildArt() {
  const bars = [0, 1, 2, 3];
  return (
    <div className="flex h-28 items-end gap-2">
      {bars.map((i) => (
        <motion.div
          key={i}
          className="w-4 rounded-t-md bg-gradient-to-t from-accent-violet to-accent-cyan"
          animate={{ height: ["20%", "100%", "45%", "80%", "30%"] }}
          transition={{ duration: 2.2, repeat: Infinity, delay: i * 0.15, ease: "easeInOut" }}
          style={{ height: "30%" }}
        />
      ))}
    </div>
  );
}

/* ---- Image: a paint-swirl morphing canvas --------------------------- */
function ImageArt() {
  return (
    <div className="relative h-28 w-28">
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="absolute inset-0 rounded-[40%] mix-blend-screen blur-md"
          style={{
            background:
              i === 0
                ? "radial-gradient(circle, #7c5cff, transparent 70%)"
                : i === 1
                ? "radial-gradient(circle, #22d3ee, transparent 70%)"
                : "radial-gradient(circle, #ff5cc8, transparent 70%)",
          }}
          animate={{ rotate: [0, 360], borderRadius: ["40%", "55%", "40%"] }}
          transition={{ duration: 5 + i, repeat: Infinity, ease: "linear" }}
        />
      ))}
      <div className="absolute inset-0 flex items-center justify-center text-2xl">🎨</div>
    </div>
  );
}

/* ---- Publish: a rocket riding pulse rings --------------------------- */
function PublishArt() {
  return (
    <div className="relative flex h-28 w-28 items-center justify-center">
      {[0, 1].map((i) => (
        <span
          key={i}
          className="absolute h-12 w-12 rounded-full border border-accent-cyan/60 animate-pulse-ring"
          style={{ animationDelay: `${i * 0.9}s` }}
        />
      ))}
      <motion.div
        className="text-3xl"
        animate={{ y: [4, -6, 4], rotate: [0, 4, -4, 0] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
      >
        🚀
      </motion.div>
    </div>
  );
}
