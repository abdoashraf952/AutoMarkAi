"use client";

import type { AnalysisResult } from "@/lib/analytics";
import { Card, EmptyState, SectionTitle, StatTile } from "./ui";

export default function OverviewTab({ result }: { result: AnalysisResult }) {
  const profile = result.profiling_result;
  const summary = result.dataset_summary ?? profile?.dataset_summary ?? null;

  if (!profile && !summary) {
    return <EmptyState>No profiling data was produced for this dataset.</EmptyState>;
  }

  return (
    <div className="space-y-6">
      {/* Headline numbers — a KPI row, not a chart */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Rows" value={(summary?.row_count ?? 0).toLocaleString()} />
        <StatTile label="Columns" value={String(summary?.column_count ?? 0)} />
        <StatTile
          label="Quality"
          value={profile ? `${profile.data_quality_score.toFixed(0)}%` : "—"}
          hint={profile ? `${profile.total_missing_pct.toFixed(1)}% missing` : undefined}
        />
        <StatTile
          label="Duplicates"
          value={profile ? profile.duplicate_row_count.toLocaleString() : "—"}
          hint={summary ? `${summary.memory_usage_mb.toFixed(1)} MB` : undefined}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-[3fr_2fr]">
        {/* Narrative */}
        <Card>
          <SectionTitle sub="How the profiler read your data">
            Data Profiling Narrative
          </SectionTitle>
          <p className="whitespace-pre-line text-sm leading-relaxed text-white/70">
            {profile?.profiling_narrative || "No narrative was generated."}
          </p>

          {!!profile?.quality_issues?.length && (
            <div className="mt-5">
              <h4 className="mb-2 text-xs font-bold uppercase tracking-widest text-white/40">
                Quality Issues
              </h4>
              <ul className="space-y-2">
                {profile.quality_issues.map((issue, i) => (
                  <li
                    key={i}
                    className="rounded-r-lg px-3 py-2 text-[13px] text-white/70"
                    style={{
                      background: "rgba(227,73,72,0.10)",
                      borderLeft: "3px solid #e34948",
                    }}
                  >
                    {issue}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        {/* Domain + column type breakdown */}
        <div className="space-y-5">
          <Card>
            <SectionTitle>Business Domain</SectionTitle>
            <div className="font-serif text-xl font-bold" style={{ color: "#E8C97A" }}>
              {result.business_domain || "Unknown"}
            </div>
            <div className="mt-1 text-xs text-white/40">
              {(result.domain_confidence * 100).toFixed(0)}% confidence
            </div>
            {result.domain_reasoning && (
              <p className="mt-3 text-[13px] leading-relaxed text-white/60">
                {result.domain_reasoning}
              </p>
            )}
          </Card>

          {profile && (
            <Card>
              <SectionTitle>Column Types</SectionTitle>
              <dl className="space-y-2 text-[13px]">
                {(
                  [
                    ["Numeric", profile.numeric_columns],
                    ["Categorical", profile.categorical_columns],
                    ["Datetime", profile.datetime_columns],
                    ["Text", profile.text_columns],
                  ] as const
                ).map(([label, cols]) => (
                  <div key={label} className="flex items-center justify-between gap-3">
                    <dt className="text-white/50">{label}</dt>
                    <dd className="tabular-nums font-semibold text-white/80">
                      {cols?.length ?? 0}
                    </dd>
                  </div>
                ))}
              </dl>
            </Card>
          )}
        </div>
      </div>

      {/* Per-column profile */}
      {!!profile?.column_profiles?.length && (
        <Card>
          <SectionTitle sub={`${profile.column_profiles.length} columns profiled`}>
            Column Detail
          </SectionTitle>
          <div className="max-h-[420px] overflow-auto rounded-xl" style={{ border: "1px solid rgba(255,255,255,0.07)" }}>
            <table className="w-full text-left text-[12px]">
              <thead className="sticky top-0" style={{ background: "rgba(28,22,16,0.98)" }}>
                <tr className="text-white/50">
                  <th className="px-3 py-2 font-semibold">Column</th>
                  <th className="px-3 py-2 font-semibold">Type</th>
                  <th className="px-3 py-2 text-right font-semibold">Nulls</th>
                  <th className="px-3 py-2 text-right font-semibold">Unique</th>
                  <th className="px-3 py-2 text-right font-semibold">Mean</th>
                </tr>
              </thead>
              <tbody>
                {profile.column_profiles.map((c) => (
                  <tr key={c.name} style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                    <td className="px-3 py-1.5 font-medium text-white/80">{c.name}</td>
                    <td className="px-3 py-1.5 text-white/45">{c.inferred_type}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-white/60">
                      {c.null_pct.toFixed(1)}%
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-white/60">
                      {c.unique_count.toLocaleString()}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-white/60">
                      {c.mean != null ? c.mean.toFixed(2) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
