"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import * as api from "@/lib/api";
import { toDataUrl } from "@/lib/api";
import { CopyKey, t } from "@/lib/copy";
import { openStream, StreamHandle } from "@/lib/sse";
import type {
  CampaignBundle,
  ImageMode,
  Language,
  MarketingType,
  PublishResult,
  StageResponse,
  TargetOption,
} from "@/lib/types";

// ------------------------------------------------------------------ //
// Fine-grained conversational phases (distinct from backend stages).  //
// ------------------------------------------------------------------ //
export type ChatPhase =
  | "language"
  | "marketing_type"
  | "image"
  | "image_mode"
  | "describe"
  | "budget"
  | "starting"
  | "campaign_target"
  | "questions"
  | "building"
  | "image_review"
  | "image_regenerating"
  | "max_regen"
  | "text_review"
  | "text_editing"
  | "done"
  | "publishing"
  | "published"
  | "error";

export type LoaderKind = "analyze" | "build" | "image" | "publish";

export type MessageKind =
  | "text"
  | "user-image"
  | "image-card"
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
  hasOriginal?: boolean; // image-grid: first tile is the user's original photo
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

const PROGRESS_CAPTION: Record<string, string> = {
  questions_ready: "Questions ready",
  planning: "Campaign plan locked in",
  creative: "Writing your ad copy & visuals",
  media_buying: "Crafting your media-buying strategy",
  bundle_ready: "Assembling your campaign",
};

