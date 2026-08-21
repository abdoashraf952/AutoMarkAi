"use client";

import { useEffect, useState } from "react";
import { getCharts } from "@/lib/analytics";
import type { ChartSpecPayload, VizRecommendation } from "@/lib/analytics";
import { ChartCard } from "./charts";
import { Card, EmptyState, SectionTitle } from "./ui";

export default function VizTab({
  sessionId,
  recommendations,
}: {
  sessionId: string;
  recommendations: VizRecommendation[];
}) {
  const [charts, setCharts] = useState<ChartSpecPayload[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCharts(sessionId)
      .then((r) => !cancelled && setCharts(r.charts))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  if (!recommendations.length) {
    return <EmptyState>No visualization recommendations were generated.</EmptyState>;
  }

  return (
    <div className="space-y-6">
      <div>
        <SectionTitle sub="Rendered from your data, aggregated server-side">
          Live Previews
        </SectionTitle>

        {error && (
          <div
            className="rounded-xl px-4 py-3 text-sm text-white/70"
            style={{ background: "rgba(227,73,72,0.12)", border: "1px solid rgba(227,73,72,0.3)" }}
          >
            Could not build chart previews: {error}
          </div>
        )}

        {!charts && !error && (
          <div className="text-sm text-white/40">Building previews…</div>
        )}

        {charts && charts.length === 0 && (
          <EmptyState>
            None of the recommended charts could be plotted against this dataset.
          </EmptyState>
        )}

        {!!charts?.length && (
          <div className="grid gap-4 xl:grid-cols-2">
            {charts.map((spec, i) => (
              <ChartCard key={i} spec={spec} />
            ))}
          </div>
        )}
      </div>

      {/* The full recommendation list, including ones with no preview */}
      <Card>
        <SectionTitle sub={`${recommendations.length} AI-recommended charts`}>
          Recommendations
        </SectionTitle>
        <div className="overflow-x-auto rounded-xl" style={{ border: "1px solid rgba(255,255,255,0.07)" }}>
          <table className="w-full min-w-[640px] text-left text-[12px]">
            <thead style={{ background: "rgba(255,255,255,0.05)" }}>
              <tr className="text-white/50">
                <th className="px-3 py-2 font-semibold">Title</th>
                <th className="px-3 py-2 font-semibold">Chart</th>
                <th className="px-3 py-2 font-semibold">X</th>
                <th className="px-3 py-2 font-semibold">Y</th>
                <th className="px-3 py-2 font-semibold">Aggregation</th>
                <th className="px-3 py-2 font-semibold">Purpose</th>
              </tr>
            </thead>
            <tbody>
              {recommendations.map((v, i) => (
                <tr key={i} style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                  <td className="px-3 py-2 font-medium text-white/80">{v.title ?? "—"}</td>
                  <td className="px-3 py-2 capitalize text-white/55">{v.chart_type ?? "—"}</td>
                  <td className="px-3 py-2 text-white/55">{v.x_axis ?? "—"}</td>
                  <td className="px-3 py-2 text-white/55">{v.y_axis ?? "—"}</td>
                  <td className="px-3 py-2 text-white/55">{v.aggregation ?? "—"}</td>
                  <td className="px-3 py-2 text-white/45">{v.business_purpose ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
