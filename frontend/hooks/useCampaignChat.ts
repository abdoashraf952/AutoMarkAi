"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import * as api from "@/lib/api";
import { toDataUrl } from "@/lib/api";
import { CopyKey, t } from "@/lib/copy";
import { openStream, StreamHandle } from "@/lib/sse";
import type {
  ApprovalMode,
  AssetType,
  CampaignBundle,
  InterruptData,
  Language,
  PublishResult,
  StageResponse,
  TargetOption,
} from "@/lib/types";

// ------------------------------------------------------------------ //
// Fine-grained conversational phases (distinct from backend stages).  //
// ------------------------------------------------------------------ //
export type ChatPhase =
  | "language"
  | "mode"            // Phase 1: approval-mode selector (after language, before photos)
  | "image"
  | "file_uploads"
  | "budget"
  | "starting"
  | "campaign_target"
  | "questions"
  | "building"
  | "photo_select"
  | "text_review"
  | "approval_queue"  // Phase 1: Approval Gateway — waiting for user decision
  | "done"
  | "publishing"
  | "published"
  | "error";

export type LoaderKind = "analyze" | "build" | "image" | "publish";

export type MessageKind =
  | "text"
  | "user-image"
  | "image-grid"
  | "copy-card"
  | "done-card"
  | "publish-card";

export interface ChatMessage {
  id: string;
  role: "bot" | "user";
  kind: MessageKind;
  text?: string;
  imageSrc?: string;
  imageCaption?: string;
  images?: string[]; // data URLs (image-grid)
  hasOriginal?: boolean;
  copy?: { copies: string[]; headlines: string[]; cta: string };
  bundle?: CampaignBundle;
  finalImage?: string;
  publish?: { result: PublishResult | null; error: string | null; sim: boolean };
}

export interface LoadingState {
  active: boolean;
  kind: LoaderKind;
  caption: string;
}

// Sequential client-asset upload steps (CHANGE 4). Logo is required.
export interface AssetStep {
  type: AssetType;
  required: boolean;
  titleKey: CopyKey;
  whyKey: CopyKey;
}
export const ASSET_STEPS: AssetStep[] = [
  { type: "logo", required: true, titleKey: "askLogo", whyKey: "logoWhy" },
  { type: "brochure", required: false, titleKey: "askBrochure", whyKey: "brochureWhy" },
  { type: "floor_plans", required: false, titleKey: "askFloorPlans", whyKey: "floorPlansWhy" },
  { type: "master_plan", required: false, titleKey: "askMasterPlan", whyKey: "masterPlanWhy" },
  { type: "price_list", required: false, titleKey: "askPriceList", whyKey: "priceListWhy" },
];

const PROGRESS_CAPTION: Record<string, string> = {
  questions_ready: "Compound details captured",
  planning: "Campaign plan locked in",
  creative: "Writing your ad copy",
  media_buying: "Crafting your media-buying strategy",
  bundle_ready: "Assembling your campaign",
};

