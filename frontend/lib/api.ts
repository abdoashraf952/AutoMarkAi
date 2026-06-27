// ------------------------------------------------------------------ //
// Thin typed client over the AutoMark AI FastAPI backend (api.py).    //
// Every call returns parsed JSON or throws an ApiError.               //
// ------------------------------------------------------------------ //

import type {
  ApprovalMode,
  AssetType,
  ImagesResponse,
  PhotoSelectBody,
  PublishBody,
  PublishResponse,
  ResultResponse,
  SessionResponse,
  SetupData,
  StageResponse,
  TextDecisionBody,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      detail = body?.detail || JSON.stringify(body);
    } catch {
      /* non-json error body */
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

export async function createSession(): Promise<SessionResponse> {
  const res = await fetch(`${API_BASE}/session`, { method: "POST" });
  return parse<SessionResponse>(res);
}

/** Upload a client asset (logo, brochure, floor plans, …) before starting. */
export async function uploadAsset(
  sessionId: string,
  assetType: AssetType,
  file: File
): Promise<{ ok: boolean; asset_type: string; filename: string }> {
  const form = new FormData();
  form.append("asset_type", assetType);
  form.append("file", file, file.name);
  const res = await fetch(`${API_BASE}/session/${sessionId}/upload-asset`, {
    method: "POST",
    body: form,
  });
  return parse(res);
}

/** Set the approval mode (and optionally feature flags) for the session.
 *  Call before /start, or at any time to adjust the mode mid-campaign. */
export async function setMode(
  sessionId: string,
  approvalMode: ApprovalMode,
  featureFlags: Record<string, boolean> = {}
): Promise<{ ok: boolean; approval_mode: string; feature_flags: Record<string, boolean> }> {
  const res = await fetch(`${API_BASE}/session/${sessionId}/mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approval_mode: approvalMode, feature_flags: featureFlags }),
  });
  return parse(res);
}

/** Starts the pipeline with the uploaded unit photos — blocks until the first
 *  interrupt. In 'guided' or 'autopilot' mode the first interrupt may be
 *  'questions' (campaign target is auto-picked), not 'campaign_target'. */
export async function startSession(
  sessionId: string,
  setup: SetupData
): Promise<StageResponse> {
  const form = new FormData();
  form.append("budget", String(setup.budget));
  form.append("language", setup.language);
  form.append("approval_mode", setup.approvalMode ?? "full_manual");
  for (const file of setup.imageFiles) {
    form.append("images", file, file.name);
  }

  const res = await fetch(`${API_BASE}/session/${sessionId}/start`, {
    method: "POST",
    body: form,
  });
  return parse<StageResponse>(res);
}

/** Answer the current adaptive question; the response carries the next question
 *  (stage "questions") or the next stage when the interview is done. */
export async function submitAnswer(
  sessionId: string,
  answer: string
): Promise<StageResponse> {
  const res = await fetch(`${API_BASE}/session/${sessionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer }),
  });
  return parse<StageResponse>(res);
}

/** Choose which uploaded photos to use in the ad (photo_select interrupt). */
export async function selectPhotos(
  sessionId: string,
  selectedIndices: number[]
): Promise<StageResponse> {
  const body: PhotoSelectBody = { selected_indices: selectedIndices };
  const res = await fetch(`${API_BASE}/session/${sessionId}/select-photos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse<StageResponse>(res);
}

export async function textDecision(
  sessionId: string,
  body: TextDecisionBody
): Promise<StageResponse> {
  const res = await fetch(`${API_BASE}/session/${sessionId}/text-decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse<StageResponse>(res);
}

export async function getImages(sessionId: string): Promise<ImagesResponse> {
  const res = await fetch(`${API_BASE}/session/${sessionId}/images`);
  return parse<ImagesResponse>(res);
}

export async function publish(
  sessionId: string,
  body: PublishBody = { make_sponsored_ad: true, make_organic_post: true }
): Promise<PublishResponse> {
  const res = await fetch(`${API_BASE}/session/${sessionId}/publish`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse<PublishResponse>(res);
}

export async function getResult(sessionId: string): Promise<ResultResponse> {
  const res = await fetch(`${API_BASE}/session/${sessionId}/result`);
  return parse<ResultResponse>(res);
}

/** Convenience: build an <img>-ready data URL from a raw base64 string. */
export function toDataUrl(base64: string, mime = "image/png"): string {
  if (!base64) return "";
  if (base64.startsWith("data:")) return base64;
  return `data:${mime};base64,${base64}`;
}
