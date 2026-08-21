// ------------------------------------------------------------------ //
// SSE helper for GET /session/{id}/stream.                            //
// Emits live `progress` events while a blocking POST is in flight, so //
// the loading animations can show meaningful, evolving captions.      //
// ------------------------------------------------------------------ //

import { CAMPAIGN_API } from "./api";
import type { StreamEvent } from "./types";

export interface StreamHandle {
  close: () => void;
}

export function openStream(
  sessionId: string,
  onEvent: (e: StreamEvent) => void
): StreamHandle {
  const source = new EventSource(`${CAMPAIGN_API}/session/${sessionId}/stream`);

  source.onmessage = (msg) => {
    try {
      const data = JSON.parse(msg.data) as StreamEvent;
      if (data.event === "ping") return; // keepalive — ignore
      onEvent(data);
    } catch {
      /* malformed frame — ignore */
    }
  };

  source.onerror = () => {
    // The stream closes itself after `done`/`error`; browser auto-reconnect
    // is harmless here. We swallow transient errors silently.
  };

  return { close: () => source.close() };
}