export function useCampaignChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [phase, setPhase] = useState<ChatPhase>("language");
  const [lang, setLang] = useState<Language>("en");
  const [loading, setLoading] = useState<LoadingState>({ active: false, kind: "analyze", caption: "" });
  const [error, setError] = useState<string | null>(null);

  // Phase 1: approval mode — "guided" is the recommended default for new users.
  const [approvalMode, setApprovalModeState] = useState<ApprovalMode>("guided");

  // setup collection
  const setupRef = useRef<Partial<{ budget: number; imageFiles: File[]; approvalMode: ApprovalMode }>>({
    approvalMode: "guided",
  });

  // campaign-target (the one fixed question — AI-ranked options)
  const [targetOptions, setTargetOptions] = useState<TargetOption[]>([]);

  // real estate interview — the current question payload
  const [currentQuestion, setCurrentQuestion] = useState<InterruptData | null>(null);

  // file uploads — which asset step we're on
  const [assetIndex, setAssetIndex] = useState(0);

  // photo selection — the uploaded photos to choose from
  const [photoImages, setPhotoImages] = useState<string[]>([]);

  // session
  const sessionRef = useRef<string | null>(null);
  const streamRef = useRef<StreamHandle | null>(null);
  const idRef = useRef(0);
  const bootedRef = useRef(false);

  const nextId = () => `m${idRef.current++}`;
  const pushMsg = useCallback((m: Omit<ChatMessage, "id">) => {
    setMessages((prev) => [...prev, { id: nextId(), ...m }]);
  }, []);
  const botText = useCallback((text: string) => pushMsg({ role: "bot", kind: "text", text }), [pushMsg]);
  const userText = useCallback((text: string) => pushMsg({ role: "user", kind: "text", text }), [pushMsg]);
  const tr = useCallback((key: CopyKey, vars?: Record<string, string | number>) => t(lang, key, vars), [lang]);

  // ---------------------------------------------------------------- //
  // Boot — greet + ask language                                       //
  // ---------------------------------------------------------------- //
  useEffect(() => {
    if (bootedRef.current) return;
    bootedRef.current = true;
    botText(t("en", "greeting"));
    botText(t("en", "askLanguage"));
    return () => {
      streamRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fail = useCallback(
    (e: unknown) => {
      const msg = e instanceof Error ? e.message : String(e);
      setLoading((l) => ({ ...l, active: false }));
      setError(msg);
      pushMsg({ role: "bot", kind: "text", text: `⚠️ Something went wrong: ${msg}` });
      setPhase("error");
    },
    [pushMsg]
  );

  const startLoading = useCallback((kind: LoaderKind, caption: string) => {
    setLoading({ active: true, kind, caption });
  }, []);
  const stopLoading = useCallback(() => setLoading((l) => ({ ...l, active: false })), []);

  // ---------------------------------------------------------------- //
  // Central stage-response handler (post-interview stages)            //
  // ---------------------------------------------------------------- //
  const handleStage = useCallback(
    async (resp: StageResponse) => {
      const sid = sessionRef.current!;
      const stage = resp.stage;

      if (stage === "approval") {
        // Phase 1: Approval Gateway — show the pending item and wait for user action.
        stopLoading();
        botText(tr("approvalQueueTitle"));
        setPhase("approval_queue");
        return;
      }

      if (stage === "photo_select") {
        const imgs = await api.getImages(sid);
        stopLoading();
        setPhotoImages(imgs.images.map((i) => toDataUrl(i.data)));
        botText(tr("photoSelectIntro"));
        setPhase("photo_select");
        return;
      }

      if (stage === "text_review") {
        stopLoading();
        botText(tr("textReviewPickIntro"));
        pushMsg({
          role: "bot",
          kind: "copy-card",
          copy: {
            copies: resp.data.copies || [],
            headlines: resp.data.headlines || [],
            cta: resp.data.cta || "",
          },
        });
        setPhase("text_review");
        return;
      }

      if (stage === "done") {
        const [result, imgs] = await Promise.all([api.getResult(sid), api.getImages(sid)]);
        const finalImage = imgs.images[0] ? toDataUrl(imgs.images[0].data) : "";
        stopLoading();
        botText(tr("doneIntro"));
        pushMsg({ role: "bot", kind: "done-card", bundle: result.bundle, finalImage });
        setPhase("done");
        return;
      }
    },
    [botText, pushMsg, stopLoading, tr]
  );

  const handleQuestionsOrStage = useCallback(
    async (resp: StageResponse) => {
      if (resp.stage === "questions") {
        stopLoading();
        setCurrentQuestion(resp.data);
        const idx = resp.data.index ?? 0;
        const total = resp.data.total_fixed ?? 8;
        const header = resp.data.is_follow_up
          ? tr("followUpProgress")
          : tr("questionProgress", { n: idx + 1, total });
        botText(`**${header}**\n\n${resp.data.question ?? ""}`);
        setPhase("questions");
      } else {
        setLoading((l) => ({ ...l, kind: "build", caption: tr("buildingCampaign") }));
        await handleStage(resp);
      }
    },
    [botText, handleStage, stopLoading, tr]
  );

  // ---------------------------------------------------------------- //
  // Setup steps                                                       //
  // ---------------------------------------------------------------- //
  const chooseLanguage = useCallback(
    (l: Language) => {
      setLang(l);
      userText(l === "ar" ? "العربية (مصري)" : "English");
      setTimeout(() => {
        botText(t(l, "askApprovalMode"));
        setPhase("mode");
      }, 250);
    },
    [botText, userText]
  );

  const setApprovalMode = useCallback(
    (mode: ApprovalMode, label: string) => {
      setApprovalModeState(mode);
      setupRef.current.approvalMode = mode;
      userText(label);
      setTimeout(() => {
        botText(t(lang, "askUnitPhotos"));
        setPhase("image");
      }, 250);
    },
    [botText, lang, userText]
  );

  // Multiple unit photos uploaded. Create the session now so client assets can
  // be uploaded during the file-uploads phase that follows.
  const setImages = useCallback(
    async (files: File[]) => {
      if (!files.length) return;
      setupRef.current.imageFiles = files;
      pushMsg({ role: "user", kind: "image-grid", images: files.map((f) => URL.createObjectURL(f)) });
      try {
        const session = await api.createSession();
        sessionRef.current = session.session_id;
        streamRef.current = openStream(session.session_id, (ev) => {
          if (ev.event === "progress" && ev.stage && PROGRESS_CAPTION[ev.stage]) {
            setLoading((l) => (l.active ? { ...l, caption: PROGRESS_CAPTION[ev.stage!] } : l));
          }
        });
      } catch (e) {
        fail(e);
        return;
      }
      setAssetIndex(0);
      botText(tr("uploadsIntro"));
      setPhase("file_uploads");
    },
    [botText, fail, pushMsg, tr]
  );

  // file_uploads — advance through ASSET_STEPS; on the last, go to budget.
  const advanceAsset = useCallback(() => {
    setAssetIndex((i) => {
      const next = i + 1;
      if (next >= ASSET_STEPS.length) {
        botText(tr("askBudget"));
        setPhase("budget");
        return i;
      }
      return next;
    });
  }, [botText, tr]);

  const uploadAssetFile = useCallback(
    async (file: File) => {
      const step = ASSET_STEPS[assetIndex];
      pushMsg({ role: "user", kind: "user-image", imageSrc: URL.createObjectURL(file) });
      try {
        await api.uploadAsset(sessionRef.current!, step.type, file);
      } catch (e) {
        fail(e);
        return;
      }
      advanceAsset();
    },
    [advanceAsset, assetIndex, fail, pushMsg]
  );

  const skipAsset = useCallback(() => {
    userText(tr("fileSkip"));
    advanceAsset();
  }, [advanceAsset, tr, userText]);

  // After the budget we kick off the pipeline; the first interrupt is the
  // AI-ranked campaign-target question.
  const beginPipeline = useCallback(async () => {
    const s = setupRef.current;
    if (!s.budget || !s.imageFiles?.length || !sessionRef.current) return;
    setPhase("starting");
    startLoading("analyze", "Taking a look at your units…");
    try {
      const resp = await api.startSession(sessionRef.current, {
        budget: s.budget,
        language: lang,
        imageFiles: s.imageFiles,
        approvalMode: s.approvalMode ?? "full_manual",
      });
      stopLoading();
      if (resp.stage === "campaign_target") {
        // full_manual: user picks the campaign goal
        setTargetOptions((resp.data.options as TargetOption[]) ?? []);
        botText(tr("askTarget"));
        setPhase("campaign_target");
      } else {
        // guided / autopilot: goal was auto-picked, jump straight to interview
        botText(tr("questionsIntro"));
        await handleQuestionsOrStage(resp);
      }
    } catch (e) {
      fail(e);
    }
  }, [botText, fail, handleQuestionsOrStage, lang, startLoading, stopLoading, tr]);

  const setBudget = useCallback(
    (n: number) => {
      setupRef.current.budget = n;
      userText(`$${n.toLocaleString()}`);
      void beginPipeline();
    },
    [beginPipeline, userText]
  );

  // ---------------------------------------------------------------- //
  // Campaign target → real estate interview                          //
  // ---------------------------------------------------------------- //
  const chooseTarget = useCallback(
    async (goal: string, label: string) => {
      userText(label);
      setTargetOptions([]);
      setPhase("building");
      startLoading("analyze", tr("thinkingNextQ"));
      try {
        const resp = await api.submitAnswer(sessionRef.current!, goal);
        botText(tr("questionsIntro"));
        await handleQuestionsOrStage(resp);
      } catch (e) {
        fail(e);
      }
    },
    [botText, fail, handleQuestionsOrStage, startLoading, tr, userText]
  );

  // ---------------------------------------------------------------- //
  // Questions — one at a time (free text / single / multi select)     //
  // ---------------------------------------------------------------- //
  const answerQuestion = useCallback(
    async (answer: string, displayLabel?: string) => {
      userText(displayLabel ?? answer);
      setCurrentQuestion(null);
      setPhase("building");
      startLoading("analyze", tr("thinkingNextQ"));
      try {
        const resp = await api.submitAnswer(sessionRef.current!, answer);
        await handleQuestionsOrStage(resp);
      } catch (e) {
        fail(e);
      }
    },
    [fail, handleQuestionsOrStage, startLoading, tr, userText]
  );

  // ---------------------------------------------------------------- //
  // Photo selection                                                   //
  // ---------------------------------------------------------------- //
  const confirmPhotos = useCallback(
    async (indices: number[]) => {
      userText(tr("confirmPhotos"));
      setPhase("building");
      startLoading("build", tr("buildingCampaign"));
      try {
        const resp = await api.selectPhotos(sessionRef.current!, indices);
        await handleStage(resp);
      } catch (e) {
        fail(e);
      }
    },
    [fail, handleStage, startLoading, tr, userText]
  );

  // ---------------------------------------------------------------- //
  // Text review                                                       //
  // ---------------------------------------------------------------- //
  const submitText = useCallback(
    async (copyIndex: number, headlineIndex: number, copyText: string, headlineText: string) => {
      userText(tr("confirmSelection"));
      setPhase("building");
      startLoading("build", "Finalizing your campaign…");
      try {
        const resp = await api.textDecision(sessionRef.current!, {
          copy_index: copyIndex,
          headline_index: headlineIndex,
          copy_text: copyText,
          headline_text: headlineText,
        });
        await handleStage(resp);
      } catch (e) {
        fail(e);
      }
    },
    [fail, handleStage, startLoading, tr, userText]
  );

  // ---------------------------------------------------------------- //
  // Approval Gateway — resolve a pending approval gate               //
  // ---------------------------------------------------------------- //
  const approveGate = useCallback(async () => {
    userText(tr("approveBtn"));
    setPhase("building");
    startLoading("build", tr("buildingCampaign"));
    try {
      const resp = await api.submitAnswer(sessionRef.current!, "approved");
      await handleStage(resp);
    } catch (e) {
      fail(e);
    }
  }, [fail, handleStage, startLoading, tr, userText]);

  const rejectGate = useCallback(async (feedback: string) => {
    userText(feedback || tr("rejectBtn"));
    setPhase("building");
    startLoading("build", tr("buildingCampaign"));
    try {
      const resp = await api.submitAnswer(sessionRef.current!, `rejected: ${feedback}`);
      await handleStage(resp);
    } catch (e) {
      fail(e);
    }
  }, [fail, handleStage, startLoading, tr, userText]);

  // ---------------------------------------------------------------- //
  // Publish                                                           //
  // ---------------------------------------------------------------- //
  const doPublish = useCallback(async () => {
    userText(tr("publishBtn"));
    setPhase("publishing");
    startLoading("publish", tr("publishing"));
    try {
      const res = await api.publish(sessionRef.current!);
      stopLoading();
      pushMsg({
        role: "bot",
        kind: "publish-card",
        publish: { result: res.result, error: res.errors?.join("\n") || null, sim: res.simulation_mode },
      });
      botText(res.simulation_mode ? tr("publishedSim") : tr("publishedLive"));
      botText(tr("startOver"));
      setPhase("published");
    } catch (e) {
      fail(e);
    }
  }, [botText, fail, pushMsg, startLoading, stopLoading, tr, userText]);

  // ---------------------------------------------------------------- //
  // Restart                                                           //
  // ---------------------------------------------------------------- //
  const restart = useCallback(() => {
    streamRef.current?.close();
    streamRef.current = null;
    sessionRef.current = null;
    setupRef.current = { approvalMode: "guided" };
    idRef.current = 0;
    setMessages([]);
    setTargetOptions([]);
    setCurrentQuestion(null);
    setAssetIndex(0);
    setPhotoImages([]);
    setError(null);
    setLoading({ active: false, kind: "analyze", caption: "" });
    setApprovalModeState("guided");
    setLang("en");
    setPhase("language");
    botText(t("en", "greeting"));
    botText(t("en", "askLanguage"));
  }, [botText]);

  return {
    messages,
    phase,
    lang,
    loading,
    error,
    // setup
    chooseLanguage,
    setImages,
    // approval mode (Phase 1)
    approvalMode,
    setApprovalMode,
    // file uploads
    assetStep: ASSET_STEPS[assetIndex],
    uploadAssetFile,
    skipAsset,
    setBudget,
    // campaign target
    targetOptions,
    chooseTarget,
    // questions
    currentQuestion,
    answerQuestion,
    // photo select
    photoImages,
    confirmPhotos,
    // text review
    submitText,
    // approval queue (Phase 1)
    approveGate,
    rejectGate,
    // publish
    doPublish,
    restart,
  };
}

export type CampaignChat = ReturnType<typeof useCampaignChat>;
