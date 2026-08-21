"use client";

import { useMemo, useState } from "react";
import type { KPI } from "@/lib/analytics";
import { Card, EmptyState, Pill, SectionTitle, priorityStyle } from "./ui";

const PRIORITY_ORDER = ["critical", "high", "medium", "low"];

function TrendGlyph({ direction }: { direction?: string | null }) {
  const d = (direction ?? "").toLowerCase();
  if (d === "up") return <span style={{ color: "#34d399" }}>▲</span>;
  if (d === "down") return <span style={{ color: "#f08a89" }}>▼</span>;
  if (d === "stable") return <span className="text-white/40">■</span>;
  return null;
}

function KpiCard({ kpi }: { kpi: KPI }) {
  const [open, setOpen] = useState(false);
  const style = priorityStyle(kpi.priority);

  return (
    <Card accent={style.fg}>
      <div className="mb-2 flex items-start justify-between gap-3">
        <h4 className="text-sm font-bold leading-snug text-white">{kpi.name}</h4>
        <Pill bg={style.bg} fg={style.fg}>{kpi.priority ?? "—"}</Pill>
      </div>

      {kpi.current_value != null && (
        <div className="mb-2 flex items-baseline gap-2">
          <span className="font-serif text-2xl font-bold tabular-nums text-white">
            {kpi.current_value}
          </span>
          {kpi.unit && <span className="text-xs text-white/40">{kpi.unit}</span>}
          <TrendGlyph direction={kpi.trend_direction} />
        </div>
      )}

      <p className="text-[13px] leading-relaxed text-white/60">{kpi.business_definition}</p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {kpi.category && <Pill>{kpi.category}</Pill>}
        <button
          onClick={() => setOpen((v) => !v)}
          className="text-[11px] font-semibold uppercase tracking-wider text-white/40 transition-colors hover:text-white/70"
        >
          {open ? "Less" : "Details"}
        </button>
      </div>

      {open && (
        <div className="mt-3 space-y-3 border-t pt-3" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
          {kpi.why_important && (
            <div>
              <div className="mb-1 text-[10px] font-bold uppercase tracking-widest text-white/35">
                Why it matters
              </div>
              <p className="text-[13px] leading-relaxed text-white/60">{kpi.why_important}</p>
            </div>
          )}
          {kpi.formula && (
            <div>
              <div className="mb-1 text-[10px] font-bold uppercase tracking-widest text-white/35">
                Formula
              </div>
              <code
                className="block rounded-lg px-3 py-2 text-[12px] text-white/75"
                style={{ background: "rgba(0,0,0,0.35)" }}
              >
                {kpi.formula}
              </code>
            </div>
          )}
          {!!kpi.required_columns?.length && (
            <div>
              <div className="mb-1.5 text-[10px] font-bold uppercase tracking-widest text-white/35">
                Required columns
              </div>
              <div className="flex flex-wrap gap-1.5">
                {kpi.required_columns.map((c) => (
                  <span
                    key={c}
                    className="rounded-md px-2 py-0.5 text-[11px] text-white/60"
                    style={{ background: "rgba(255,255,255,0.06)" }}
                  >
                    {c}
                  </span>
                ))}
              </div>
            </div>
          )}
          {kpi.benchmark && (
            <div>
              <div className="mb-1 text-[10px] font-bold uppercase tracking-widest text-white/35">
                Benchmark
              </div>
              <p className="text-[13px] text-white/60">{kpi.benchmark}</p>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export default function KpiTab({ kpis }: { kpis: KPI[] }) {
  const [filter, setFilter] = useState<string>("all");

  const categories = useMemo(
    () => Array.from(new Set(kpis.map((k) => k.category).filter(Boolean))) as string[],
    [kpis]
  );

  const sorted = useMemo(() => {
    const rank = (p?: string) => {
      const i = PRIORITY_ORDER.indexOf((p ?? "low").toLowerCase());
      return i === -1 ? PRIORITY_ORDER.length : i;
    };
    return [...kpis]
      .filter((k) => filter === "all" || k.category === filter)
      .sort((a, b) => rank(a.priority) - rank(b.priority));
  }, [kpis, filter]);

  if (!kpis.length) {
    return <EmptyState>No KPIs were discovered for this dataset.</EmptyState>;
  }

  return (
    <div>
      <SectionTitle sub={`${kpis.length} KPIs discovered, highest priority first`}>
        Key Performance Indicators
      </SectionTitle>

      {/* Filters sit in one row above the content */}
      {categories.length > 1 && (
        <div className="mb-5 flex flex-wrap gap-2">
          {["all", ...categories].map((c) => (
            <button
              key={c}
              onClick={() => setFilter(c)}
              className="rounded-full px-3 py-1.5 text-[11px] font-semibold transition-colors"
              style={
                filter === c
                  ? { background: "rgba(201,168,76,0.20)", color: "#E8C97A" }
                  : { background: "rgba(255,255,255,0.05)", color: "rgba(255,255,255,0.45)" }
              }
            >
              {c === "all" ? "All" : c}
            </button>
          ))}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {sorted.map((kpi) => (
          <KpiCard key={kpi.id} kpi={kpi} />
        ))}
      </div>
    </div>
  );
}
