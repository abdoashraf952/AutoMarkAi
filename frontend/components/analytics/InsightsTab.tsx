"use client";

import { useMemo, useState } from "react";
import type { Insight } from "@/lib/analytics";
import { Card, EmptyState, Pill, SectionTitle, priorityStyle } from "./ui";

const PRIORITY_ORDER = ["critical", "high", "medium", "low"];

const TYPE_STYLE: Record<string, { bg: string; fg: string }> = {
  trend: { bg: "rgba(57,135,229,0.18)", fg: "#7fb2ee" },
  opportunity: { bg: "rgba(25,158,112,0.20)", fg: "#4fc79b" },
  risk: { bg: "rgba(227,73,72,0.18)", fg: "#f08a89" },
  performance: { bg: "rgba(201,168,76,0.18)", fg: "#E8C97A" },
  anomaly: { bg: "rgba(217,89,38,0.20)", fg: "#ef9166" },
  benchmark: { bg: "rgba(144,133,233,0.20)", fg: "#b3aaf2" },
};

function typeStyle(t?: string | null) {
  return TYPE_STYLE[(t ?? "").toLowerCase()] ?? { bg: "rgba(255,255,255,0.07)", fg: "rgba(255,255,255,0.55)" };
}

function InsightCard({ insight }: { insight: Insight }) {
  const [open, setOpen] = useState(false);
  const p = priorityStyle(insight.priority);
  const t = typeStyle(insight.type);

  return (
    <Card accent={p.fg}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Pill bg={t.bg} fg={t.fg}>{insight.type ?? "insight"}</Pill>
        <Pill bg={p.bg} fg={p.fg}>{insight.priority ?? "—"}</Pill>
        {insight.confidence && <Pill>{insight.confidence} confidence</Pill>}
      </div>

      <h4 className="mb-2 font-serif text-base font-bold leading-snug text-white">
        {insight.title}
      </h4>

      <p className="text-[13px] leading-relaxed text-white/70">{insight.executive_summary}</p>

      <button
        onClick={() => setOpen((v) => !v)}
        className="mt-3 text-[11px] font-semibold uppercase tracking-wider text-white/40 transition-colors hover:text-white/70"
      >
        {open ? "Collapse" : "Full analysis"}
      </button>

      {open && (
        <div className="mt-3 space-y-4 border-t pt-3" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
          {insight.detailed_analysis && (
            <p className="whitespace-pre-line text-[13px] leading-relaxed text-white/60">
              {insight.detailed_analysis}
            </p>
          )}

          {!!insight.evidence?.length && (
            <div>
              <div className="mb-1.5 text-[10px] font-bold uppercase tracking-widest text-white/35">
                Evidence
              </div>
              <ul className="space-y-1.5">
                {insight.evidence.map((e, i) => (
                  <li key={i} className="flex gap-2 text-[13px] text-white/60">
                    <span className="text-white/25">•</span>
                    <span>{e}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {insight.recommendation && (
            <div
              className="rounded-xl px-3 py-2.5"
              style={{ background: "rgba(201,168,76,0.10)", border: "1px solid rgba(201,168,76,0.25)" }}
            >
              <div className="mb-1 text-[10px] font-bold uppercase tracking-widest" style={{ color: "#E8C97A" }}>
                Recommendation
              </div>
              <p className="text-[13px] leading-relaxed text-white/75">{insight.recommendation}</p>
            </div>
          )}

          {insight.business_impact && (
            <div>
              <div className="mb-1 text-[10px] font-bold uppercase tracking-widest text-white/35">
                Business impact
              </div>
              <p className="text-[13px] text-white/60">{insight.business_impact}</p>
            </div>
          )}

          {!!insight.affected_kpis?.length && (
            <div className="flex flex-wrap gap-1.5">
              {insight.affected_kpis.map((k) => (
                <span
                  key={k}
                  className="rounded-md px-2 py-0.5 text-[11px] text-white/60"
                  style={{ background: "rgba(255,255,255,0.06)" }}
                >
                  {k}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export default function InsightsTab({ insights }: { insights: Insight[] }) {
  const [filter, setFilter] = useState("all");

  const types = useMemo(
    () => Array.from(new Set(insights.map((i) => i.type).filter(Boolean))) as string[],
    [insights]
  );

  const sorted = useMemo(() => {
    const rank = (p?: string) => {
      const i = PRIORITY_ORDER.indexOf((p ?? "low").toLowerCase());
      return i === -1 ? PRIORITY_ORDER.length : i;
    };
    return [...insights]
      .filter((i) => filter === "all" || i.type === filter)
      .sort((a, b) => rank(a.priority) - rank(b.priority));
  }, [insights, filter]);

  if (!insights.length) {
    return <EmptyState>No insights were generated for this dataset.</EmptyState>;
  }

  return (
    <div>
      <SectionTitle sub={`${insights.length} insights, most critical first`}>
        Business Insights
      </SectionTitle>

      {types.length > 1 && (
        <div className="mb-5 flex flex-wrap gap-2">
          {["all", ...types].map((t) => (
            <button
              key={t}
              onClick={() => setFilter(t)}
              className="rounded-full px-3 py-1.5 text-[11px] font-semibold capitalize transition-colors"
              style={
                filter === t
                  ? { background: "rgba(201,168,76,0.20)", color: "#E8C97A" }
                  : { background: "rgba(255,255,255,0.05)", color: "rgba(255,255,255,0.45)" }
              }
            >
              {t === "all" ? "All" : t}
            </button>
          ))}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {sorted.map((insight) => (
          <InsightCard key={insight.id} insight={insight} />
        ))}
      </div>
    </div>
  );
}
