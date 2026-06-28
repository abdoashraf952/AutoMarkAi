"use client";

import { useState } from "react";
import type { CampaignReport, Language } from "@/lib/types";
import { t } from "@/lib/copy";

interface Props {
  report: CampaignReport;
  lang?: Language;
  onTriggerOperate?: () => void;
  operating?: boolean;
}

export default function CampaignReportCard({
  report,
  lang = "en",
  onTriggerOperate,
  operating = false,
}: Props) {
  const [showDecisions, setShowDecisions] = useState(false);
  const rtl = lang === "ar";

  const { diagnosis, decisions, control_mode, learning_state, compliance } = report;

  const controlLabel =
    control_mode === "advantage_plus"
      ? t(lang, "controlModeAuto")
      : t(lang, "controlModeManual");

  return (
    <div className={`glass rounded-2xl p-4 space-y-3 w-full ${rtl ? "rtl" : ""}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">{t(lang, "operateTitle")}</h3>
        <span className="text-[10px] text-white/40 font-mono">{controlLabel}</span>
      </div>

      {/* Status */}
      <div className="bg-white/5 rounded-xl px-3 py-2 text-sm text-white/80 leading-relaxed">
        {learning_state === "learning" ? (
          <span className="text-white/50">{t(lang, "learnPhaseNote")}</span>
        ) : (
          diagnosis?.status || t(lang, "operateStatus")
        )}
      </div>

      {/* Compliance badge */}
      {compliance && (
        <div
          className={`text-[11px] rounded-lg px-2 py-1 font-medium ${
            compliance.passed
              ? "bg-green-500/10 text-green-400"
              : "bg-red-500/10 text-red-400"
          }`}
        >
          {compliance.passed ? t(lang, "compliancePassed") : t(lang, "complianceFailed")}
          {!compliance.passed && compliance.violations.length > 0 && (
            <ul className="mt-1 list-disc list-inside opacity-80 text-[10px]">
              {compliance.violations.map((v, i) => (
                <li key={i}>{v}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Decisions toggle */}
      {decisions && decisions.length > 0 && (
        <div>
          <button
            onClick={() => setShowDecisions((s) => !s)}
            className="text-[11px] text-accent-violet/70 hover:text-accent-violet transition-colors"
          >
            {t(lang, "decisionsLabel")} ({decisions.length}) {showDecisions ? "▲" : "▼"}
          </button>
          {showDecisions && (
            <ul className="mt-2 space-y-1.5">
              {decisions.map((d, i) => (
                <li
                  key={i}
                  className="text-[11px] text-white/60 bg-white/5 rounded-lg px-2.5 py-1.5 leading-snug"
                >
                  <span className="font-semibold text-white/80 uppercase tracking-wide">
                    {d.decision}
                  </span>{" "}
                  — {d.rationale?.slice(0, 120)}
                  {(d.rationale?.length ?? 0) > 120 ? "…" : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Trigger operate button */}
      {onTriggerOperate && (
        <button
          onClick={onTriggerOperate}
          disabled={operating}
          className="w-full mt-1 rounded-xl py-2 text-sm font-semibold bg-accent-violet/20
                     hover:bg-accent-violet/30 text-accent-violet transition-colors
                     disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {operating ? t(lang, "operateRunning") : t(lang, "triggerOperate")}
        </button>
      )}
    </div>
  );
}
