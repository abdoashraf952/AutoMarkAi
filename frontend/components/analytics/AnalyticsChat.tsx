"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { askQuestion } from "@/lib/analytics";
import type { AnalyticsChatMessage } from "@/lib/analytics";
import MarkdownLite from "@/components/MarkdownLite";
import { EmptyState } from "./ui";

const SUGGESTIONS = [
  "What is the single biggest risk in this data?",
  "Which KPI should we improve first, and why?",
  "Summarise the trend over time.",
  "Which segment underperforms the most?",
];

export default function AnalyticsChat({ sessionId }: { sessionId: string }) {
  const [messages, setMessages] = useState<AnalyticsChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const send = async (text: string) => {
    const query = text.trim();
    if (!query || busy) return;

    setError(null);
    setDraft("");
    setMessages((m) => [...m, { role: "user", content: query }]);
    setBusy(true);

    try {
      const res = await askQuestion(sessionId, query);
      setMessages((m) => [...m, { role: "assistant", content: res.answer || "—" }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setError((prev) => prev);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-[60vh] flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto pr-2">
        {!messages.length && (
          <div className="space-y-4">
            <EmptyState>Ask a question about this dataset.</EmptyState>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full px-3 py-1.5 text-[12px] transition-colors"
                  style={{
                    background: "rgba(255,255,255,0.05)",
                    border: "1px solid rgba(255,255,255,0.09)",
                    color: "rgba(255,255,255,0.6)",
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => {
          const mine = m.role === "user";
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${mine ? "justify-end" : "justify-start"}`}
            >
              <div
                className="max-w-[80%] rounded-2xl px-4 py-2.5 text-[13.5px] leading-relaxed"
                style={
                  mine
                    ? {
                        background: "linear-gradient(135deg, #B8860B 0%, #C9A84C 100%)",
                        color: "#1a1408",
                      }
                    : {
                        background: "rgba(255,255,255,0.06)",
                        border: "1px solid rgba(255,255,255,0.09)",
                        color: "rgba(232,234,245,0.82)",
                      }
                }
              >
                <MarkdownLite text={m.content} />
              </div>
            </motion.div>
          );
        })}

        {busy && (
          <div className="flex justify-start">
            <div
              className="rounded-2xl px-4 py-3"
              style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.09)" }}
            >
              <div className="flex gap-1.5">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="h-1.5 w-1.5 animate-pulse rounded-full"
                    style={{ background: "#C9A84C", animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        {error && (
          <div
            className="rounded-xl px-4 py-3 text-sm"
            style={{
              background: "rgba(227,73,72,0.12)",
              border: "1px solid rgba(227,73,72,0.3)",
              color: "rgba(255,255,255,0.75)",
            }}
          >
            {error}
          </div>
        )}

        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(draft);
        }}
        className="mt-4 flex items-center gap-2"
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask about this dataset…"
          disabled={busy}
          className="flex-1 rounded-2xl px-4 py-3 text-sm outline-none transition-colors placeholder:text-white/25 disabled:opacity-50"
          style={{
            background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.1)",
            color: "#e8eaf5",
          }}
        />
        <button
          type="submit"
          disabled={busy || !draft.trim()}
          className="rounded-2xl px-5 py-3 text-[12px] font-bold uppercase tracking-wider transition-transform hover:scale-[1.03] disabled:opacity-40 disabled:hover:scale-100"
          style={{
            background: "linear-gradient(135deg, #B8860B 0%, #C9A84C 45%, #E8C97A 100%)",
            color: "#1a1408",
          }}
        >
          Ask
        </button>
      </form>
    </div>
  );
}
