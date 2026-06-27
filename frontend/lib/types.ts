// ------------------------------------------------------------------ //
// Shared types mirroring the FastAPI (api.py) contract.               //
// ------------------------------------------------------------------ //

/** Backend interrupt stages (the `stage` field returned by the API). */
export type BackendStage =
  | "campaign_target"
  | "questions"
  | "photo_select"
  | "text_review"
  | "done";

export type MarketingType = "real_estate";
export type Language = "en" | "ar";

/** Real estate interview question shapes. */
export type QuestionType =
  | "free_text"
  | "single_select_with_other"
  | "multi_select_with_other";

/** One AI-ranked campaign-goal option (campaign_target interrupt). */
export interface TargetOption {
  label: string;
  description: string;
  goal: string; // natural-language goal sentence sent back as the answer
  recommended: boolean;
}

/** One selectable option in a real estate interview question. */
export interface QuestionOption {
  label: string;
  value: string;
  recommended: boolean;
}

/** Client asset types uploaded one-by-one before the interview. */
export type AssetType = "logo" | "brochure" | "floor_plans" | "master_plan" | "price_list";

/** Common envelope returned by /start, /answers, /image-decision, etc. */
export interface StageResponse {
  stage: BackendStage;
  data: InterruptData;
}

/** _safe_data payloads — images are stripped to placeholder strings. */
export interface InterruptData {
  stage?: BackendStage;
  // campaign_target (the one fixed question — ranked multiple choice)
  options?: TargetOption[] | QuestionOption[];
  // questions (real estate interview — one at a time)
  question?: string;
  question_type?: QuestionType;
  allow_other?: boolean;
  is_follow_up?: boolean;
  index?: number;
  total_fixed?: number;
  // photo_select
  images?: string[]; // placeholders like "<image_0>"
  count?: number;
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
  budget: number;
  language: Language;
  imageFiles: File[]; // required — at least one real unit photo
}

export interface PhotoSelectBody {
  selected_indices: number[];
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
  campaign?: { platform?: string; objective?: string; tone?: string; special_ad_categories?: string[] };
  real_estate_project?: {
    compound_name?: string;
    location?: string;
    unit_types?: string;
    starting_price?: string;
    payment_plan?: string;
    offer?: string;
    lead_destination?: string;
    campaign_duration_days?: number;
    price_tier?: string;
  };
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
