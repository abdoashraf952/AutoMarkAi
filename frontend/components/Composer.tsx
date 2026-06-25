"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { CampaignChat } from "@/hooks/useCampaignChat";
import { MARKETING_TYPE_OPTIONS, t } from "@/lib/copy";
import LoadingArt from "./LoadingArt";
import OptionCards from "./steps/OptionCards";
import ImageUpload from "./steps/ImageUpload";
import BudgetInput from "./steps/BudgetInput";
import TextSend from "./steps/TextSend";
import ReviewActions from "./steps/ReviewActions";

/**
 * The docked, context-aware input area. It renders exactly the control the
 * current conversational phase needs — nothing more. This is what makes the
 * flow feel like a guided chat instead of a giant form.
 */
export default function Composer({
  chat,
  onEnd,
}: {
  chat: CampaignChat;
  onEnd?: () => void;
}) {
  const { phase, lang, loading } = chat;
  const rtl = lang === "ar";

  return (
    <div className={`w-full ${rtl ? "rtl" : ""}`}>
      <AnimatePresence mode="wait">
        {loading.active ? (
          <motion.div key="loading" exit={{ opacity: 0 }}>
            <LoadingArt kind={loading.kind} caption={loading.caption} />
          </motion.div>
        ) : (
          <motion.div
            key={phase}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25 }}
            className="w-full"
          >
            <Control chat={chat} onEnd={onEnd} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Control({ chat, onEnd }: { chat: CampaignChat; onEnd?: () => void }) {
  const { phase, lang } = chat;
  const rtl = lang === "ar";
  const tr = (k: Parameters<typeof t>[1]) => t(lang, k);

  switch (phase) {
    case "language":
      return (
        <OptionCards
          columns={2}
          options={[
            { value: "en", label: "English", emoji: "🇬🇧" },
            { value: "ar", label: "العربية (مصري)", emoji: "🇪🇬" },
          ]}
          onPick={(v) => chat.chooseLanguage(v as "en" | "ar")}
        />
      );

    case "marketing_type":
      return (
        <OptionCards
          options={MARKETING_TYPE_OPTIONS[lang]}
          onPick={(v, label) => chat.chooseMarketingType(v as any, label)}
        />
      );

    case "image":
      return <ImageUpload onSelect={chat.setImage} />;

    case "image_mode":
      return (
        <OptionCards
          columns={2}
          options={[
            {
              value: "use_original",
              label: tr("useOriginal"),
              sub: rtl ? "صورتك زي ما هي" : "Your photo, as-is",
              emoji: "🖼️",
            },
            {
              value: "enhance_with_ai",
              label: tr("enhanceAI"),
              sub: rtl ? "تحسين بالذكاء الاصطناعي" : "Polished, ad-ready look",
              emoji: "✨",
            },
          ]}
          onPick={(v) => chat.chooseImageMode(v as any)}
        />
      );

    case "budget":
      return <BudgetInput onSubmit={chat.setBudget} />;

    case "goal":
      return (
        <TextSend
          placeholder={tr("goalPlaceholder")}
          sendLabel={tr("send")}
          onSend={chat.setGoal}
          rtl={rtl}
        />
      );

    case "questions":
      return (
        <TextSend
          placeholder={rtl ? "اكتب إجابتك…" : "Type your answer…"}
          sendLabel={tr("submitAnswer")}
          onSend={chat.answerQuestion}
          rtl={rtl}
          autoFocusKey={chat.qIndex}
        />
      );

    case "image_review":
      // Regenerations exhausted: offer "choose from all versions" instead of a
      // misleading regenerate that would never produce a new image.
      if (chat.canRegenerate && chat.remainingRegens <= 0) {
        return (
          <div className="flex flex-wrap gap-2.5">
            <button onClick={chat.approveImage} className="btn-primary flex-1">
              ✓ {tr("approve")}
            </button>
            <button onClick={chat.gatherVersions} className="btn-ghost flex-1">
              🖼️ {tr("seeAllVersions")}
            </button>
          </div>
        );
      }
      return (
        <ReviewActions
          approveLabel={tr("approve")}
          changeLabel={tr("regenerate")}
          feedbackPlaceholder={tr("feedbackPlaceholderImg")}
          onApprove={chat.approveImage}
          onChange={chat.regenerateImage}
          rtl={rtl}
          approveOnly={!chat.canRegenerate}
        />
      );

    case "text_review":
      // Selection + manual edit happens inside the copy card above.
      return <p className="text-center text-sm text-white/55">{tr("pickEditHint")}</p>;

    case "max_regen":
      return <p className="text-center text-sm text-white/55">{tr("pickAbove")}</p>;

    case "done":
      return (
        <button onClick={chat.doPublish} className="btn-primary w-full text-base">
          🚀 {tr("publishBtn")}
        </button>
      );

    case "published":
      return (
        <div className="flex flex-wrap gap-2.5">
          <button onClick={chat.restart} className="btn-primary flex-1">
            ✦ {tr("newCampaign")}
          </button>
          <button onClick={() => onEnd?.()} className="btn-ghost flex-1">
            {tr("endBtn")}
          </button>
        </div>
      );

    case "error":
      return (
        <button onClick={chat.restart} className="btn-primary w-full">
          ↻ {rtl ? "ابدأ من جديد" : "Start over"}
        </button>
      );

    default:
      return null;
  }
}
