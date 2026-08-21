"use client";

import { motion } from "framer-motion";
import type { AuthUser } from "@/hooks/useAuth";

/* ── Shared building SVG icon ──────────────────────────────────────── */
export function BuildingIcon({ size = 36 }: { size?: number }) {
  const s = size / 36;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 36 36"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Left building */}
      <rect x={1 * s} y={14 * s} width={14 * s} height={22 * s} rx={1 * s} fill="white" fillOpacity="0.95" />
      <rect x={4 * s} y={17 * s} width={3 * s} height={3 * s} rx={0.5 * s} fill="#C9A84C" fillOpacity="0.85" />
      <rect x={9 * s} y={17 * s} width={3 * s} height={3 * s} rx={0.5 * s} fill="#C9A84C" fillOpacity="0.85" />
      <rect x={4 * s} y={23 * s} width={3 * s} height={3 * s} rx={0.5 * s} fill="#C9A84C" fillOpacity="0.6" />
      <rect x={9 * s} y={23 * s} width={3 * s} height={3 * s} rx={0.5 * s} fill="#C9A84C" fillOpacity="0.6" />
      <rect x={4 * s} y={29 * s} width={3 * s} height={3 * s} rx={0.5 * s} fill="#C9A84C" fillOpacity="0.35" />
      <rect x={9 * s} y={29 * s} width={3 * s} height={3 * s} rx={0.5 * s} fill="#C9A84C" fillOpacity="0.35" />
      {/* Right taller building */}
      <rect x={19 * s} y={5 * s} width={16 * s} height={31 * s} rx={1 * s} fill="white" />
      <rect x={22 * s} y={8 * s}  width={3.5 * s} height={3.5 * s} rx={0.5 * s} fill="#D97706" fillOpacity="0.85" />
      <rect x={28 * s} y={8 * s}  width={3.5 * s} height={3.5 * s} rx={0.5 * s} fill="#D97706" fillOpacity="0.85" />
      <rect x={22 * s} y={15 * s} width={3.5 * s} height={3.5 * s} rx={0.5 * s} fill="#D97706" fillOpacity="0.85" />
      <rect x={28 * s} y={15 * s} width={3.5 * s} height={3.5 * s} rx={0.5 * s} fill="#D97706" fillOpacity="0.85" />
      <rect x={22 * s} y={22 * s} width={3.5 * s} height={3.5 * s} rx={0.5 * s} fill="#D97706" fillOpacity="0.6" />
      <rect x={28 * s} y={22 * s} width={3.5 * s} height={3.5 * s} rx={0.5 * s} fill="#D97706" fillOpacity="0.6" />
      <rect x={22 * s} y={29 * s} width={3.5 * s} height={3.5 * s} rx={0.5 * s} fill="#D97706" fillOpacity="0.35" />
      <rect x={28 * s} y={29 * s} width={3.5 * s} height={3.5 * s} rx={0.5 * s} fill="#D97706" fillOpacity="0.35" />
      {/* Antenna */}
      <rect x={26 * s} y={1 * s} width={2 * s} height={5 * s} rx={1 * s} fill="white" fillOpacity="0.7" />
    </svg>
  );
}

/* ── Feature chips ──────────────────────────────────────────────────── */
const FEATURES = [
  { icon: "🏢", label: "Built for real estate" },
  { icon: "📸", label: "Your actual unit photos" },
  { icon: "✍️", label: "Ad copy that converts" },
  { icon: "🚀", label: "Live on Meta in one tap" },
];

/* ── Floating ambient property cards (desktop only) ────────────────── */
function FloatingCard({
  children,
  className,
  floatDuration,
  floatDelay,
  entryDelay,
  rotate,
}: {
  children: React.ReactNode;
  className: string;
  floatDuration: number;
  floatDelay: number;
  entryDelay: number;
  rotate: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: entryDelay, duration: 0.7, ease: "easeOut" }}
      className={`pointer-events-none absolute hidden select-none xl:block ${className}`}
      style={{ transform: rotate }}
    >
      <motion.div
        animate={{ y: [0, -10, 0] }}
        transition={{
          duration: floatDuration,
          repeat: Infinity,
          ease: "easeInOut",
          delay: floatDelay,
        }}
        className="glass rounded-2xl"
        style={{ border: "1px solid rgba(201,168,76,0.18)" }}
      >
        {children}
      </motion.div>
    </motion.div>
  );
}

