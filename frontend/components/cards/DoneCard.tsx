"use client";

import { useState } from "react";
import type { CampaignBundle } from "@/lib/types";
import AdPreview from "./AdPreview";

/** Final campaign summary: key metrics, ad preview, and expandable details. */
export default function DoneCard({
  bundle,
  image,
}: {
  bundle: CampaignBundle;
  image: string;
}) {
  const [showDetails, setShowDetails] = useState(false);
  const product = bundle.product || {};
  const campaign = bundle.campaign || {};
  const media = bundle.media || {};
  const audience = media.audience || {};

  return (
    <div className="glass w-full max-w-lg space-y-5 rounded-3xl p-5 shadow-card">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Product" value={product.type || "—"} />
        <Metric label="Platform" value={cap(campaign.platform)} />
        <Metric label="Objective" value={campaign.objective || "—"} />
        <Metric label="Daily budget" value={`$${(media.daily_budget_usd || 0).toFixed(0)}`} />
      </div>

      <AdPreview bundle={bundle} image={image} />

      <StrategyPanel strategy={bundle.strategy} />

      <button
        onClick={() => setShowDetails((s) => !s)}
        className="text-xs font-semibold text-accent-cyan hover:underline"
      >
        {showDetails ? "Hide" : "Show"} media-buying details
      </button>

      {showDetails && (
        <div className="space-y-1.5 rounded-2xl bg-black/20 p-4 text-sm text-white/75">
          <Row label="Age range" value={`${audience.age_min ?? "—"}–${audience.age_max ?? "—"}`} />
          <Row label="Interests" value={(audience.interests || []).join(", ") || "—"} />
          <Row label="Locations" value={(audience.locations || []).join(", ") || "—"} />
          <Row label="Bid strategy" value={media.bid_strategy || "—"} />
          <Row
            label="Estimated reach"
            value={
              media.estimated_reach
                ? `${fmt(media.estimated_reach.min)}–${fmt(media.estimated_reach.max)}`
                : "—"
            }
          />
          {media.budget_split && (
            <Row
              label="Budget split"
              value={Object.entries(media.budget_split)
                .map(([k, v]) => `${cap(k)} ${Math.round(v * 100)}%`)
                .join(" · ")}
            />
          )}
        </div>
      )}
    </div>
  );
}

function StrategyPanel({ strategy }: { strategy?: CampaignBundle["strategy"] }) {
  if (!strategy) return null;
  const persona = strategy.target_persona || {};
  const channels = strategy.channels || {};
  const windows = strategy.schedule?.peak_windows || [];
  const angles = strategy.messaging_angles || [];

  const hasContent =
    persona.primary_segment || windows.length > 0 || (channels.primary || []).length > 0;
  if (!hasContent) return null;

  const gender = persona.gender && persona.gender !== "all" ? `${persona.gender}, ` : "";
  const ageRange =
    persona.age_min || persona.age_max ? `${persona.age_min ?? "—"}–${persona.age_max ?? "—"}` : "";

  return (
    <div className="space-y-3 rounded-2xl border border-accent-violet/25 bg-accent-violet/5 p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-white">
        <span>🎯</span> Marketing strategy
      </div>

      {persona.primary_segment && (
        <Row
          label="Audience"
          value={`${persona.primary_segment}${gender || ageRange ? ` (${gender}${ageRange})` : ""}`}
        />
      )}
      {(channels.primary || []).length > 0 && (
        <Row label="Channels" value={(channels.primary || []).map(cap).join(" · ")} />
      )}

      {windows.length > 0 && (
        <div>
          <div className="mb-1 text-xs font-medium text-white/55">
            Best posting times{strategy.timezone ? ` · ${strategy.timezone}` : ""}
          </div>
          <div className="space-y-1">
            {windows.map((w, i) => (
              <div key={i} className="flex items-center gap-2 text-sm text-white/85">
                <span className="rounded-md bg-white/10 px-2 py-0.5 text-[11px] text-accent-cyan">
                  {(w.days || []).join(" ")}
                </span>
                <span className="font-medium">
                  {w.start}–{w.end}
                </span>
                {w.label && <span className="text-white/50">· {w.label}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {angles.length > 0 && (
        <Row label="Angles" value={angles.join(" · ")} />
      )}

      {strategy.schedule?.note && (
        <p className="text-[11px] italic text-white/35">{strategy.schedule.note}</p>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-white/5 p-3">
      <div className="text-[10px] uppercase tracking-wider text-white/40">{label}</div>
      <div className="mt-0.5 truncate text-sm font-semibold text-white" title={value}>
        {value}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="min-w-[110px] text-white/45">{label}:</span>
      <span className="flex-1">{value}</span>
    </div>
  );
}

const cap = (s?: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : "—");
const fmt = (n?: number) => (typeof n === "number" ? n.toLocaleString() : "—");
