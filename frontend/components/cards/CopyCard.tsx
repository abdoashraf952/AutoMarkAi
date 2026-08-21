"use client";

import { useState } from "react";
import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { t } from "@/lib/copy";
import type { Language } from "@/lib/types";

/**
 * Interactive copy review: the user picks ONE ad copy and ONE headline, can edit
 * either text inline, then confirms. Disabled once submitted or when the chat has
 * moved past the text-review phase.
 */
export default function CopyCard({
  copies,
  headlines,
  cta,
  lang = "en",
  onConfirm,
  disabled,
}: {
  copies: string[];
  headlines: string[];
  cta: string;
  lang?: Language;
  onConfirm?: (copyIndex: number, headlineIndex: number, copyText: string, headlineText: string) => void;
  disabled?: boolean;
}) {
  const tr = (k: Parameters<typeof t>[1]) => t(lang, k);
  const rtl = lang === "ar";

  const [copyIdx, setCopyIdx] = useState(0);
  const [headlineIdx, setHeadlineIdx] = useState(0);
  const [copyText, setCopyText] = useState(copies[0] ?? "");
  const [headlineText, setHeadlineText] = useState(headlines[0] ?? "");
  const [submitted, setSubmitted] = useState(false);

  const locked = disabled || submitted;

  function pickCopy(i: number) {
    if (locked) return;
    setCopyIdx(i);
    setCopyText(copies[i] ?? "");
  }
  function pickHeadline(i: number) {
    if (locked) return;
    setHeadlineIdx(i);
    setHeadlineText(headlines[i] ?? "");
  }

  function confirm() {
    if (locked || !copyText.trim() || !headlineText.trim()) return;
    setSubmitted(true);
    onConfirm?.(copyIdx, headlineIdx, copyText.trim(), headlineText.trim());
  }

  return (
    <div className={`glass w-full max-w-lg space-y-4 rounded-3xl p-5 shadow-card ${rtl ? "rtl" : ""}`}>
      <Selectable
        title={tr("chooseCopy")}
        items={copies}
        selected={copyIdx}
        onPick={pickCopy}
        locked={locked}
      />
      <EditField
        label={tr("editIfNeeded")}
        value={copyText}
        onChange={setCopyText}
        locked={locked}
        rtl={rtl}
        rows={2}
      />

      <Selectable
        title={tr("chooseHeadline")}
        items={headlines}
        selected={headlineIdx}
        onPick={pickHeadline}
        locked={locked}
      />
      <EditField
        label={tr("editIfNeeded")}
        value={headlineText}
        onChange={setHeadlineText}
        locked={locked}
        rtl={rtl}
        rows={1}
      />

      <div>
        <SectionTitle>{tr("ctaLabel")}</SectionTitle>
        <span className="inline-flex rounded-xl bg-gradient-to-r from-accent-violet to-accent-cyan px-4 py-1.5 text-sm font-semibold text-white">
          {cta}
        </span>
      </div>

      {!disabled && (
        <button
          onClick={confirm}
          disabled={locked || !copyText.trim() || !headlineText.trim()}
          className="btn-primary w-full disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitted ? "✓" : "✓ " + tr("confirmSelection")}
        </button>
      )}
    </div>
  );
}

function Selectable({
  title,
  items,
  selected,
  onPick,
  locked,
}: {
  title: string;
  items: string[];
  selected: number;
  onPick: (i: number) => void;
  locked?: boolean;
}) {
  if (!items?.length) return null;
  return (
    <div>
      <SectionTitle>{title}</SectionTitle>
      <div className="space-y-1.5">
        {items.map((it, i) => {
          const active = i === selected;
          return (
            <motion.button
              key={i}
              type="button"
              disabled={locked}
              onClick={() => onPick(i)}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.06 }}
              className={`flex w-full items-start gap-2.5 rounded-xl border px-3 py-2 text-start text-sm transition ${
                active
                  ? "border-accent-cyan/60 bg-accent-cyan/10 text-white"
                  : "border-white/10 bg-white/5 text-white/75 hover:border-white/25"
              } ${locked ? "cursor-default" : "cursor-pointer"}`}
            >
              <span
                className={`mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full border ${
                  active ? "border-accent-cyan" : "border-white/40"
                }`}
              >
                {active && <span className="h-2 w-2 rounded-full bg-accent-cyan" />}
              </span>
              <span>{it}</span>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}

function EditField({
  label,
  value,
  onChange,
  locked,
  rtl,
  rows,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  locked?: boolean;
  rtl?: boolean;
  rows?: number;
}) {
  return (
    <div>
      <p className="mb-1 text-[11px] text-white/40">{label}</p>
      <textarea
        rows={rows ?? 2}
        value={value}
        disabled={locked}
        onChange={(e) => onChange(e.target.value)}
        className={`field resize-none text-sm disabled:opacity-60 ${rtl ? "rtl" : ""}`}
      />
    </div>
  );
}

function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-white/45">
      {children}
    </h4>
  );
}