/* ── Main component ─────────────────────────────────────────────────── */
export default function Landing({
  onStart,
  user,
  onMyCampaigns,
  onAnalytics,
  onLogout,
}: {
  onStart:       () => void;
  user?:         AuthUser | null;
  onMyCampaigns?: () => void;
  onAnalytics?:  () => void;
  onLogout?:     () => void;
}) {
  return (
    <main className="relative flex h-[100dvh] flex-col items-center justify-center overflow-hidden px-6 text-center">

      {/* ── Top nav (only when logged in) ─── */}
      {user && (
        <div className="absolute left-0 right-0 top-0 z-20 flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-xl"
              style={{ background: "linear-gradient(135deg, #B8860B 0%, #C9A84C 50%, #D97706 100%)" }}
            >
              <BuildingIcon size={16} />
            </div>
            <span className="text-xs font-semibold text-white/60">{user.email}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onMyCampaigns}
              className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3.5 py-1.5 text-xs font-semibold text-white/75 transition hover:bg-white/10 hover:text-white"
              style={{ transition: "all 0.2s" }}
            >
              📋 My Campaigns
            </button>
            <button
              onClick={onAnalytics}
              className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3.5 py-1.5 text-xs font-semibold text-white/75 transition hover:bg-white/10 hover:text-white"
              style={{ transition: "all 0.2s" }}
            >
              📊 Analytics
            </button>
            <button
              onClick={onLogout}
              className="rounded-xl border border-white/8 bg-white/4 px-3.5 py-1.5 text-xs text-white/40 transition hover:text-white/70"
            >
              Sign out
            </button>
          </div>
        </div>
      )}

      {/* ── Left floating card: property listing ── */}
      <FloatingCard
        className="left-[3%] top-[26%] w-56"
        rotate="rotate(-4deg)"
        floatDuration={5.5}
        floatDelay={0.8}
        entryDelay={0.9}
      >
        <div className="p-4">
          <div
            className="mb-3 flex h-24 w-full items-center justify-center overflow-hidden rounded-xl"
            style={{
              background:
                "linear-gradient(135deg, rgba(201,168,76,0.18) 0%, rgba(146,64,14,0.12) 100%)",
            }}
          >
            <span className="text-4xl">🏢</span>
          </div>
          <p className="text-left text-xs font-semibold text-white">Palm Hills Compound</p>
          <p className="text-left text-[10px]" style={{ color: "#E8C97A" }}>
            3BR Villa · October, Egypt
          </p>
          <div className="mt-2 flex items-center justify-between">
            <span className="text-[10px] text-white/40">Starting at</span>
            <span className="text-xs font-bold" style={{ color: "#C9A84C" }}>
              EGP 5.2M
            </span>
          </div>
          <div
            className="mt-2 rounded-full px-2 py-0.5 text-center text-[9px] font-semibold"
            style={{ background: "rgba(201,168,76,0.14)", color: "#E8C97A" }}
          >
            ✓ Ad campaign live
          </div>
        </div>
      </FloatingCard>

      {/* ── Right floating card: campaign reach stats ── */}
      <FloatingCard
        className="right-[3%] top-[18%] w-52"
        rotate="rotate(3deg)"
        floatDuration={6.2}
        floatDelay={0.3}
        entryDelay={1.1}
      >
        <div className="p-4">
          <div className="mb-3 flex items-center gap-2">
            <div
              className="flex h-7 w-7 items-center justify-center rounded-lg text-sm"
              style={{ background: "rgba(201,168,76,0.18)" }}
            >
              📊
            </div>
            <div className="text-left">
              <p className="text-xs font-semibold text-white">Campaign Live</p>
              <p className="text-[10px] text-white/40">Lake View Towers</p>
            </div>
          </div>
          <p className="text-left text-[10px] text-white/45">Reach this week</p>
          <p className="text-left text-2xl font-bold" style={{ color: "#E8C97A" }}>
            12,400
          </p>
          <div className="mt-2 h-1.5 w-full rounded-full bg-white/8">
            <motion.div
              className="h-full rounded-full"
              style={{ background: "linear-gradient(90deg, #C9A84C, #E8C97A)" }}
              initial={{ width: "0%" }}
              animate={{ width: "78%" }}
              transition={{ delay: 2.2, duration: 1.4, ease: "easeOut" }}
            />
          </div>
          <p className="mt-1 text-right text-[9px]" style={{ color: "#C9A84C" }}>
            78% of weekly target
          </p>
        </div>
      </FloatingCard>

      {/* ── Bottom-right floating card: best CPL stat ── */}
      <FloatingCard
        className="bottom-[22%] right-[5%] w-44"
        rotate="rotate(-2deg)"
        floatDuration={4.8}
        floatDelay={1.4}
        entryDelay={1.3}
      >
        <div className="p-3.5">
          <div className="flex items-center gap-2">
            <span className="text-base">🏆</span>
            <p className="text-xs font-semibold text-white">Top Campaign</p>
          </div>
          <p className="mt-2 text-left text-[10px] text-white/45">Cost per lead achieved</p>
          <p className="text-left text-xl font-bold" style={{ color: "#C9A84C" }}>
            $0.83
          </p>
          <p className="text-left text-[9px] text-white/30">Villa compound · Sept 2024</p>
        </div>
      </FloatingCard>

      {/* ── Main hero content ─────────────────────────────────────────── */}
      <div className="relative z-10 flex max-w-2xl flex-col items-center">

        {/* Platform label */}
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0, duration: 0.6 }}
          className="mb-5 flex items-center gap-3"
        >
          <span
            className="h-px w-8"
            style={{ background: "linear-gradient(90deg, transparent, #C9A84C)" }}
          />
          <span
            className="text-[11px] font-semibold uppercase tracking-[0.22em]"
            style={{ color: "#C9A84C" }}
          >
            Real Estate AI Platform
          </span>
          <span
            className="h-px w-8"
            style={{ background: "linear-gradient(90deg, #C9A84C, transparent)" }}
          />
        </motion.div>

        {/* Brand icon */}
        <motion.div
          initial={{ opacity: 0, scale: 0.88, y: 14 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 200, damping: 22, delay: 0.07 }}
          className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl shadow-glow"
          style={{
            background: "linear-gradient(135deg, #B8860B 0%, #C9A84C 35%, #E8C97A 65%, #D97706 100%)",
          }}
        >
          <BuildingIcon size={36} />
        </motion.div>

        {/* Headline — serif for luxury feel */}
        <motion.h1
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="max-w-2xl font-serif text-4xl font-bold leading-tight sm:text-5xl"
        >
          Your real estate ad,{" "}
          <span className="accent-gradient-text">ready to launch</span>
          {" "}— in under 2 minutes.
        </motion.h1>

        {/* Sub-headline */}
        <motion.p
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="mt-5 max-w-xl text-base leading-relaxed text-white/60"
        >
          Meet{" "}
          <span className="font-semibold text-white">Mark</span>, your real estate campaign
          partner. Upload your unit photos, share your compound details, and Mark builds a
          professional Meta ad campaign for you — no marketing experience needed.
        </motion.p>

        {/* Feature chips */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="mt-7 flex flex-wrap items-center justify-center gap-2"
        >
          {FEATURES.map((f) => (
            <span key={f.label} className="chip">
              {f.icon} {f.label}
            </span>
          ))}
        </motion.div>

        {/* CTA button */}
        <motion.button
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45 }}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={onStart}
          className="btn-primary mt-9 px-8 py-4 text-base font-bold"
        >
          Create my real estate campaign →
        </motion.button>

        {/* Trust line */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.58 }}
          className="mt-3.5 text-xs text-white/35"
        >
          Takes about 2 minutes · Nothing goes live until you approve it
        </motion.p>

        {/* Stats row */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.68 }}
          className="mt-7 flex items-center gap-1"
        >
          {[
            { num: "Meta", label: "Real live campaigns" },
            { num: "2 min", label: "Average setup time" },
            { num: "Zero", label: "Marketing skills needed" },
          ].map((s, i) => (
            <div key={i} className="flex items-center">
              <div className="flex flex-col items-center gap-0.5 px-5">
                <span className="text-sm font-bold" style={{ color: "#E8C97A" }}>
                  {s.num}
                </span>
                <span className="text-[10px] text-white/35">{s.label}</span>
              </div>
              {i < 2 && (
                <span
                  className="h-6 w-px"
                  style={{ background: "rgba(201,168,76,0.2)" }}
                />
              )}
            </div>
          ))}
        </motion.div>

      </div>
    </main>
  );
}
