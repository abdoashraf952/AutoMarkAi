"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import type { Language, QuestionOption } from "@/lib/types";
import { t } from "@/lib/copy";

/**
 * Renders a real estate interview question with options (CHANGE 3).
 * - single_select_with_other: tap a card to submit; or type an "Other" answer.
 * - multi_select_with_other: tick several options, then Confirm.
 * Both include an "Other" free-text input.
 */
export default function QuestionWithOptions({
  options,
  multi,
  onSubmit,
  lang,
}: {
  options: QuestionOption[];
  multi: boolean;
  onSubmit: (answer: string, displayLabel: string) => void;
  lang?: Language;
}) {
  const rtl = lang === "ar";
  const tr = (k: Parameters<typeof t>[1]) => t(lang ?? "en", k);
  const recLabel = rtl ? "موصى به" : "Recommended";

  const [selected, setSelected] = useState<string[]>([]); // labels (multi)
  const [other, setOther] = useState("");

  function submitSingle(opt: QuestionOption) {
    onSubmit(opt.label, opt.label);
  }

  function toggle(label: string) {
    setSelected((prev) =>
      prev.includes(label) ? prev.filter((l) => l !== label) : [...prev, label]
    );
  }

  function submitMulti() {
    const labels = [...selected];
    if (other.trim()) labels.push(other.trim());
    if (!labels.length) return;
    const joined = labels.join(", ");
    onSubmit(joined, joined);
  }

  function submitOther() {
    if (!other.trim()) return;
    onSubmit(other.trim(), other.trim());
  }

  return (
    <div className={`flex w-full flex-col gap-2.5 ${rtl ? "rtl" : ""}`}>
      <div className="grid w-full gap-2 sm:grid-cols-2">
        {options.map((opt, i) => {
          const checked = selected.includes(opt.label);
          return (
            <motion.button
              key={opt.value + i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.03 }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => (multi ? toggle(opt.label) : submitSingle(opt))}
              className={`group relative flex items-center gap-2.5 rounded-2xl px-3.5 py-3 text-left transition-all ${
                opt.recommended
                  ? "border border-accent-amber/50 bg-accent-amber/10 hover:bg-accent-amber/15"
                  : checked
                  ? "border border-accent-cyan/60 bg-accent-cyan/10"
                  : "glass hover:border-accent-violet/60 hover:shadow-glow"
              }`}
            >
              {multi && (
                <span
                  className={`flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-md border text-xs ${
                    checked ? "border-accent-cyan bg-accent-cyan text-ink-900" : "border-white/30"
                  }`}
                >
                  {checked ? "✓" : ""}
                </span>
              )}
              <span className="flex-1">
                <span className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-white">{opt.label}</span>
                  {opt.recommended && <span className="badge-rec">{recLabel}</span>}
                </span>
              </span>
              {!multi && (
                <span className="text-white/30 transition-transform group-hover:translate-x-0.5 group-hover:text-accent-cyan">
                  →
                </span>
              )}
            </motion.button>
          );
        })}
      </div>

      {/* Other free-text */}
      <div className="flex w-full items-end gap-2">
        <input
          value={other}
          onChange={(e) => setOther(e.target.value)}
          placeholder={tr("otherPlaceholder")}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !multi) {
              e.preventDefault();
              submitOther();
            }
          }}
          className={`field ${rtl ? "rtl" : ""}`}
        />
        {multi ? (
          <button onClick={submitMulti} className="btn-primary flex-shrink-0 !px-4 !py-3">
            {tr("confirmMulti")}
          </button>
        ) : (
          <button
            onClick={submitOther}
            disabled={!other.trim()}
            className="btn-primary flex-shrink-0 !px-4 !py-3"
          >
            {tr("send")}
          </button>
        )}
      </div>
    </div>
  );
}
