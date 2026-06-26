// ------------------------------------------------------------------ //
// Thin typed client over the AutoMark AI FastAPI backend (api.py).    //
// Every call returns parsed JSON or throws an ApiError.               //
// ------------------------------------------------------------------ //

import type {
  ImageDecisionBody,
  ImagesResponse,
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

/** Starts the pipeline (image optional) — blocks until the first interrupt
 *  (stage "campaign_target"). The campaign goal is chosen later from the
 *  AI-ranked options, not sent here. */
export async function startSession(
  sessionId: string,
  setup: SetupData
): Promise<StageResponse> {
  const form = new FormData();
  form.append("budget", String(setup.budget));
  form.append("image_mode", setup.imageMode);
  form.append("marketing_type", setup.marketingType);
  form.append("language", setup.language);
  form.append("description", setup.description ?? "");
  if (setup.imageFile) {
    form.append("image", setup.imageFile, setup.imageFile.name);
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

export async function imageDecision(
  sessionId: string,
  body: ImageDecisionBody
): Promise<StageResponse> {
  const res = await fetch(`${API_BASE}/session/${sessionId}/image-decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse<StageResponse>(res);
}

export async function pickImage(
  sessionId: string,
  chosenIndex: number
): Promise<StageResponse> {
  const res = await fetch(`${API_BASE}/session/${sessionId}/pick-image`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chosen_index: chosenIndex }),
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
