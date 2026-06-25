# AutoMark AI — Conversational Web App (Next.js)

A chat-first front-end for the AutoMark AI pipeline. **Mark** (the AI media
buyer) walks the user through the whole
journey one message at a time — uploading a photo, setting a budget, answering
product questions one-by-one, reviewing the generated visual and copy, and
finally publishing to Meta — all driven by the existing **FastAPI** backend
([`backend/api.py`](../backend/api.py)).

Aesthetic: **premium dark + glassmorphism**, animated aurora backdrop, and
bespoke loading animations for every waiting step so the experience never
feels idle.

---

## How it maps to the backend

The chat is a client-side **state machine** ([`hooks/useCampaignChat.ts`](hooks/useCampaignChat.ts))
that decomposes the backend's coarse stages into fine conversational phases:

| Conversational phase(s) | Backend call | Backend stage |
| --- | --- | --- |
| `language → marketing_type → image → image_mode → budget → goal` | `POST /session` then `POST /session/{id}/start` | → `questions` |
| `questions` (asked **one at a time**, collected locally) | `POST /session/{id}/answers` (all answers in one call) | → `image_review` |
| `image_review` (approve / tweak) | `POST /session/{id}/image-decision` | → `text_review` / loops / `max_regenerations_exceeded` |
| `max_regen` (pick a tile) | `POST /session/{id}/pick-image` | → `text_review` |
| `text_review` (approve / edit) | `POST /session/{id}/text-decision` | → `done` / loops to `image_review` |
| `done` (publish) | `POST /session/{id}/publish` + `GET /session/{id}/result` | — |

> **Why one-at-a-time questions work without backend changes:** `/answers`
> takes every answer in a single payload, so the UI simply collects answers
> conversationally and submits them together at the end.

Heavy base64 images are fetched separately via `GET /session/{id}/images`
(the JSON endpoints strip them). The **SSE stream**
(`GET /session/{id}/stream`) is used purely to enrich the loading captions
("Campaign plan locked in", "Crafting your media-buying strategy", …) while a
blocking POST is in flight.

---

## Run it

**1. Start the backend** (from the repo root):

```bash
cd AutoMarkAi
uvicorn api:app --reload --port 8000
```

**2. Start the web app** (in a second terminal):

```bash
cd web
cp .env.local.example .env.local   # adjust NEXT_PUBLIC_API_BASE if needed
npm install
npm run dev
```

Open <http://localhost:3000>.

> CORS is already wide-open in `api.py` (`allow_origins=["*"]`), so the browser
> can call the FastAPI backend directly. Tighten it to your deployed origin
> before going to production.

---

## Project structure

```
web/
├── app/
│   ├── layout.tsx          ← root layout + aurora background + fonts
│   ├── page.tsx            ← header, progress rail, chat window, composer
│   └── globals.css         ← design tokens, glass primitives, animations
├── hooks/
│   └── useCampaignChat.ts  ← the conversation state machine (the brain)
├── lib/
│   ├── api.ts              ← typed FastAPI client
│   ├── sse.ts              ← EventSource helper for progress captions
│   ├── copy.ts             ← bilingual (en/ar) assistant copy
│   └── types.ts            ← contract types mirroring api.py
└── components/
    ├── AuroraBackground.tsx
    ├── StageRail.tsx       ← 5-step journey indicator
    ├── ChatWindow.tsx      ← message stream + auto-scroll + typing dots
    ├── MessageBubble.tsx   ← dispatches text / image / card messages
    ├── Composer.tsx        ← context-aware docked input (per phase)
    ├── LoadingArt.tsx      ← 4 bespoke step loaders (analyze/build/image/publish)
    ├── MarkdownLite.tsx    ← minimal **bold** + line-break renderer
    ├── TypingIndicator.tsx
    ├── steps/              ← OptionCards, ImageUpload, BudgetInput, TextSend, ReviewActions
    └── cards/              ← ImageCard, ImageGrid, CopyCard, DoneCard, AdPreview, PublishCard
```

---

## Notes & next steps

- **Bilingual:** English + Egyptian Arabic, chosen as the first chat step;
  Arabic flips the composer to RTL.
- **Resilience:** any API error surfaces as a chat bubble with a "Start over"
  action; the in-memory backend session means a server restart requires a new
  campaign.
- **Possible enhancements:** persist the session id to survive refreshes,
  stream the bot text token-by-token, add confetti on publish, and allow
  multi-image review when `NUM_GENERATED_IMAGES > 1`.
