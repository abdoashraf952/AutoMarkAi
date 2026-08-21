"use client";

// Small shared primitives for the analytics tabs, matching the campaign
// module's glass + gold visual language.

import type { ReactNode } from "react";

export const PRIORITY_STYLE: Record<string, { bg: string; fg: string }> = {
  critical: { bg: "rgba(227,73,72,0.18)", fg: "#f08a89" },
  high: { bg: "rgba(217,119,6,0.20)", fg: "#f0b155" },
  medium: { bg: "rgba(201,168,76,0.18)", fg: "#E8C97A" },
  low: { bg: "rgba(255,255,255,0.07)", fg: "rgba(255,255,255,0.55)" },
};

export function priorityStyle(priority?: string | null) {
  return PRIORITY_STYLE[(priority ?? "low").toLowerCase()] ?? PRIORITY_STYLE.low;
}

export function Pill({
  children,
  bg = "rgba(255,255,255,0.07)",
  fg = "rgba(255,255,255,0.55)",
}: {
  children: ReactNode;
  bg?: string;
  fg?: string;
}) {
  return (
    <span
      className="rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest"
      style={{ background: bg, color: fg }}
    >
      {children}
    </span>
  );
}

export function Card({
  children,
  className = "",
  accent,
}: {
  children: ReactNode;
  className?: string;
  accent?: string;
}) {
  return (
    <div
      className={`rounded-2xl p-5 ${className}`}
      style={{
        background: "linear-gradient(160deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.03) 100%)",
        border: "1px solid rgba(255,255,255,0.09)",
        backdropFilter: "blur(20px)",
        ...(accent ? { borderLeft: `3px solid ${accent}` } : {}),
      }}
    >
      {children}
    </div>
  );
}

/** Single headline number — used for row/column counts and quality score. */
export function StatTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div
      className="rounded-2xl px-4 py-3"
      style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}
    >
      <div className="text-[10px] font-semibold uppercase tracking-widest text-white/35">
        {label}
      </div>
      <div className="mt-1 font-serif text-2xl font-bold tabular-nums text-white">{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-white/40">{hint}</div>}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div
      className="rounded-2xl px-6 py-10 text-center text-sm text-white/40"
      style={{ border: "1px dashed rgba(255,255,255,0.12)" }}
    >
      {children}
    </div>
  );
}

export function SectionTitle({ children, sub }: { children: ReactNode; sub?: string }) {
  return (
    <div className="mb-4">
      <h3 className="font-serif text-lg font-bold text-white">{children}</h3>
      {sub && <p className="mt-0.5 text-xs text-white/40">{sub}</p>}
    </div>
  );
}