export function useCampaignChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [phase, setPhase] = useState<ChatPhase>("language");
  const [lang, setLang] = useState<Language>("en");
  const [loading, setLoading] = useState<LoadingState>({
    active: false,
    kind: "analyze",
    caption: "",
  });
  const [error, setError] = useState<string | null>(null);

  // setup collection
  const setupRef = useRef<Partial<{
    marketingType: MarketingType;
    imageMode: ImageMode;
    budget: number;
    imageFile: File;
    description: string;
  }>>({});

  // campaign-target (the one fixed question — AI-ranked options)
  const [targetOptions, setTargetOptions] = useState<TargetOption[]>([]);

  // questions (adaptive — one at a time, dynamic count, generated server-side)
  const [qIndex, setQIndex] = useState(0);

  // image review meta
  const [canRegenerate, setCanRegenerate] = useState(true);
  const [imageMeta, setImageMeta] = useState({ regenCount: 0, maxRegens: 2 });

  // session
  const sessionRef = useRef<string | null>(null);
  const streamRef = useRef<StreamHandle | null>(null);
  const idRef = useRef(0);
  const bootedRef = useRef(false);

  const nextId = () => `m${idRef.current++}`;

  const pushMsg = useCallback((m: Omit<ChatMessage, "id">) => {
    setMessages((prev) => [...prev, { id: nextId(), ...m }]);
  }, []);

  const botText = useCallback(
    (text: string) => pushMsg({ role: "bot", kind: "text", text }),
    [pushMsg]
  );
  const userText = useCallback(
    (text: string) => pushMsg({ role: "user", kind: "text", text }),
    [pushMsg]
  );

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
  // Central stage-response handler                                    //
  // ---------------------------------------------------------------- //
  const handleStage = useCallback(
    async (resp: StageResponse) => {
      const sid = sessionRef.current!;
      const stage = resp.stage;

      if (stage === "image_review") {
        const can = resp.data.can_regenerate !== false;
        const regenCount = resp.data.regen_count ?? 0;
        const maxRegens = resp.data.max_regens ?? 2;
        setCanRegenerate(can);
        setImageMeta({ regenCount, maxRegens });
        const imgs = await api.getImages(sid);
        const src = imgs.images[0] ? toDataUrl(imgs.images[0].data) : "";
        stopLoading();
        const remaining = maxRegens - regenCount;
        botText(can ? tr("imageReviewIntro") : tr("imageConfirmIntro"));
        if (can && regenCount > 0) {
          botText(
            remaining > 0
              ? tr("regensLeft", { n: remaining })
              : tr("regensNoneLeft")
          );
        }
        const generated = setupRef.current.imageMode === "generate_with_ai";
        pushMsg({
          role: "bot",
          kind: "image-card",
          imageSrc: src,
          imageCaption: generated
            ? tr("aiCreatedImage")
            : can
            ? tr("enhancedImage")
            : tr("yourPhoto"),
        });
        setPhase("image_review");
        return;
      }

      if (stage === "max_regenerations_exceeded") {
        const imgs = await api.getImages(sid);
        stopLoading();
        botText(tr("maxRegenIntro"));
        pushMsg({
          role: "bot",
          kind: "image-grid",
          images: imgs.images.map((i) => toDataUrl(i.data)),
          hasOriginal: resp.data.has_original === true,
        });
        setPhase("max_regen");
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
        const [result, imgs] = await Promise.all([
          api.getResult(sid),
          api.getImages(sid),
        ]);
        const finalImage = imgs.images[0] ? toDataUrl(imgs.images[0].data) : "";
        stopLoading();
        botText(tr("doneIntro"));
        pushMsg({
          role: "bot",
          kind: "done-card",
          bundle: result.bundle,
          finalImage,
        });
        setPhase("done");
        return;
      }

      // questions stage handled by caller (start)
    },
    [botText, pushMsg, stopLoading, tr]
  );

  // ---------------------------------------------------------------- //
  // Setup steps                                                       //
  // ---------------------------------------------------------------- //
  const chooseLanguage = useCallback(
    (l: Language) => {
      setLang(l);
      userText(l === "ar" ? "العربية (مصري)" : "English");
      setTimeout(() => {
        botText(t(l, "askMarketingType"));
        setPhase("marketing_type");
      }, 250);
    },
    [botText, userText]
  );

  const chooseMarketingType = useCallback(
    (mt: MarketingType, label: string) => {
      setupRef.current.marketingType = mt;
      userText(label);
      botText(tr("askImage"));
      setPhase("image");
    },
    [botText, tr, userText]
  );

  const setImage = useCallback(
    (file: File) => {
      setupRef.current.imageFile = file;
      const src = URL.createObjectURL(file);
      pushMsg({ role: "user", kind: "user-image", imageSrc: src });
      botText(tr("askImageMode"));
      setPhase("image_mode");
    },
    [botText, pushMsg, tr]
  );

  // Skip the (optional) photo upload — AI will generate the visual instead.
  // Since there's no image, we first ask the owner to describe what they're
  // promoting so the target, questions, and plan are grounded in real info.
  const skipImage = useCallback(() => {
    setupRef.current.imageFile = undefined;
    setupRef.current.imageMode = "generate_with_ai";
    userText(tr("skipImage"));
    botText(tr("askDescribe"));
    setPhase("describe");
  }, [botText, tr, userText]);

  const setDescription = useCallback(
    (text: string) => {
      setupRef.current.description = text;
      userText(text);
      botText(tr("askBudget"));
      setPhase("budget");
    },
    [botText, tr, userText]
  );

  const chooseImageMode = useCallback(
    (mode: ImageMode) => {
      setupRef.current.imageMode = mode;
      userText(mode === "use_original" ? tr("useOriginal") : tr("enhanceAI"));
      botText(tr("askBudget"));
      setPhase("budget");
    },
    [botText, tr, userText]
  );

  // After the budget we kick off the pipeline; the first interrupt is the
  // AI-ranked campaign-target question (the one fixed question).
  const beginPipeline = useCallback(async () => {
    const s = setupRef.current;
    if (!s.budget || !s.marketingType || !s.imageMode) return;
    setPhase("starting");
    startLoading("analyze", "Taking a look…");
    try {
      const session = await api.createSession();
      sessionRef.current = session.session_id;

      // Live progress captions while the blocking call runs.
      streamRef.current = openStream(session.session_id, (ev) => {
        if (ev.event === "progress" && ev.stage && PROGRESS_CAPTION[ev.stage]) {
          setLoading((l) => (l.active ? { ...l, caption: PROGRESS_CAPTION[ev.stage!] } : l));
        }
      });

      const resp = await api.startSession(session.session_id, {
        budget: s.budget,
        imageMode: s.imageMode,
        marketingType: s.marketingType,
        language: lang,
        imageFile: s.imageFile,
        description: s.description,
      });

      // First interrupt: the ranked campaign-target options.
      stopLoading();
      setTargetOptions(resp.data.options ?? []);
      botText(tr("askTarget"));
      setPhase("campaign_target");
    } catch (e) {
      fail(e);
    }
  }, [botText, fail, lang, startLoading, stopLoading, tr]);

  const setBudget = useCallback(
    (n: number) => {
      setupRef.current.budget = n;
      userText(`$${n.toLocaleString()}`);
      void beginPipeline();
    },
    [beginPipeline, userText]
  );

  // ---------------------------------------------------------------- //
  // Campaign target — the fixed question, then the adaptive interview //
  // ---------------------------------------------------------------- //
  const showFirstQuestionOrAdvance = useCallback(
    async (resp: StageResponse) => {
      if (resp.stage === "questions") {
        const idx = resp.data.index ?? 0;
        stopLoading();
        setQIndex(idx);
        botText(tr("questionsIntro"));
        botText(`**${tr("questionProgress", { n: idx + 1 })}**\n\n${resp.data.question ?? ""}`);
        setPhase("questions");
      } else {
        await handleStage(resp);
      }
    },
    [botText, handleStage, stopLoading, tr]
  );

  const chooseTarget = useCallback(
    async (goal: string, label: string) => {
      userText(label);
      setTargetOptions([]);
      setPhase("building");
      startLoading("analyze", tr("thinkingNextQ"));
      try {
        const resp = await api.submitAnswer(sessionRef.current!, goal);
        await showFirstQuestionOrAdvance(resp);
      } catch (e) {
        fail(e);
      }
    },
    [fail, showFirstQuestionOrAdvance, startLoading, tr, userText]
  );

  // ---------------------------------------------------------------- //
  // Questions — one at a time, dynamic count                          //
  // ---------------------------------------------------------------- //
  const answerQuestion = useCallback(
    async (text: string) => {
      userText(text);
      setPhase("building");
      // We don't know if this is the last question (dynamic), so use a neutral
      // caption; if the interview ends, the build/image loader takes over.
      startLoading("analyze", tr("thinkingNextQ"));
      try {
        const resp = await api.submitAnswer(sessionRef.current!, text);
        if (resp.stage === "questions") {
          // Backend generated the next adaptive question.
          const idx = resp.data.index ?? qIndex + 1;
          stopLoading();
          setQIndex(idx);
          botText(`**${tr("questionProgress", { n: idx + 1 })}**\n\n${resp.data.question ?? ""}`);
          setPhase("questions");
        } else {
          // Interview complete → pipeline moved on (image review, etc.)
          setLoading((l) => ({ ...l, kind: "build", caption: tr("buildingCampaign") }));
          await handleStage(resp);
        }
      } catch (e) {
        fail(e);
      }
    },
    [botText, fail, handleStage, qIndex, startLoading, stopLoading, tr, userText]
  );

  // ---------------------------------------------------------------- //
  // Image review                                                      //
  // ---------------------------------------------------------------- //
  const approveImage = useCallback(async () => {
    userText(tr("approve"));
    setPhase("building");
    startLoading("build", "Locking in your visual…");
    try {
      const resp = await api.imageDecision(sessionRef.current!, { action: "approve" });
      await handleStage(resp);
    } catch (e) {
      fail(e);
    }
  }, [fail, handleStage, startLoading, tr, userText]);

  const regenerateImage = useCallback(
    async (feedback: string) => {
      userText(feedback);
      setPhase("image_regenerating");
      startLoading("image", tr("regenerating"));
      try {
        const resp = await api.imageDecision(sessionRef.current!, {
          action: "regenerate",
          approved: [false],
          feedback: { "0": feedback || "regenerate" },
        });
        await handleStage(resp);
      } catch (e) {
        fail(e);
      }
    },
    [fail, handleStage, startLoading, tr, userText]
  );

  // Regenerations exhausted: don't fake another generation — ask the backend
  // for the picker (it returns the full image history to choose from).
  const gatherVersions = useCallback(async () => {
    userText(tr("seeAllVersions"));
    setPhase("building");
    startLoading("build", tr("gatheringVersions"));
    try {
      const resp = await api.imageDecision(sessionRef.current!, {
        action: "show_history",
      });
      await handleStage(resp);
    } catch (e) {
      fail(e);
    }
  }, [fail, handleStage, startLoading, tr, userText]);

  const pickImage = useCallback(
    async (index: number) => {
      userText(`Image ${index + 1}`);
      setPhase("building");
      startLoading("build", "Applying your selection…");
      try {
        const resp = await api.pickImage(sessionRef.current!, index);
        await handleStage(resp);
      } catch (e) {
        fail(e);
      }
    },
    [fail, handleStage, startLoading, userText]
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
    setupRef.current = {};
    idRef.current = 0;
    setMessages([]);
    setQIndex(0);
    setTargetOptions([]);
    setCanRegenerate(true);
    setImageMeta({ regenCount: 0, maxRegens: 2 });
    setError(null);
    setLoading({ active: false, kind: "analyze", caption: "" });
    setLang("en");
    setPhase("language");
    // re-greet
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
    chooseMarketingType,
    setImage,
    skipImage,
    setDescription,
    chooseImageMode,
    setBudget,
    // campaign target
    targetOptions,
    chooseTarget,
    // questions
    qIndex,
    answerQuestion,
    // image review
    canRegenerate,
    remainingRegens: imageMeta.maxRegens - imageMeta.regenCount,
    approveImage,
    regenerateImage,
    gatherVersions,
    pickImage,
    // text review
    submitText,
    // publish
    doPublish,
    restart,
  };
}

export type CampaignChat = ReturnType<typeof useCampaignChat>;
