"use client";

import { useState } from "react";
import type { Language } from "@/lib/types";
import { t } from "@/lib/copy";

/**
 * Approval Queue card — shown when the Approval Gateway interrupts for a
 * plan / creative / money / launch gate (Phase 1).
 *
 * Presents the description of the pending item and two actions:
 *   Approve →   resume the pipeline
 *   Edit        provide feedback and re-run
 */
export default function ApprovalCard({
  description,
  onApprove,
  onReject,
  lang = "en",
}: {
  description?: string;
  onApprove: () => void;
  onReject: (feedback: string) => void;
  lang?: Language;
}) {
  const [editing, setEditing] = useState(false);
  const [feedback, setFeedback] = useState("");
  const rtl = lang === "ar";

  const handleReject = () => {
    onReject(feedback.trim());
    setEditing(false);
    setFeedback("");
  };

  return (
    <div className={`glass rounded-2xl p-4 space-y-3 w-full ${rtl ? "rtl" : ""}`}>
      {description && (
        <p className="text-sm text-white/80 leading-relaxed">{description}</p>
      )}

      {!editing ? (
        <div className="flex gap-2.5">
          <button
            onClick={onApprove}
            className="btn-primary flex-1 text-sm"
          >
            {t(lang, "approveBtn")}
          </button>
          <button
            onClick={() => setEditing(true)}
            className="btn-ghost flex-1 text-sm"
          >
            {t(lang, "rejectBtn")}
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <textarea
            className="w-full rounded-xl bg-white/10 border border-white/20 px-3 py-2
                       text-sm text-white placeholder-white/40 resize-none focus:outline-none
                       focus:ring-1 focus:ring-accent-violet"
            rows={3}
            placeholder={rtl ? "اكتب ملاحظاتك هنا…" : "What should be changed?"}
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            autoFocus
          />
          <div className="flex gap-2">
            <button
              onClick={handleReject}
              disabled={!feedback.trim()}
              className="btn-primary flex-1 text-sm disabled:opacity-40"
            >
              {rtl ? "إرسال الملاحظات" : "Send feedback"}
            </button>
            <button
              onClick={() => { setEditing(false); setFeedback(""); }}
              className="btn-ghost text-sm px-3"
            >
              {rtl ? "إلغاء" : "Cancel"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
