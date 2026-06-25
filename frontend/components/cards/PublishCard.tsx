"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import type { PublishResult } from "@/lib/types";

/** Renders the Meta publish outcome — sponsored ad IDs + organic post. */
export default function PublishCard({
  result,
  error,
  sim,
}: {
  result: PublishResult | null;
  error: string | null;
  sim: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      className="glass w-full max-w-lg space-y-4 rounded-3xl p-5 shadow-card"
    >
      <div className="flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent-lime/20 text-accent-lime">
          ✓
        </span>
        <h3 className="text-sm font-semibold text-white">
          Published{sim ? " (demo mode)" : " to Meta"}
        </h3>
      </div>

      {result?.campaign && (
        <Block title="📢 Sponsored ad (paused)">
          <IdRow label="Campaign" id={result.campaign.id} extra={result.campaign.status} />
          {result.ad_set && <IdRow label="Ad set" id={result.ad_set.id} />}
          {result.creative && <IdRow label="Creative" id={result.creative.id} />}
          {result.ad && <IdRow label="Ad" id={result.ad.id} extra={result.ad.status} />}
        </Block>
      )}

      {result?.post && (
        <Block title="📝 Organic page post">
          <IdRow label="Post" id={result.post.id} />
          {result.post.created_time && (
            <IdRow label="Created" id={result.post.created_time} mono={false} />
          )}
        </Block>
      )}

      {error && (
        <div className="rounded-2xl bg-red-500/10 p-3 text-xs text-red-300">{error}</div>
      )}
    </motion.div>
  );
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl bg-white/5 p-4">
      <h4 className="mb-2 text-xs font-semibold text-white/70">{title}</h4>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function IdRow({
  label,
  id,
  extra,
  mono = true,
}: {
  label: string;
  id: string;
  extra?: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-2 text-xs">
      <span className="text-white/45">{label}</span>
      <span className="flex items-center gap-2">
        <span className={mono ? "font-mono text-white/80" : "text-white/80"}>{id}</span>
        {extra && (
          <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] text-white/60">
            {extra}
          </span>
        )}
      </span>
    </div>
  );
}
