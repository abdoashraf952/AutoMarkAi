"use client";

// ------------------------------------------------------------------ //
// Inline SVG charts for the analytics tabs.                           //
//                                                                     //
// Data arrives already aggregated from GET /sessions/{id}/charts —    //
// pandas does the grouping server-side, so these components only draw.//
//                                                                     //
// Colour policy (validated against the app's warm dark surface        //
// #1C1610 with the dataviz validator, all six checks PASS):           //
//   • single-series bar / line / scatter → one hue, the brand gold.   //
//     Magnitude is the job, so sequential-by-one-hue is correct;      //
//     colour carries no identity and must not vary per bar.           //
//   • donut / pie (part-to-whole, identity IS the job) → the 8-slot   //
//     categorical palette below, assigned in fixed order, never       //
//     cycled. Worst adjacent CVD ΔE 8.4, normal-vision ΔE 19.3.       //
//                                                                     //
// Every chart ships a hover tooltip and a table view, so identity and //
// values are never conveyed by colour alone.                          //
// ------------------------------------------------------------------ //

import { useMemo, useState } from "react";

// ── Tokens ────────────────────────────────────────────────────────── //

/** Single-hue accent for magnitude charts. 3:1+ on the chart surface. */
const ACCENT = "#C9A84C";

/** Fixed-order categorical slots. Never generate a 9th — fold to "Other". */
const CATEGORICAL = [
  "#3987e5", // blue
  "#d95926", // orange
  "#199e70", // aqua
  "#c98500", // yellow
  "#d55181", // magenta
  "#008300", // green
  "#9085e9", // violet
  "#e66767", // red
];

const SURFACE = "#17140e";
const GRID = "rgba(255,255,255,0.07)";
const TEXT_MUTED = "rgba(232,234,245,0.45)";
const TEXT_SECONDARY = "rgba(232,234,245,0.70)";

export interface ChartPoint {
  label?: string;
  value?: number;
  x?: number;
  y?: number;
}

export interface ChartSpec {
  type: "bar" | "line" | "pie" | "donut" | "scatter";
  title: string;
  x: string;
  y: string;
  points: ChartPoint[];
}

// ── Shared helpers ────────────────────────────────────────────────── //

function fmtNum(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  if (Number.isInteger(n)) return String(n);
  return n.toFixed(2);
}

