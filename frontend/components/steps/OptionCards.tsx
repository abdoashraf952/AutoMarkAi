"use client";

import { motion } from "framer-motion";

export interface Option<T> {
  value: T;
  label: string;
  sub?: string;
  emoji?: string;
}

/** Horizontal/stacked selectable cards used for discrete choices. */
export default function OptionCards<T extends string>({
  options,
  onPick,
  columns = 1,
}: {
  options: Option<T>[];
  onPick: (value: T, label: string) => void;
  columns?: 1 | 2 | 3;
}) {
  const grid =
    columns === 3 ? "sm:grid-cols-3" : columns === 2 ? "sm:grid-cols-2" : "grid-cols-1";
  return (
    <div className={`grid w-full gap-2.5 ${grid}`}>
      {options.map((opt, i) => (
        <motion.button
          key={opt.value}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.05 }}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => onPick(opt.value, opt.label)}
          className="glass group flex items-center gap-3 rounded-2xl px-4 py-3.5 text-left transition-all hover:border-accent-violet/60 hover:shadow-glow"
        >
          {opt.emoji && <span className="text-2xl">{opt.emoji}</span>}
          <span className="flex-1">
            <span className="block text-sm font-semibold text-white">{opt.label}</span>
            {opt.sub && <span className="block text-xs text-white/50">{opt.sub}</span>}
          </span>
          <span className="text-white/30 transition-transform group-hover:translate-x-0.5 group-hover:text-accent-cyan">
            →
          </span>
        </motion.button>
      ))}
    </div>
  );
}
