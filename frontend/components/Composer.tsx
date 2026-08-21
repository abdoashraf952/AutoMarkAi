"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { CampaignChat } from "@/hooks/useCampaignChat";
import { t } from "@/lib/copy";
import type { QuestionOption } from "@/lib/types";
import LoadingArt from "./LoadingArt";
import OptionCards from "./steps/OptionCards";
import ImageUpload from "./steps/ImageUpload";
import FileUploadStep from "./steps/FileUploadStep";
import BudgetInput from "./steps/BudgetInput";
import TextSend from "./steps/TextSend";
import CampaignTargetCards from "./steps/CampaignTargetCards";
import QuestionWithOptions from "./steps/QuestionWithOptions";
import PhotoSelectGrid from "./steps/PhotoSelectGrid";
import ApprovalModeCards from "./steps/ApprovalModeCards";
import ApprovalCard from "./steps/ApprovalCard";
import CampaignReportCard from "./steps/CampaignReportCard";

/**
 * The docked, context-aware input area. Renders exactly the control the current
 * conversational phase needs — nothing more.
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

    case "mode":
      return (
        <ApprovalModeCards
          onPick={chat.setApprovalMode}
          lang={lang}
        />
      );

    case "image":
      return (
        <ImageUpload
          onSelect={chat.setImages}
          label={tr("askUnitPhotos")}
          invalidMsg={tr("imageInvalid")}
          doneLabel={tr("confirmSelection")}
          rtl={rtl}
        />
      );

    case "file_uploads":
      return (
        <FileUploadStep
          title={tr(chat.assetStep.titleKey)}
          why={tr(chat.assetStep.whyKey)}
          required={chat.assetStep.required}
          skipLabel={tr("fileSkip")}
          onSelect={chat.uploadAssetFile}
          onSkip={chat.skipAsset}
          rtl={rtl}
        />
      );

    case "budget":
      return <BudgetInput onSubmit={chat.setBudget} />;

    case "campaign_target":
      return (
        <CampaignTargetCards
          options={chat.targetOptions}
          onPick={chat.chooseTarget}
          lang={lang}
        />
      );

    case "questions": {
      const q = chat.currentQuestion;
      const type = q?.question_type ?? "free_text";
      if (type === "free_text" || !q?.options) {
        return (
          <TextSend
            placeholder={tr("otherPlaceholder")}
            sendLabel={tr("submitAnswer")}
            onSend={(text) => chat.answerQuestion(text)}
            rtl={rtl}
            autoFocusKey={`${q?.index ?? 0}-${q?.is_follow_up ? "f" : "q"}`}
          />
        );
      }
      return (
        <QuestionWithOptions
          options={q.options as QuestionOption[]}
          multi={type === "multi_select_with_other"}
          onSubmit={(answer, label) => chat.answerQuestion(answer, label)}
          lang={lang}
        />
      );
    }

    case "photo_select":
      return (
        <PhotoSelectGrid
          images={chat.photoImages}
          confirmLabel={tr("confirmPhotos")}
          onConfirm={chat.confirmPhotos}
          rtl={rtl}
        />
      );

    case "text_review":
      return <p className="text-center text-sm text-white/55">{tr("pickEditHint")}</p>;

    case "approval_queue":
      return (
        <ApprovalCard
          description={undefined}
          onApprove={chat.approveGate}
          onReject={chat.rejectGate}
          lang={lang}
        />
      );

    case "done":
      return (
        <button onClick={chat.doPublish} className="btn-primary w-full text-base">
          🚀 {tr("publishBtn")}
        </button>
      );

    // Phase 4: operate loop — show campaign report after publish
    case "operate":
      return (
        <CampaignReportCard
          report={chat.campaignReport!}
          lang={lang}
          onTriggerOperate={chat.triggerOperate}
          operating={chat.operateRunning}
        />
      );

    case "published":
      return (
        <div className="flex flex-wrap gap-2.5">
          <button onClick={() => onEnd?.()} className="btn-primary flex-1">
            🏠 {rtl ? "العودة للرئيسية" : "Return to Home"}
          </button>
          <button onClick={chat.restart} className="btn-ghost flex-1">
            ✦ {tr("newCampaign")}
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
