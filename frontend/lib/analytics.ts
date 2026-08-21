// ------------------------------------------------------------------ //
// Typed client for the analytics module (src/analytics/api.py),       //
// mounted at /api/analytics on the same backend as campaigns.         //
// ------------------------------------------------------------------ //

import { ANALYTICS_API, ApiError, authHeader, authToken } from "./api";

// ── Types ─────────────────────────────────────────────────────────── //

export interface ColumnProfile {
  name: string;
  dtype: string;
  inferred_type: string;
  null_count: number;
  null_pct: number;
  unique_count: number;
  unique_pct: number;
  sample_values?: unknown[];
  mean?: number | null;
  median?: number | null;
  std?: number | null;
  min_val?: number | null;
  max_val?: number | null;
  top_categories?: Record<string, unknown>[];
}

export interface DatasetSummary {
  file_name: string;
  row_count: number;
  column_count: number;
  columns: string[];
  dtypes: Record<string, string>;
  memory_usage_mb: number;
  sample_rows?: Record<string, unknown>[];
}

export interface ProfilingResult {
  dataset_summary: DatasetSummary;
  column_profiles: ColumnProfile[];
  total_missing_pct: number;
  duplicate_row_count: number;
  numeric_columns: string[];
  categorical_columns: string[];
  datetime_columns: string[];
  text_columns: string[];
  data_quality_score: number;
  quality_issues: string[];
  profiling_narrative: string;
}

export interface KPI {
  id: string;
  name: string;
  business_definition?: string;
  formula?: string | null;
  required_columns?: string[];
  priority?: string;
  category?: string;
  why_important?: string;
  current_value?: string | null;
  unit?: string | null;
  trend_direction?: string | null;
  benchmark?: string | null;
}

export interface Insight {
  id: string;
  title?: string;
  type?: string;
  priority?: string;
  executive_summary?: string;
  detailed_analysis?: string;
  evidence?: string[];
  recommendation?: string;
  affected_kpis?: string[];
  business_impact?: string | null;
  confidence?: string;
}

export interface VizRecommendation {
  title?: string;
  chart_type?: string;
  x_axis?: string;
  y_axis?: string;
  aggregation?: string;
  powerbi_visual_type?: string;
  business_purpose?: string;
  [k: string]: unknown;
}

export interface AnalysisResult {
  session_id: string;
  analysis_id: string | null;
  file_name: string;
  file_size_bytes: number;
  business_domain: string;
  domain_confidence: number;
  domain_reasoning: string;
  dataset_summary: DatasetSummary | null;
  profiling_result: ProfilingResult | null;
  kpis: KPI[];
  insights: Insight[];
  visualizations: VizRecommendation[];
  executive_report: string | null;
  report_generated_at: string | null;
  current_step: string;
  error_message: string | null;
}

export interface AnalysisSummary {
  analysis_id: string;
  session_id: string;
  file_name: string;
  file_size_bytes: number | null;
  business_domain: string | null;
  domain_confidence: number | null;
  created_at: string | null;
}

export interface AnalyticsChatMessage {
  role: "user" | "assistant";
  content: string;
  message_type?: string;
  timestamp?: string | null;
}

export interface CrmTable {
  name: string;
  description: string;
}

export interface ChartSpecPayload {
  type: "bar" | "line" | "pie" | "donut" | "scatter";
  title: string;
  x: string;
  y: string;
  points: { label?: string; value?: number; x?: number; y?: number }[];
}

export type AnalyticsEvent =
  | { event: "started"; session_id: string }
  | { event: "progress"; step: string; message: string }
  | { event: "complete"; analysis_id: string | null }
  | { event: "error"; message: string };

// ── Helpers ───────────────────────────────────────────────────────── //

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      detail = body?.detail || JSON.stringify(body);
    } catch {
      /* non-json error body */
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

function jsonHeaders(): HeadersInit {
  return { "Content-Type": "application/json", ...authHeader() };
}

// ── Endpoints ─────────────────────────────────────────────────────── //

export async function createAnalyticsSession(): Promise<{ session_id: string }> {
  const res = await fetch(`${ANALYTICS_API}/sessions`, {
    method: "POST",
    headers: authHeader(),
  });
  return parse(res);
}

export async function uploadDataset(
  sessionId: string,
  file: File
): Promise<{ file_name: string; file_size_bytes: number }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${ANALYTICS_API}/sessions/${sessionId}/upload`, {
    method: "POST",
    headers: authHeader(), // no Content-Type — the browser sets the boundary
    body: form,
  });
  return parse(res);
}

export async function startAnalysis(sessionId: string): Promise<{ status: string }> {
  const res = await fetch(`${ANALYTICS_API}/sessions/${sessionId}/analyze`, {
    method: "POST",
    headers: authHeader(),
  });
  return parse(res);
}

export async function getResult(sessionId: string): Promise<AnalysisResult> {
  const res = await fetch(`${ANALYTICS_API}/sessions/${sessionId}/result`, {
    headers: authHeader(),
  });
  return parse(res);
}

export async function askQuestion(
  sessionId: string,
  query: string
): Promise<{ answer: string; chat_history: AnalyticsChatMessage[] }> {
  const res = await fetch(`${ANALYTICS_API}/sessions/${sessionId}/chat`, {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify({ query }),
  });
  return parse(res);
}

export async function getCharts(sessionId: string): Promise<{ charts: ChartSpecPayload[] }> {
  const res = await fetch(`${ANALYTICS_API}/sessions/${sessionId}/charts`, {
    headers: authHeader(),
  });
  return parse(res);
}

export async function listAnalyses(): Promise<AnalysisSummary[]> {
  const res = await fetch(`${ANALYTICS_API}/analyses`, { headers: authHeader() });
  return parse(res);
}

export async function getAnalysis(analysisId: string): Promise<AnalysisResult> {
  const res = await fetch(`${ANALYTICS_API}/analyses/${analysisId}`, {
    headers: authHeader(),
  });
  return parse(res);
}

export async function listCrmTables(): Promise<CrmTable[]> {
  const res = await fetch(`${ANALYTICS_API}/crm-tables`, { headers: authHeader() });
  return parse(res);
}

export async function loadCrmTable(
  sessionId: string,
  table: string
): Promise<{ file_name: string; file_size_bytes: number }> {
  const res = await fetch(`${ANALYTICS_API}/sessions/${sessionId}/load-crm-table`, {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify({ table }),
  });
  return parse(res);
}

/**
 * Subscribe to pipeline progress.
 *
 * EventSource cannot send an Authorization header, so the JWT goes in the
 * query string — the backend accepts either for this endpoint only.
 */
export function openAnalyticsStream(
  sessionId: string,
  onEvent: (e: AnalyticsEvent) => void
): { close: () => void } {
  const token = authToken();
  const url =
    `${ANALYTICS_API}/sessions/${sessionId}/stream` +
    (token ? `?token=${encodeURIComponent(token)}` : "");

  const source = new EventSource(url);

  source.onmessage = (msg) => {
    try {
      onEvent(JSON.parse(msg.data) as AnalyticsEvent);
    } catch {
      /* malformed frame — ignore */
    }
  };
  source.onerror = () => {
    /* stream closes itself after complete/error; ignore transient failures */
  };

  return { close: () => source.close() };
}
