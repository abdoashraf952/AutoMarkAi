// ------------------------------------------------------------------ //
// Shared types mirroring the FastAPI (api.py) contract.               //
// ------------------------------------------------------------------ //

/** Backend interrupt stages (the `stage` field returned by the API). */
export type BackendStage =
  | "campaign_target"
  | "questions"
  | "photo_select"
  | "text_review"
  | "approval"   // Phase 1: Approval Gateway gate (plan / creative / money / launch)
  | "done"
  | "compliance" // Phase 2: compliance gate result
  | "research"   // Phase 3: research squad progress
  | "diagnosis"  // Phase 4: operate loop diagnosis
  | "operate_decision"; // Phase 4: lifecycle decision

// ---- Approval Gateway (Phase 1) ---------------------------------- //

/** Three-tier approval mode controlling how often the user is interrupted. */
export type ApprovalMode = "full_manual" | "guided" | "autopilot";

/** Gate types that flow through request_approval(). */
export type ApprovalGateType = "creative" | "plan" | "money" | "launch" | "schedule";

/** Payload of an "approval" stage interrupt. */
export interface ApprovalItem {
  stage: "approval";
  type: ApprovalGateType;
  description: string;
  payload?: unknown;
}

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
  // approval gate (Phase 1)
  type?: ApprovalGateType;
  description?: string;
  payload?: unknown;
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
  approvalMode?: ApprovalMode;
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

// ---- Phase 2: Compliance (Phase 2) -------------------------------- //

export interface ComplianceResult {
  passed: boolean;
  violations: string[];
  warnings: string[];
  market: string;
  special_ad_category: string;
}

// ---- Phase 3: Research (Phase 3) ---------------------------------- //

export interface AudiencePlan {
  targeting_approach: string;
  geo: { city: string; radius_km: number; country: string };
  age_min: number;
  age_max: number;
  genders: string[];
  price_tier: string;
  platform_split: Record<string, number>;
  broad_delivery_note: string;
}

export interface CompetitorFinding {
  brand: string;
  hook: string;
  offer: string;
  format: string;
  run_days: number;
  insight: string;
}

// ---- Phase 4: Operate loop (Phase 4) ------------------------------ //

export type ControlMode = "advantage_plus" | "manual";
export type LearningState = "learning" | "exited" | "unstable";

export interface MetricSnapshot {
  ts: string;
  cpl: number;
  qualified_rate: number;
  frequency: number;
  leads: number;
  spend_usd: number;
  simulated?: boolean;
}

export interface OperateDiagnosis {
  ts: string;
  status: string;  // plain-language status
  cpl: number;
  qualified_rate: number;
  leads_today: number;
  frequency: number;
  learning_state: LearningState;
  simulated?: boolean;
}

export interface DecisionLogEntry {
  ts: string;
  decision: string;
  rationale: string;
  learning_state: LearningState;
  cpl?: number;
  qualified_rate?: number;
  outcome?: { executed: boolean; sim: boolean };
}

export interface CampaignReport {
  session_id: string;
  operate_enabled: boolean;
  control_mode: ControlMode;
  learning_state: LearningState;
  diagnosis: OperateDiagnosis;
  decisions: DecisionLogEntry[];
  metric_count: number;
  compliance: ComplianceResult;
}

// ---- Phase 5: Memory (Phase 5) ------------------------------------ //

export interface ClientMemory {
  client_id: string;
  updated_at: string;
  sessions: Array<{
    ts: string;
    compound_name?: string;
    location?: string;
    price_tier?: string;
    outcome?: string;
    performance_notes?: string;
  }>;
  known_compounds: string[];
  total_sessions: number;
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
