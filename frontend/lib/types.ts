// ------------------------------------------------------------------ //
// Shared types mirroring the FastAPI (api.py) contract.               //
// ------------------------------------------------------------------ //

/** Backend interrupt stages (the `stage` field returned by the API). */
export type BackendStage =
  | "questions"
  | "image_review"
  | "max_regenerations_exceeded"
  | "text_review"
  | "done";

export type MarketingType = "product" | "business" | "service";
export type ImageMode = "use_original" | "enhance_with_ai";
export type Language = "en" | "ar";

/** Common envelope returned by /start, /answers, /image-decision, etc. */
export interface StageResponse {
  stage: BackendStage;
  data: InterruptData;
}

/** _safe_data payloads — images are stripped to placeholder strings. */
export interface InterruptData {
  stage?: BackendStage;
  marketing_type?: MarketingType;
  // questions (adaptive — one at a time)
  question?: string;
  index?: number;
  total?: number;
  questions?: string[]; // legacy/batch (no longer used by the UI)
  // image_review
  images?: string[]; // placeholders like "<image_0>"
  regen_count?: number;
  max_regens?: number;
  can_regenerate?: boolean;
  // max_regenerations_exceeded
  image_history?: string[];
  has_original?: boolean;
  message?: string;
  // text_review
  copies?: string[];
  headlines?: string[];
  cta?: string;
}

export interface SessionResponse {
  session_id: string;
}

export interface ImagesResponse {
  count: number;
  images: { index: number; data: string }[]; // base64 (no data: prefix)
}

export interface SetupData {
  goal: string;
  budget: number;
  imageMode: ImageMode;
  marketingType: MarketingType;
  language: Language;
  imageFile: File;
}

export interface ImageDecisionBody {
  action: "approve" | "regenerate" | "show_history";
  approved?: boolean[];
  feedback?: Record<string, string>;
}

export interface TextDecisionBody {
  copy_index: number;
  headline_index: number;
  copy_text: string;
  headline_text: string;
}

export interface PublishBody {
  make_sponsored_ad: boolean;
  make_organic_post: boolean;
}

// ---- Final bundle (GET /result) ---------------------------------- //

export interface CampaignBundle {
  meta?: { generated_at?: string; llm_used?: Record<string, string>; warnings?: string[] };
  product?: { type?: string; description?: string };
  campaign?: { platform?: string; objective?: string; tone?: string };
  creative?: {
    copies?: string[];
    headlines?: string[];
    cta?: string;
    visual_prompt?: string;
    generated_images_count?: number;
  };
  media?: {
    budget_split?: Record<string, number>;
    daily_budget_usd?: number;
    audience?: {
      age_min?: number;
      age_max?: number;
      genders?: string[];
      interests?: string[];
      locations?: string[];
      income_tier?: string;
    };
    placement?: string[];
    bid_strategy?: string;
    optimization_goal?: string;
    estimated_reach?: { min?: number; max?: number };
    reasoning?: string;
  };
  strategy?: {
    target_persona?: {
      primary_segment?: string;
      archetype?: string;
      gender?: string;
      age_min?: number;
      age_max?: number;
      locations?: string[];
      psychographics?: string[];
      motivations?: string[];
      interests?: string[];
    };
    channels?: { primary?: string[]; secondary?: string[]; rationale?: string };
    timezone?: string;
    timezone_offset?: string;
    schedule?: {
      strategy?: string;
      peak_windows?: { label?: string; days?: string[]; start?: string; end?: string }[];
      best_single_start_time?: string;
      note?: string;
    };
    cadence?: { ads_per_week?: number; flight_days?: number; refresh_creative_every_days?: number };
    messaging_angles?: string[];
    rationale?: string;
  };
}

export interface ResultResponse {
  session_id: string;
  stage: BackendStage;
  bundle: CampaignBundle;
  publish_result: PublishResult | null;
  publish_error: string | null;
}

export interface PublishResult {
  campaign?: { id: string; status: string };
  ad_set?: { id: string; status?: string };
  creative?: { id: string };
  ad?: { id: string; status: string };
  post?: { id: string; created_time?: string; message?: string };
}

export interface PublishResponse {
  success: boolean;
  simulation_mode: boolean;
  result: PublishResult;
  errors: string[];
}

/** SSE event shape from GET /session/{id}/stream. */
export interface StreamEvent {
  event: "progress" | "interrupt" | "done" | "error" | "ping";
  stage?: string;
  message?: string;
  data?: InterruptData;
}
