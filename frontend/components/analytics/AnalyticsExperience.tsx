"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import {
  createAnalyticsSession,
  getResult,
  listCrmTables,
  loadCrmTable,
  openAnalyticsStream,
  startAnalysis,
  uploadDataset,
} from "@/lib/analytics";
import type { AnalysisResult, CrmTable } from "@/lib/analytics";
import type { AuthUser } from "@/hooks/useAuth";

import AnalyticsChat from "./AnalyticsChat";
import InsightsTab from "./InsightsTab";
import KpiTab from "./KpiTab";
import OverviewTab from "./OverviewTab";
import ReportTab from "./ReportTab";
import VizTab from "./VizTab";

type Tab = "overview" | "kpis" | "insights" | "viz" | "report" | "chat";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "kpis", label: "KPIs" },
  { id: "insights", label: "Insights" },
  { id: "viz", label: "Visualizations" },
  { id: "report", label: "Report" },
  { id: "chat", label: "Chat" },
];

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export default function AnalyticsExperience({
  user,
  onBack,
}: {
  user: AuthUser;
  onBack: () => void;
}) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileSize, setFileSize] = useState<number>(0);

  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<string>("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [tab, setTab] = useState<Tab>("overview");
  const [crmTables, setCrmTables] = useState<CrmTable[]>([]);
  const [uploading, setUploading] = useState(false);

  const streamRef = useRef<{ close: () => void } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Bootstrap: one session per visit, plus the CRM table list ──────── //
  useEffect(() => {
    let cancelled = false;
    createAnalyticsSession()
      .then((r) => !cancelled && setSessionId(r.session_id))
      .catch((e) => !cancelled && setError(e.message));
    listCrmTables()
      .then((t) => !cancelled && setCrmTables(t))
      .catch(() => {
        /* CRM integration is optional — a missing table list is not an error */
      });
    return () => {
      cancelled = true;
      streamRef.current?.close();
    };
  }, []);

  // ── Actions ────────────────────────────────────────────────────────── //

  const handleFile = useCallback(
    async (file: File) => {
      if (!sessionId) return;
      setError(null);
      setUploading(true);
      try {
        const r = await uploadDataset(sessionId, file);
        setFileName(r.file_name);
        setFileSize(r.file_size_bytes);
        setResult(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [sessionId]
  );

  const handleCrmTable = useCallback(
    async (table: string) => {
      if (!sessionId) return;
      setError(null);
      setUploading(true);
      try {
        const r = await loadCrmTable(sessionId, table);
        setFileName(r.file_name);
        setFileSize(r.file_size_bytes);
        setResult(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load CRM table");
      } finally {
        setUploading(false);
      }
    },
    [sessionId]
  );

  const run = useCallback(async () => {
    if (!sessionId || running) return;
    setError(null);
    setResult(null);
    setRunning(true);
    setProgress("Starting…");

    streamRef.current?.close();
    streamRef.current = openAnalyticsStream(sessionId, async (event) => {
      if (event.event === "progress") {
        setProgress(event.message);
      } else if (event.event === "complete") {
        try {
          setResult(await getResult(sessionId));
          setTab("overview");
        } catch (e) {
          setError(e instanceof Error ? e.message : "Could not load the result");
        }
        setRunning(false);
        streamRef.current?.close();
      } else if (event.event === "error") {
        setError(event.message);
        setRunning(false);
        streamRef.current?.close();
      }
    });

    try {
      await startAnalysis(sessionId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the analysis");
      setRunning(false);
      streamRef.current?.close();
    }
  }, [sessionId, running]);

  // ── Render ─────────────────────────────────────────────────────────── //

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden">
      {/* Header */}
      <header
        className="flex flex-shrink-0 items-center justify-between gap-4 px-6 py-4"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}
      >
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="rounded-xl px-3 py-1.5 text-[12px] font-semibold text-white/50 transition-colors hover:text-white"
            style={{ background: "rgba(255,255,255,0.05)" }}
          >
            ← Back
          </button>
          <div>
            <h1 className="font-serif text-lg font-bold text-white">Analytics</h1>
            <p className="text-[11px] text-white/35">AI business intelligence</p>
          </div>
        </div>
        <span className="hidden text-[11px] text-white/35 sm:block">{user.email}</span>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* Sidebar — data source */}
        <aside
          className="hidden w-72 flex-shrink-0 overflow-y-auto p-5 lg:block"
          style={{ borderRight: "1px solid rgba(255,255,255,0.07)" }}
        >
          <h2 className="mb-3 text-[10px] font-bold uppercase tracking-widest text-white/35">
            Dataset
          </h2>

          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
              e.target.value = "";
            }}
          />

          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={!sessionId || uploading || running}
            className="w-full rounded-2xl px-4 py-6 text-center text-[12px] transition-colors disabled:opacity-40"
            style={{
              border: "1px dashed rgba(255,255,255,0.18)",
              background: "rgba(255,255,255,0.03)",
              color: "rgba(255,255,255,0.55)",
            }}
          >
            {uploading ? "Uploading…" : "Drop or choose a CSV / Excel file"}
          </button>

          {fileName && (
            <div
              className="mt-3 rounded-xl px-3 py-2.5"
              style={{ background: "rgba(201,168,76,0.10)", border: "1px solid rgba(201,168,76,0.25)" }}
            >
              <div className="truncate text-[12px] text-white/80">{fileName}</div>
              <div className="text-[11px] text-white/40">{fmtBytes(fileSize)}</div>
            </div>
          )}

          <button
            onClick={run}
            disabled={!fileName || running}
            className="mt-3 w-full rounded-2xl py-3 text-[12px] font-bold uppercase tracking-wider transition-transform hover:scale-[1.02] disabled:opacity-40 disabled:hover:scale-100"
            style={{
              background: "linear-gradient(135deg, #B8860B 0%, #C9A84C 45%, #E8C97A 100%)",
              color: "#1a1408",
            }}
          >
            {running ? "Analysing…" : "Run analysis"}
          </button>

          {/* CRM tables — the shared database made visible */}
          {!!crmTables.length && (
            <div className="mt-7">
              <h2 className="mb-1 text-[10px] font-bold uppercase tracking-widest text-white/35">
                From the CRM
              </h2>
              <p className="mb-3 text-[11px] leading-snug text-white/30">
                Analyse the CRM&apos;s own tables — same database, no export needed.
              </p>
              <div className="space-y-2">
                {crmTables.map((t) => (
                  <button
                    key={t.name}
                    onClick={() => handleCrmTable(t.name)}
                    disabled={uploading || running}
                    className="w-full rounded-xl px-3 py-2.5 text-left transition-colors disabled:opacity-40"
                    style={{
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(255,255,255,0.08)",
                    }}
                  >
                    <div className="text-[12px] font-semibold capitalize text-white/75">
                      {t.name}
                    </div>
                    <div className="mt-0.5 text-[11px] leading-snug text-white/35">
                      {t.description}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {result && (
            <div className="mt-7">
              <h2 className="mb-2 text-[10px] font-bold uppercase tracking-widest text-white/35">
                Domain
              </h2>
              <div className="font-serif text-base font-bold" style={{ color: "#E8C97A" }}>
                {result.business_domain || "Unknown"}
              </div>
              <div className="text-[11px] text-white/35">
                {(result.domain_confidence * 100).toFixed(0)}% confidence
              </div>
            </div>
          )}
        </aside>

        {/* Main */}
        <main className="min-w-0 flex-1 overflow-y-auto p-6">
          {error && (
            <div
              className="mb-5 rounded-xl px-4 py-3 text-sm text-white/80"
              style={{ background: "rgba(227,73,72,0.12)", border: "1px solid rgba(227,73,72,0.3)" }}
            >
              {error}
            </div>
          )}

          {/* Mobile data-source controls */}
          <div className="mb-5 flex gap-2 lg:hidden">
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={!sessionId || uploading || running}
              className="flex-1 rounded-xl px-3 py-2.5 text-[12px] disabled:opacity-40"
              style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)" }}
            >
              {fileName ?? "Choose file"}
            </button>
            <button
              onClick={run}
              disabled={!fileName || running}
              className="rounded-xl px-4 py-2.5 text-[12px] font-bold uppercase tracking-wider disabled:opacity-40"
              style={{
                background: "linear-gradient(135deg, #B8860B 0%, #C9A84C 45%, #E8C97A 100%)",
                color: "#1a1408",
              }}
            >
              Run
            </button>
          </div>

          {running && (
            <div className="flex flex-col items-center justify-center py-24">
              <div
                className="h-10 w-10 animate-spin rounded-full"
                style={{ border: "2px solid rgba(201,168,76,0.2)", borderTopColor: "#C9A84C" }}
              />
              <p className="mt-4 text-sm text-white/60">{progress}</p>
              <p className="mt-1 text-[11px] text-white/30">
                The full pipeline runs seven agents — this takes a moment.
              </p>
            </div>
          )}

          {!running && !result && !error && (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <div className="font-serif text-2xl font-bold text-white/80">
                Upload a dataset to begin
              </div>
              <p className="mt-2 max-w-md text-sm text-white/40">
                AutoMark profiles the data, detects your business domain, discovers KPIs,
                generates insights, and writes an executive report.
              </p>
            </div>
          )}

          {!running && result && (
            <>
              {/* Tabs */}
              <div
                className="mb-6 flex gap-1 overflow-x-auto"
                style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}
              >
                {TABS.map((t) => {
                  const active = tab === t.id;
                  return (
                    <button
                      key={t.id}
                      onClick={() => setTab(t.id)}
                      className="relative flex-shrink-0 px-4 py-2.5 text-[13px] font-semibold transition-colors"
                      style={{ color: active ? "#E8C97A" : "rgba(255,255,255,0.4)" }}
                    >
                      {t.label}
                      {active && (
                        <motion.div
                          layoutId="analytics-tab-underline"
                          className="absolute inset-x-2 -bottom-px h-0.5 rounded-full"
                          style={{ background: "#C9A84C" }}
                        />
                      )}
                    </button>
                  );
                })}
              </div>

              <AnimatePresence mode="wait">
                <motion.div
                  key={tab}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.18 }}
                >
                  {tab === "overview" && <OverviewTab result={result} />}
                  {tab === "kpis" && <KpiTab kpis={result.kpis} />}
                  {tab === "insights" && <InsightsTab insights={result.insights} />}
                  {tab === "viz" && sessionId && (
                    <VizTab sessionId={sessionId} recommendations={result.visualizations} />
                  )}
                  {tab === "report" && (
                    <ReportTab
                      report={result.executive_report}
                      fileName={result.file_name}
                      generatedAt={result.report_generated_at}
                    />
                  )}
                  {tab === "chat" && sessionId && <AnalyticsChat sessionId={sessionId} />}
                </motion.div>
              </AnimatePresence>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