function truncate(s: string, max = 14): string {
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

interface TooltipState {
  x: number;
  y: number;
  lines: string[];
}

function Tooltip({ tip }: { tip: TooltipState | null }) {
  if (!tip) return null;
  return (
    <div
      className="pointer-events-none absolute z-20 rounded-lg px-2.5 py-1.5 text-[11px] leading-snug shadow-card"
      style={{
        left: tip.x,
        top: tip.y,
        transform: "translate(-50%, -115%)",
        background: "rgba(10,8,5,0.95)",
        border: "1px solid rgba(255,255,255,0.14)",
        color: "#e8eaf5",
        whiteSpace: "nowrap",
      }}
    >
      {tip.lines.map((l, i) => (
        <div key={i} style={i === 0 ? { fontWeight: 600 } : { color: TEXT_MUTED }}>
          {l}
        </div>
      ))}
    </div>
  );
}

/** Accessible fallback: the same numbers as a table, toggled per chart. */
function DataTable({ spec }: { spec: ChartSpec }) {
  const isXY = spec.type === "scatter";
  return (
    <div className="max-h-64 overflow-auto rounded-xl" style={{ border: `1px solid ${GRID}` }}>
      <table className="w-full text-left text-[11px]">
        <thead className="sticky top-0" style={{ background: "rgba(255,255,255,0.05)" }}>
          <tr style={{ color: TEXT_SECONDARY }}>
            <th className="px-3 py-2 font-semibold">{spec.x}</th>
            <th className="px-3 py-2 text-right font-semibold">{spec.y}</th>
          </tr>
        </thead>
        <tbody>
          {spec.points.map((p, i) => (
            <tr key={i} style={{ borderTop: `1px solid ${GRID}`, color: TEXT_MUTED }}>
              <td className="px-3 py-1.5">{isXY ? fmtNum(p.x ?? 0) : p.label}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">
                {fmtNum((isXY ? p.y : p.value) ?? 0)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Bar (horizontal — category names stay readable) ───────────────── //

function BarChart({ spec }: { spec: ChartSpec }) {
  const [tip, setTip] = useState<TooltipState | null>(null);
  const points = spec.points;
  const max = Math.max(...points.map((p) => p.value ?? 0), 0) || 1;

  const rowH = 26;
  const gap = 6;
  const labelW = 108;
  const height = points.length * (rowH + gap);

  return (
    <div className="relative">
      <Tooltip tip={tip} />
      <svg width="100%" height={height} role="img" aria-label={spec.title}>
        {points.map((p, i) => {
          const value = p.value ?? 0;
          const y = i * (rowH + gap);
          const pct = Math.max(0, value / max);
          return (
            <g
              key={i}
              onMouseMove={(e) => {
                const r = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
                setTip({
                  x: e.clientX - r.left,
                  y: y + rowH / 2,
                  lines: [p.label ?? "", `${spec.y}: ${fmtNum(value)}`],
                });
              }}
              onMouseLeave={() => setTip(null)}
            >
              {/* full-width hit target, larger than the mark itself */}
              <rect x={0} y={y} width="100%" height={rowH} fill="transparent" />
              <text
                x={0}
                y={y + rowH / 2 + 4}
                fontSize={11}
                fill={TEXT_SECONDARY}
              >
                {truncate(p.label ?? "")}
              </text>
              {/* recessive track */}
              <rect
                x={labelW}
                y={y + 6}
                width={`calc(100% - ${labelW + 52}px)`}
                height={rowH - 12}
                rx={4}
                fill="rgba(255,255,255,0.04)"
              />
              <rect
                x={labelW}
                y={y + 6}
                width={`calc((100% - ${labelW + 52}px) * ${pct})`}
                height={rowH - 12}
                rx={4}
                fill={ACCENT}
              />
              {/* direct label — values are never colour-only */}
              <text
                x="100%"
                y={y + rowH / 2 + 4}
                textAnchor="end"
                fontSize={11}
                fill={TEXT_MUTED}
                className="tabular-nums"
              >
                {fmtNum(value)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ── Line ──────────────────────────────────────────────────────────── //

function LineChart({ spec }: { spec: ChartSpec }) {
  const [tip, setTip] = useState<TooltipState | null>(null);
  const [hover, setHover] = useState<number | null>(null);

  const W = 520;
  const H = 200;
  const PAD = { t: 12, r: 12, b: 26, l: 44 };

  const points = spec.points;
  const values = points.map((p) => p.value ?? 0);
  const max = Math.max(...values, 0);
  const min = Math.min(...values, 0);
  const span = max - min || 1;

  const px = (i: number) =>
    PAD.l + (i / Math.max(points.length - 1, 1)) * (W - PAD.l - PAD.r);
  const py = (v: number) => PAD.t + (1 - (v - min) / span) * (H - PAD.t - PAD.b);

  const d = points.map((p, i) => `${i ? "L" : "M"}${px(i)},${py(p.value ?? 0)}`).join(" ");

  // Recessive gridlines at quartiles.
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => min + f * span);

  return (
    <div className="relative">
      <Tooltip tip={tip} />
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        role="img"
        aria-label={spec.title}
        onMouseLeave={() => {
          setTip(null);
          setHover(null);
        }}
      >
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={PAD.l} x2={W - PAD.r} y1={py(t)} y2={py(t)} stroke={GRID} strokeWidth={1} />
            <text x={PAD.l - 6} y={py(t) + 3} textAnchor="end" fontSize={9} fill={TEXT_MUTED}>
              {fmtNum(t)}
            </text>
          </g>
        ))}

        <path d={d} fill="none" stroke={ACCENT} strokeWidth={2} strokeLinejoin="round" />

        {hover !== null && (
          <line
            x1={px(hover)}
            x2={px(hover)}
            y1={PAD.t}
            y2={H - PAD.b}
            stroke="rgba(255,255,255,0.22)"
            strokeWidth={1}
          />
        )}

        {points.map((p, i) => (
          <g key={i}>
            {/* hit target wider than the marker */}
            <rect
              x={px(i) - 12}
              y={PAD.t}
              width={24}
              height={H - PAD.t - PAD.b}
              fill="transparent"
              onMouseMove={(e) => {
                const r = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
                setHover(i);
                setTip({
                  x: e.clientX - r.left,
                  y: (py(p.value ?? 0) / H) * r.height,
                  lines: [p.label ?? "", `${spec.y}: ${fmtNum(p.value ?? 0)}`],
                });
              }}
            />
            {hover === i && (
              <circle
                cx={px(i)}
                cy={py(p.value ?? 0)}
                r={4.5}
                fill={ACCENT}
                stroke={SURFACE}
                strokeWidth={2}
              />
            )}
          </g>
        ))}

        {/* first / last x labels only — no label on every point */}
        {points.length > 0 && (
          <>
            <text x={PAD.l} y={H - 8} fontSize={9} fill={TEXT_MUTED}>
              {truncate(points[0].label ?? "", 12)}
            </text>
            <text x={W - PAD.r} y={H - 8} textAnchor="end" fontSize={9} fill={TEXT_MUTED}>
              {truncate(points[points.length - 1].label ?? "", 12)}
            </text>
          </>
        )}
      </svg>
    </div>
  );
}

// ── Donut / pie ───────────────────────────────────────────────────── //

function DonutChart({ spec }: { spec: ChartSpec }) {
  const [tip, setTip] = useState<TooltipState | null>(null);
  const points = spec.points.slice(0, CATEGORICAL.length);
  const total = points.reduce((s, p) => s + (p.value ?? 0), 0) || 1;

  const size = 168;
  const r = 68;
  const cx = size / 2;
  const cy = size / 2;
  const inner = spec.type === "donut" ? 40 : 0;

  let angle = -Math.PI / 2;
  const arcs = points.map((p, i) => {
    const frac = (p.value ?? 0) / total;
    const start = angle;
    // 2px surface gap between adjacent fills
    const sweep = frac * Math.PI * 2;
    const end = start + sweep;
    angle = end;

    const large = sweep > Math.PI ? 1 : 0;
    const x0 = cx + r * Math.cos(start);
    const y0 = cy + r * Math.sin(start);
    const x1 = cx + r * Math.cos(end);
    const y1 = cy + r * Math.sin(end);

    let d: string;
    if (inner > 0) {
      const ix1 = cx + inner * Math.cos(end);
      const iy1 = cy + inner * Math.sin(end);
      const ix0 = cx + inner * Math.cos(start);
      const iy0 = cy + inner * Math.sin(start);
      d = `M${x0},${y0} A${r},${r} 0 ${large} 1 ${x1},${y1} L${ix1},${iy1} A${inner},${inner} 0 ${large} 0 ${ix0},${iy0} Z`;
    } else {
      d = `M${cx},${cy} L${x0},${y0} A${r},${r} 0 ${large} 1 ${x1},${y1} Z`;
    }
    return { d, color: CATEGORICAL[i], point: p, frac };
  });

  return (
    <div className="relative flex flex-wrap items-center gap-5">
      <Tooltip tip={tip} />
      <svg width={size} height={size} role="img" aria-label={spec.title}>
        {arcs.map((a, i) => (
          <path
            key={i}
            d={a.d}
            fill={a.color}
            stroke={SURFACE}
            strokeWidth={2}
            onMouseMove={(e) => {
              const rect = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
              setTip({
                x: e.clientX - rect.left,
                y: e.clientY - rect.top,
                lines: [
                  a.point.label ?? "",
                  `${fmtNum(a.point.value ?? 0)} · ${(a.frac * 100).toFixed(1)}%`,
                ],
              });
            }}
            onMouseLeave={() => setTip(null)}
          />
        ))}
      </svg>

      {/* Legend is always present for ≥2 slices — identity is never colour-alone */}
      <ul className="flex-1 space-y-1.5 text-[11px]" style={{ minWidth: 150 }}>
        {arcs.map((a, i) => (
          <li key={i} className="flex items-center gap-2">
            <span
              className="h-2.5 w-2.5 flex-shrink-0 rounded-sm"
              style={{ background: a.color }}
            />
            <span className="flex-1 truncate" style={{ color: TEXT_SECONDARY }}>
              {a.point.label}
            </span>
            <span className="tabular-nums" style={{ color: TEXT_MUTED }}>
              {(a.frac * 100).toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Scatter ───────────────────────────────────────────────────────── //

function ScatterChart({ spec }: { spec: ChartSpec }) {
  const [tip, setTip] = useState<TooltipState | null>(null);
  const W = 520;
  const H = 220;
  const PAD = { t: 12, r: 12, b: 28, l: 48 };

  const xs = spec.points.map((p) => p.x ?? 0);
  const ys = spec.points.map((p) => p.y ?? 0);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const xSpan = xMax - xMin || 1;
  const ySpan = yMax - yMin || 1;

  const px = (v: number) => PAD.l + ((v - xMin) / xSpan) * (W - PAD.l - PAD.r);
  const py = (v: number) => PAD.t + (1 - (v - yMin) / ySpan) * (H - PAD.t - PAD.b);

  return (
    <div className="relative">
      <Tooltip tip={tip} />
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={spec.title}>
        {[0, 0.5, 1].map((f, i) => (
          <g key={i}>
            <line
              x1={PAD.l}
              x2={W - PAD.r}
              y1={py(yMin + f * ySpan)}
              y2={py(yMin + f * ySpan)}
              stroke={GRID}
            />
            <text
              x={PAD.l - 6}
              y={py(yMin + f * ySpan) + 3}
              textAnchor="end"
              fontSize={9}
              fill={TEXT_MUTED}
            >
              {fmtNum(yMin + f * ySpan)}
            </text>
          </g>
        ))}

        {spec.points.map((p, i) => (
          <circle
            key={i}
            cx={px(p.x ?? 0)}
            cy={py(p.y ?? 0)}
            r={4}
            fill={ACCENT}
            fillOpacity={0.55}
            stroke={SURFACE}
            strokeWidth={1}
            onMouseMove={(e) => {
              const r = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
              setTip({
                x: e.clientX - r.left,
                y: e.clientY - r.top,
                lines: [`${spec.x}: ${fmtNum(p.x ?? 0)}`, `${spec.y}: ${fmtNum(p.y ?? 0)}`],
              });
            }}
            onMouseLeave={() => setTip(null)}
          />
        ))}

        <text x={W / 2} y={H - 6} textAnchor="middle" fontSize={9} fill={TEXT_MUTED}>
          {spec.x}
        </text>
      </svg>
    </div>
  );
}

// ── Card wrapper ──────────────────────────────────────────────────── //

export function ChartCard({ spec }: { spec: ChartSpec }) {
  const [showTable, setShowTable] = useState(false);

  const body = useMemo(() => {
    if (!spec.points?.length) return null;
    switch (spec.type) {
      case "bar":
        return <BarChart spec={spec} />;
      case "line":
        return <LineChart spec={spec} />;
      case "pie":
      case "donut":
        return <DonutChart spec={spec} />;
      case "scatter":
        return <ScatterChart spec={spec} />;
      default:
        return null;
    }
  }, [spec]);

  if (!body) return null;

  return (
    <div
      className="rounded-2xl p-5"
      style={{
        background: SURFACE,
        border: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-white">{spec.title || `${spec.y} by ${spec.x}`}</h4>
          <p className="mt-0.5 text-[11px]" style={{ color: TEXT_MUTED }}>
            {spec.y} by {spec.x}
          </p>
        </div>
        <button
          onClick={() => setShowTable((v) => !v)}
          className="flex-shrink-0 rounded-lg px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider transition-colors"
          style={{
            background: showTable ? "rgba(201,168,76,0.18)" : "rgba(255,255,255,0.06)",
            color: showTable ? "#E8C97A" : TEXT_MUTED,
          }}
        >
          {showTable ? "Chart" : "Table"}
        </button>
      </div>
      {showTable ? <DataTable spec={spec} /> : body}
    </div>
  );
}
