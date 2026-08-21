"use client";

import type { ApprovalMode, Language } from "@/lib/types";
import { t } from "@/lib/copy";

const MODES: { value: ApprovalMode; labelKey: "fullManualLabel" | "guidedLabel" | "autoPilotLabel"; descKey: "fullManualDesc" | "guidedDesc" | "autoPilotDesc"; recommended?: boolean }[] = [
  { value: "guided",      labelKey: "guidedLabel",      descKey: "guidedDesc",      recommended: true },
  { value: "full_manual", labelKey: "fullManualLabel",  descKey: "fullManualDesc" },
  { value: "autopilot",   labelKey: "autoPilotLabel",   descKey: "autoPilotDesc" },
];

export default function ApprovalModeCards({
  onPick,
  lang = "en",
}: {
  onPick: (mode: ApprovalMode, label: string) => void;
  lang?: Language;
}) {
  const rtl = lang === "ar";

  return (
    <div className={`flex flex-col gap-2.5 w-full ${rtl ? "rtl" : ""}`}>
      {MODES.map(({ value, labelKey, descKey, recommended }) => (
        <button
          key={value}
          onClick={() => onPick(value, t(lang, labelKey))}
          className="glass rounded-2xl px-4 py-3 text-left hover:bg-white/10 transition-colors
                     border border-white/10 hover:border-accent-violet/60 w-full"
        >
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-sm font-semibold text-white">{t(lang, labelKey)}</span>
            {recommended && (
              <span className="text-[10px] font-bold uppercase tracking-wide
                               bg-accent-violet/20 text-accent-violet rounded-full px-2 py-0.5">
                {rtl ? "الأنسب" : "Recommended"}
              </span>
            )}
          </div>
          <p className="text-xs text-white/55 leading-relaxed">{t(lang, descKey)}</p>
        </button>
      ))}
    </div>
  );
}
