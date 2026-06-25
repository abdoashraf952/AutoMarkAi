"use client";

import { useState } from "react";
import { motion } from "framer-motion";

const PRESETS = [100, 500, 1000, 5000];

export default function BudgetInput({ onSubmit }: { onSubmit: (n: number) => void }) {
  const [value, setValue] = useState("");
  const num = parseFloat(value);
  const valid = !isNaN(num) && num >= 1;

  return (
    <div className="w-full space-y-3">
      <div className="flex flex-wrap gap-2">
        {PRESETS.map((p) => (
          <motion.button
            key={p}
            whileTap={{ scale: 0.95 }}
            onClick={() => onSubmit(p)}
            className="chip hover:border-accent-violet/60 hover:text-white"
          >
            ${p.toLocaleString()}
          </motion.button>
        ))}
      </div>
      <div className="flex items-end gap-2">
        <div className="relative flex-1">
          <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-white/40">
            $
          </span>
          <input
            type="number"
            min={1}
            step={50}
            value={value}
            placeholder="Custom amount"
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && valid) onSubmit(num);
            }}
            className="field pl-8"
          />
        </div>
        <button
          disabled={!valid}
          onClick={() => valid && onSubmit(num)}
          className="btn-primary !py-3"
        >
          Set budget
        </button>
      </div>
    </div>
  );
}
