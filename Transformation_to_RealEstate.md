# AutoMarkAI → Real Estate Transformation Guide

> **Purpose**: This document is a complete, step-by-step specification for transforming the current generic AutoMarkAI project into a **real-estate-specific Meta campaign generator**. Every change is listed with the exact file path, what to modify, and the reasoning. Follow these instructions in the order presented.

---

## Table of Contents

1. [Overview of Changes](#1-overview-of-changes)
2. [CHANGE 1 — Remove the Marketing Type Question](#2-change-1--remove-the-marketing-type-question)
3. [CHANGE 2 — Remove AI Photo Enhancement & Add Multi-Photo Upload](#3-change-2--remove-ai-photo-enhancement--add-multi-photo-upload)
4. [CHANGE 3 — Replace Adaptive Questions with Real Estate Interview](#4-change-3--replace-adaptive-questions-with-real-estate-interview)
5. [CHANGE 4 — Add Structured File Upload Step](#5-change-4--add-structured-file-upload-step)
6. [CHANGE 5 — HOUSING Special Ad Category Compliance](#6-change-5--housing-special-ad-category-compliance)
7. [CHANGE 6 — Rewrite All Prompt Templates for Real Estate](#7-change-6--rewrite-all-prompt-templates-for-real-estate)
8. [CHANGE 7 — Update Frontend Copy, Branding & Landing Page](#8-change-7--update-frontend-copy-branding--landing-page)
9. [CHANGE 8 — Smart Defaults Based on Price Range](#9-change-8--smart-defaults-based-on-price-range)
10. [CHANGE 9 — Update the Campaign Bundle & Meta Publishing](#10-change-9--update-the-campaign-bundle--meta-publishing)
11. [Reference Files](#11-reference-files)

---

## 1. Overview of Changes

### What the project is TODAY
A **generic** Meta ad campaign generator that works for any product, business, or service. The user uploads one photo, chooses a marketing type, answers 4–10 adaptive LLM-generated questions, then the system generates ad copy + AI images and publishes to Meta.

### What it should become
A **real-estate-specific** Meta campaign generator for Egyptian real estate agencies. The user uploads multiple unit photos, answers a curated set of real estate questions (compound name, location, unit types, prices, offers, etc.) with LLM-driven follow-ups between them, then the system generates real-estate ad copy using their actual photos and publishes to Meta with HOUSING category compliance.

### Summary of all changes

| # | Change | Impact |
|---|--------|--------|
| 1 | Remove `marketing_type` question | Hardcode to `"real_estate"` everywhere |
| 2 | Remove AI image generation/enhancement; add multi-photo upload | Photos are real unit photos, user can upload multiple |
| 3 | Replace adaptive questions with a curated real estate interview + LLM follow-ups | Fixed question list covering compound details, with LLM follow-up questions between them |
| 4 | Add structured file upload step (one-by-one) | Logo, brochure, floor plans, etc. — each with an explanation |
| 5 | Enforce Meta HOUSING special ad category | No age/gender targeting, forced 18–65+, `special_ad_categories: ["HOUSING"]` |
| 6 | Rewrite all prompt templates for real estate | Orchestrator, strategy, creative, media buying — all real-estate-specific |
| 7 | Update frontend copy, branding & landing page | Real estate messaging, remove generic references |
| 8 | Smart defaults based on price range | Auto-infer platform split, tone, and targeting from price tier |
| 9 | Update campaign bundle structure for real estate | Add `real_estate_project` section to bundle, update Meta publish flow |

---

## 2. CHANGE 1 — Remove the Marketing Type Question

### Reasoning
The app is now exclusively for real estate agencies. There's no need to ask whether they're promoting a "product", "business", or "service".

### Files to modify

#### `backend/state.py`
- Change the `marketing_type` field default/type:
  ```python
  # BEFORE:
  marketing_type: str     # "product" | "business" | "service"

  # AFTER:
  marketing_type: str     # Always "real_estate" — hardcoded, not user-selectable
  ```

#### `backend/api.py` — `start_session` endpoint (line ~219–264)
- Remove `marketing_type` from the `Form(...)` parameter. Hardcode it internally:
  ```python
  # BEFORE:
  marketing_type: str = Form("product", description="'product', 'business', or 'service'"),

  # AFTER — remove the parameter entirely and hardcode in the state dict:
  await _advance(session, {
      ...
      "marketing_type": "real_estate",   # hardcoded — no longer user-selectable
      ...
  })
  ```

#### `backend/i18n.py`
- The `_pick()` function currently looks up prompt templates by `marketing_type` key (product/business/service). Change all prompt template files (see CHANGE 6) to use a single string instead of a dict keyed by marketing_type — OR add a `"real_estate"` key to every dict. The simplest approach: change all template dicts to just be strings (no longer keyed by type), since there's only one type now.
- Update `SUPPORTED_MARKETING_TYPES`:
  ```python
  # BEFORE:
  SUPPORTED_MARKETING_TYPES = ("product", "business", "service")

  # AFTER:
  SUPPORTED_MARKETING_TYPES = ("real_estate",)
  DEFAULT_MARKETING_TYPE = "real_estate"
  ```

#### `frontend/hooks/useCampaignChat.ts`
- Remove the `"marketing_type"` phase from the `ChatPhase` type union.
- Remove the `chooseMarketingType` callback entirely.
- In the `chooseLanguage` callback, instead of transitioning to `"marketing_type"` phase, skip directly to the next phase (which will be `"image"` — the multi-photo upload, see CHANGE 2).
- Remove `marketingType` from the `setupRef` defaults, hardcode it in `beginPipeline`:
  ```typescript
  // In beginPipeline, when calling api.startSession:
  const resp = await api.startSession(session.session_id, {
    budget: s.budget,
    imageMode: "use_original",  // always use original (see CHANGE 2)
    marketingType: "real_estate" as any,  // hardcoded
    language: lang,
    imageFiles: s.imageFiles,   // multiple files (see CHANGE 2)
  });
  ```

#### `frontend/components/Composer.tsx`
- Remove the `case "marketing_type":` block entirely (lines ~71–77).

#### `frontend/lib/copy.ts`
- Remove the `MARKETING_TYPE_OPTIONS` export entirely.
- Remove the `askMarketingType` key from both EN and AR dictionaries.
- Remove the import of `MARKETING_TYPE_OPTIONS` from `Composer.tsx`.

#### `frontend/lib/types.ts`
- Change `MarketingType` type:
  ```typescript
  // BEFORE:
  export type MarketingType = "product" | "business" | "service";

  // AFTER:
  export type MarketingType = "real_estate";
  ```

#### `backend/templates/locales/en/strings.py` and `backend/templates/locales/ar/strings.py`
- Remove `MARKETING_TYPE_LABELS` and `MARKETING_TYPE_DESCRIPTIONS` dicts, or replace them with a single real estate entry.

---

## 3. CHANGE 2 — Remove AI Photo Enhancement & Add Multi-Photo Upload

### Reasoning
Real estate buyers must see **actual photos** of the units. AI-enhanced or generated images would be misleading and damage trust. The user should upload **multiple** photos of their units (the current system only accepts one).

### Remove these features entirely:
1. **Image mode selection** — the `"use_original" | "enhance_with_ai" | "generate_with_ai"` choice
2. **AI image generation** — `generate_ad_images()` calls
3. **AI image enhancement** — `enhance_ad_image()` calls
4. **Image regeneration loop** — `image_regen_node`, the regen/pick cycle in `image_review_node`
5. **"Skip image"** option — in real estate, photos are required

### Files to modify

#### `backend/state.py`
```python
# BEFORE:
image_path: str
image_mode: str         # "use_original" | "enhance_with_ai" | "generate_with_ai"

# AFTER:
image_paths: list[str]   # Multiple unit photos uploaded by the user
# Remove image_mode entirely — always "use_original"

# Also REMOVE these image-review sub-state fields (no longer needed):
# image_history: list
# regen_count: int
# review_route: str
# regen_indices: list
# image_regen_feedback: dict
```

#### `backend/api.py` — `start_session` endpoint
- Accept multiple images instead of one:
  ```python
  # BEFORE:
  image: UploadFile | None = File(None, ...)

  # AFTER:
  images: list[UploadFile] = File([], description="Unit photos (jpg/png/webp). At least one required.")
  ```
- Save all uploaded images to temp files and store their paths:
  ```python
  image_paths = []
  for img in images:
      if img.filename:
          suffix = Path(img.filename).suffix or ".jpg"
          with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
              tmp.write(await img.read())
              image_paths.append(tmp.name)

  if not image_paths:
      raise HTTPException(400, "At least one unit photo is required.")
  ```
- Remove the `image_mode` Form parameter entirely.
- Pass `image_paths` (list) instead of `image_path` (single) to the pipeline state.
- Remove the `description` Form parameter (no longer needed — the unit photos ARE the product).

#### `backend/nodes/creative.py`
- **Remove all AI image generation/enhancement logic** (the `enhance_ad_image` and `generate_ad_images` calls, lines ~93–111).
- The creative node should **only** generate ad copy text (copies, headlines, CTA). It should use all uploaded photos as-is.
- Read all photos from `state["image_paths"]`, encode them as base64, and store in `generated_images`:
  ```python
  image_paths = state.get("image_paths") or []
  generated_images = []
  for path in image_paths:
      try:
          with open(path, "rb") as fh:
              generated_images.append(base64.b64encode(fh.read()).decode("utf-8"))
      except OSError as e:
          img_errors.append(f"image_read_failed: {e}")
  creative_output["generated_images"] = generated_images
  ```
- Remove the `visual_prompt` from the creative output schema (no AI images to generate).

#### `backend/nodes/review.py`
- **Completely rewrite** the review flow. Remove:
  - `image_regen_node` — no regeneration
  - `image_pick_node` — simplified (but keep a version for selecting which photos to use in the ad)
  - The regeneration loop and `_build_choices` function
- Replace with a **photo selection node**: Show the user all their uploaded photos and let them select which one(s) to use in the ad. This is a single interrupt with no loop:
  ```python
  def photo_select_node(state: dict) -> dict:
      """Let the user pick which of their uploaded photos to use in the ad.
      
      Interrupt payload: {"stage": "photo_select", "images": [...base64...], "count": int}
      Resume payload: {"selected_indices": [0, 2, 3]}  # which photos to use
      """
      image_paths = state.get("image_paths") or []
      images_b64 = []
      for path in image_paths:
          with open(path, "rb") as fh:
              images_b64.append(base64.b64encode(fh.read()).decode("utf-8"))
      
      result = interrupt({
          "stage": "photo_select",
          "images": images_b64,
          "count": len(images_b64),
      })
      
      selected = result.get("selected_indices", list(range(len(images_b64))))
      selected_images = [images_b64[i] for i in selected if i < len(images_b64)]
      
      creative = dict(state.get("creative_output") or {})
      creative["generated_images"] = selected_images
      return {"creative_output": creative, "review_stage": "photos_selected"}
  ```

#### `backend/pipeline_graph.py`
- Remove `image_review_node`, `image_regen_node`, `image_pick_node` from the graph.
- Add `photo_select_node` in their place.
- Simplify the post-creative flow:
  ```
  creative_node → photo_select_node → text_review_node → merge_node → END
  ```
- Remove `_route_after_image_review` conditional edge function.
- Remove the regen/pick loop edges.

#### `frontend/hooks/useCampaignChat.ts`
- Remove the `"image_mode"` phase.
- Change the `"image"` phase to support **multiple file selection**.
- Add a new `"photo_select"` phase for choosing which uploaded photos to use.
- Remove `"image_regenerating"` and `"max_regen"` phases.
- Remove `canRegenerate`, `imageMeta`, `regenerateImage`, `gatherVersions` state/callbacks.
- Change `setImage` to `setImages` accepting `File[]`.
- Remove `skipImage` — photos are required for real estate.
- Remove `chooseImageMode` — no mode selection.

#### `frontend/components/Composer.tsx`
- Remove the `case "image_mode":` block entirely.
- Update `case "image":` to use a multi-file upload component.
- Remove `case "image_review":` regeneration UI.
- Remove `case "max_regen":` block.
- Add a `case "photo_select":` block for selecting photos.

#### `frontend/components/steps/ImageUpload.tsx`
- Rewrite to support **multiple file selection**:
  - Change the `<input>` to `multiple`.
  - Change `onSelect: (file: File) => void` to `onSelect: (files: File[]) => void`.
  - Show thumbnails of all selected files.
  - Remove the "Skip" button (`onSkip` prop) — photos are required.
  - Change the label to "Upload photos of your units" / "ارفع صور الوحدات".
  - Add a minimum file count validation (at least 1 photo required).

#### `frontend/lib/types.ts`
- Remove `ImageMode` type entirely (or set it to just `"use_original"`).
- Change `SetupData`:
  ```typescript
  // BEFORE:
  imageFile?: File;
  imageMode: ImageMode;
  description?: string;

  // AFTER:
  imageFiles: File[];  // required, at least one
  // Remove imageMode and description
  ```
- Update `BackendStage` — remove `"image_review"` and `"max_regenerations_exceeded"`, add `"photo_select"`.

#### `frontend/lib/api.ts` — `startSession`
- Send multiple images in the FormData:
  ```typescript
  // BEFORE:
  if (setup.imageFile) {
    form.append("image", setup.imageFile, setup.imageFile.name);
  }

  // AFTER:
  for (const file of setup.imageFiles) {
    form.append("images", file, file.name);
  }
  ```
- Remove `image_mode` and `description` from the form.
- Add a new `selectPhotos` API function for the photo_select endpoint.

#### `frontend/lib/copy.ts`
- Remove: `askImageMode`, `useOriginal`, `enhanceAI`, `skipImage`, `askDescribe`, `describePlaceholder`, `aiCreatedImage`, `enhancedImage`, `imageReviewIntro`, `regenerating`, `regensLeft`, `regensNoneLeft`, `seeAllVersions`, `gatheringVersions`, `maxRegenIntro`, `feedbackPlaceholderImg`.
- Add: `askUnitPhotos` ("Upload photos of the units you want to advertise 📸"), `photoSelectIntro` ("Pick which photos to include in your ad"), `photoRequired` ("At least one unit photo is required").

#### `backend/api.py` — Remove/simplify endpoints
- Remove the `/session/{session_id}/image-decision` endpoint entirely.
- Remove the `/session/{session_id}/pick-image` endpoint entirely.
- Add a `/session/{session_id}/select-photos` endpoint:
  ```python
  class PhotoSelectBody(BaseModel):
      selected_indices: list[int]

  @app.post("/session/{session_id}/select-photos")
  async def select_photos(session_id: str, body: PhotoSelectBody):
      from langgraph.types import Command
      session = _get_session(session_id)
      _assert_stage(session, "photo_select")
      await _advance(session, Command(resume={"selected_indices": body.selected_indices}))
      return {"stage": session["ui_stage"], "data": _safe_data(session["interrupt_data"])}
  ```

---

## 4. CHANGE 3 — Replace Adaptive Questions with Real Estate Interview

### Reasoning
Instead of purely LLM-generated questions (which may miss critical real estate details), we use a **curated list of essential questions** with **LLM-driven follow-up questions** inserted between them. This is still **chat-based** (one question at a time), NOT form-based. The LLM decides after each answer whether a follow-up would add value before moving to the next fixed question.

### Question flow design

The interview alternates between **fixed questions** from our curated list and **LLM-generated follow-ups** based on previous answers. Each fixed question includes **options with a recommendation** and an **"Other"** free-text option.

#### Fixed question list (asked in this order):

```
Q1: What's the compound/project name?
    → Type: free text
    → Follow-up opportunity: LLM may ask about the developer name if not mentioned

Q2: Where is it located?
    → Type: options + other
    → Options: New Cairo, 6th of October, Sheikh Zayed, North Coast, New Capital, Ain Sokhna, Mostakbal City, Other
    → Recommended: based on market data (if available)
    → Follow-up opportunity: LLM may ask about nearby landmarks or exact area

Q3: What types of units are available?
    → Type: multi-select + other
    → Options: Apartment, Villa, Duplex, Townhouse, Twin House, Penthouse, Studio, Chalet
    → Follow-up opportunity: LLM may ask about unit sizes if multiple types selected

Q4: What's the starting price?
    → Type: free text (numeric)
    → Follow-up opportunity: LLM may ask about price range or highest price

Q5: What are the payment terms?
    → Type: structured (asked as chat question with example options)
    → Options: "e.g. 10% down payment, 7 years installments" — user types their terms
    → Sub-info needed: Down payment percentage, installment years, delivery date
    → Follow-up opportunity: LLM may ask about delivery date or construction status if not mentioned

Q6: Do you currently have a special offer?
    → Type: options + other
    → Options: 5% Down Payment, Zero Down Payment, Limited Units Available, Free Club Membership, Discount on Cash Payment, Furnished Units, No current offer, Other
    → Recommended: "Limited Units Available" (creates urgency)
    → Follow-up opportunity: LLM may ask about offer expiry date

Q7: What's the main goal of this campaign?
    → Type: THIS IS THE EXISTING campaign_target STEP (AI-ranked options)
    → Already implemented — keep it, but make the options real-estate-specific
    → Options should be: Lead Generation (recommended), Brand Awareness, Sales, Event Registration (for project launch events)

Q8: Where should interested leads go?
    → Type: options + other
    → Options: WhatsApp, Phone Call, Facebook Instant Form, Landing Page, Other
    → Recommended: WhatsApp (highest conversion for Egyptian real estate)
    → This maps to `ad_set.conversion_location` in the Meta schema

Q9: What's your campaign budget? (in EGP or USD)
    → Type: THIS IS THE EXISTING budget step — keep it
    → Follow-up: LLM may ask about campaign duration

Q10: How long should the campaign run?
    → Type: options + other
    → Options: 1 week, 2 weeks, 1 month, 3 months, Other
    → Recommended: 2 weeks (good balance for real estate lead gen)
    → This is used to calculate daily_budget = total_budget / campaign_days
```

### How the hybrid fixed + follow-up system works

The question generator node should work as follows:

```
1. Maintain a FIXED_QUESTIONS list (the 10 questions above, in order)
2. Maintain a pointer: current_fixed_index (which fixed question we're on)
3. After each user answer:
   a. Send the full conversation context to the LLM
   b. Ask the LLM: "Based on the answer just given, is there a valuable follow-up question
      before we move to the next topic? If yes, return it. If no, return done=true."
   c. If LLM says follow-up → ask that follow-up question (still one-at-a-time chat)
   d. If LLM says no follow-up → move to the next fixed question
4. For each fixed question, provide the options, recommendation, and "Other" in the interrupt payload
5. The total question count = fixed questions + any follow-ups the LLM inserts
```

### Files to modify

#### `backend/state.py` — Add new state fields
```python
# ADD these fields:
current_fixed_q_index: int      # which fixed question we're on (0-based)
is_follow_up: bool              # whether the current question is an LLM follow-up
campaign_duration_days: int     # from Q10, used for daily budget calc
lead_destination: str           # from Q8: "whatsapp" | "phone" | "instant_form" | "landing_page"

# The real_estate_project data collected from answers:
real_estate_data: dict          # {compound_name, location, unit_types, starting_price, payment_plan, offer, ...}
```

#### `backend/nodes/question_generator.py` — Major rewrite

This is the biggest change. The current system uses a single LLM call to decide the next question. The new system uses a **fixed question list** with **optional LLM follow-ups**.

```python
"""Real estate interview — fixed questions with LLM-driven follow-ups.

Flow:
    1. fixed_question_node → interrupt with options/free-text for the current fixed question
    2. After answer: follow_up_check_node → LLM decides if a follow-up adds value
       - If yes → follow_up_ask_node (interrupt with the follow-up question)
       - If no  → advance to next fixed question → fixed_question_node
    3. Repeat until all fixed questions answered
    4. Route to orchestrator_node
"""

# The curated list of fixed questions
FIXED_QUESTIONS = [
    {
        "key": "compound_name",
        "question_en": "What's the name of the compound or project you're advertising?",
        "question_ar": "إيه اسم الكمبوند أو المشروع اللي عايز تعلن عنه؟",
        "type": "free_text",
        "options": None,
        "recommended": None,
        "data_field": "compound_name",
    },
    {
        "key": "location",
        "question_en": "Where is it located?",
        "question_ar": "فين موقعه؟",
        "type": "single_select_with_other",
        "options_en": [
            {"label": "New Cairo", "value": "new_cairo"},
            {"label": "6th of October", "value": "6th_october"},
            {"label": "Sheikh Zayed", "value": "sheikh_zayed"},
            {"label": "North Coast", "value": "north_coast"},
            {"label": "New Administrative Capital", "value": "new_capital"},
            {"label": "Ain Sokhna", "value": "ain_sokhna"},
            {"label": "Mostakbal City", "value": "mostakbal_city"},
        ],
        "options_ar": [
            {"label": "القاهرة الجديدة", "value": "new_cairo"},
            {"label": "٦ أكتوبر", "value": "6th_october"},
            {"label": "الشيخ زايد", "value": "sheikh_zayed"},
            {"label": "الساحل الشمالي", "value": "north_coast"},
            {"label": "العاصمة الإدارية الجديدة", "value": "new_capital"},
            {"label": "العين السخنة", "value": "ain_sokhna"},
            {"label": "مدينة المستقبل", "value": "mostakbal_city"},
        ],
        "recommended": "new_cairo",  # most common — can be overridden by AI
        "data_field": "location",
    },
    {
        "key": "unit_types",
        "question_en": "What types of units are available?",
        "question_ar": "إيه أنواع الوحدات المتاحة؟",
        "type": "multi_select_with_other",
        "options_en": [
            {"label": "Apartment", "value": "apartment"},
            {"label": "Villa", "value": "villa"},
            {"label": "Duplex", "value": "duplex"},
            {"label": "Townhouse", "value": "townhouse"},
            {"label": "Twin House", "value": "twin_house"},
            {"label": "Penthouse", "value": "penthouse"},
            {"label": "Studio", "value": "studio"},
            {"label": "Chalet", "value": "chalet"},
        ],
        "options_ar": [
            {"label": "شقة", "value": "apartment"},
            {"label": "فيلا", "value": "villa"},
            {"label": "دوبلكس", "value": "duplex"},
            {"label": "تاون هاوس", "value": "townhouse"},
            {"label": "توين هاوس", "value": "twin_house"},
            {"label": "بنتهاوس", "value": "penthouse"},
            {"label": "استوديو", "value": "studio"},
            {"label": "شاليه", "value": "chalet"},
        ],
        "recommended": None,
        "data_field": "unit_types",
    },
    {
        "key": "starting_price",
        "question_en": "What's the starting price? (in EGP)",
        "question_ar": "إيه أقل سعر؟ (بالجنيه المصري)",
        "type": "free_text",
        "options": None,
        "recommended": None,
        "data_field": "starting_price",
    },
    {
        "key": "payment_plan",
        "question_en": "What are the payment terms? (down payment %, installment years, delivery date)",
        "question_ar": "إيه نظام السداد؟ (مقدم %، سنوات تقسيط، تاريخ الاستلام)",
        "type": "free_text",
        "options": None,
        "recommended": None,
        "data_field": "payment_plan",
    },
    {
        "key": "offer",
        "question_en": "Do you currently have a special offer running?",
        "question_ar": "عندك عرض حالي؟",
        "type": "single_select_with_other",
        "options_en": [
            {"label": "5% Down Payment", "value": "5_percent_down"},
            {"label": "Zero Down Payment", "value": "zero_down"},
            {"label": "Limited Units Available", "value": "limited_units"},
            {"label": "Free Club Membership", "value": "free_membership"},
            {"label": "Discount on Cash", "value": "cash_discount"},
            {"label": "Furnished Units", "value": "furnished"},
            {"label": "No current offer", "value": "no_offer"},
        ],
        "options_ar": [
            {"label": "مقدم ٥٪", "value": "5_percent_down"},
            {"label": "بدون مقدم", "value": "zero_down"},
            {"label": "وحدات محدودة", "value": "limited_units"},
            {"label": "عضوية نادي مجانية", "value": "free_membership"},
            {"label": "خصم على الكاش", "value": "cash_discount"},
            {"label": "وحدات مفروشة", "value": "furnished"},
            {"label": "مفيش عرض حالياً", "value": "no_offer"},
        ],
        "recommended": "limited_units",
        "data_field": "offer",
    },
    {
        "key": "lead_destination",
        "question_en": "Where should interested people reach you?",
        "question_ar": "العميل المهتم يتواصل معاك إزاي؟",
        "type": "single_select_with_other",
        "options_en": [
            {"label": "WhatsApp", "value": "whatsapp"},
            {"label": "Phone Call", "value": "phone"},
            {"label": "Facebook Instant Form", "value": "instant_form"},
            {"label": "Landing Page", "value": "landing_page"},
        ],
        "options_ar": [
            {"label": "واتساب", "value": "whatsapp"},
            {"label": "مكالمة تليفون", "value": "phone"},
            {"label": "فورم فيسبوك", "value": "instant_form"},
            {"label": "صفحة هبوط", "value": "landing_page"},
        ],
        "recommended": "whatsapp",
        "data_field": "lead_destination",
    },
    {
        "key": "campaign_duration",
        "question_en": "How long should the campaign run?",
        "question_ar": "الحملة تشتغل لمدة قد إيه؟",
        "type": "single_select_with_other",
        "options_en": [
            {"label": "1 week", "value": "7"},
            {"label": "2 weeks", "value": "14"},
            {"label": "1 month", "value": "30"},
            {"label": "3 months", "value": "90"},
        ],
        "options_ar": [
            {"label": "أسبوع", "value": "7"},
            {"label": "أسبوعين", "value": "14"},
            {"label": "شهر", "value": "30"},
            {"label": "٣ شهور", "value": "90"},
        ],
        "recommended": "14",
        "data_field": "campaign_duration_days",
    },
]
```

#### LLM follow-up prompt (new)

After each user answer, the LLM receives the full conversation and decides if a follow-up is warranted. Create a new prompt template:

```python
FOLLOW_UP_SYSTEM = (
    "You are a real estate media buyer assistant. You've been collecting information "
    "about a real estate compound to create a Meta ad campaign. After the user answered "
    "the latest question, decide if ONE quick follow-up question would add meaningful "
    "value before moving to the next topic.\n"
    "Rules:\n"
    "- Only ask a follow-up if the user's answer was vague, incomplete, or revealed "
    "something worth exploring (e.g. they mentioned construction status, a unique feature, etc.)\n"
    "- The follow-up must be SHORT, specific, and easy to answer.\n"
    "- Do NOT ask a follow-up just for the sake of it — brevity is respected.\n"
    "- Never ask about marketing jargon (CPL, CTR, ROAS, etc.).\n"
    "- Never repeat information already known from previous answers.\n"
    "Return ONLY this JSON: {\"follow_up\": true|false, \"question\": \"<follow-up question or empty>\"}\n"
    "If follow_up is false, question must be empty string."
)
```

#### Question interrupt payload format (new)

Every question interrupt (both fixed and follow-up) should include options when available:

```python
interrupt({
    "stage": "questions",
    "question": "Where is it located?",
    "question_type": "single_select_with_other",  # or "free_text", "multi_select_with_other"
    "options": [
        {"label": "New Cairo", "value": "new_cairo", "recommended": True},
        {"label": "6th of October", "value": "6th_october", "recommended": False},
        ...
    ],
    "allow_other": True,  # shows a free-text "Other" input
    "index": 1,  # current question number (for progress display)
    "total_fixed": 8,  # total fixed questions (for progress like "2 of 8")
    "is_follow_up": False,  # True for LLM-generated follow-ups
})
```

For follow-up questions from the LLM, the payload has no predefined options:
```python
interrupt({
    "stage": "questions",
    "question": "What's special about the location — any nearby landmarks or facilities?",
    "question_type": "free_text",
    "options": None,
    "allow_other": True,
    "index": 1,  # same index as the parent fixed question
    "total_fixed": 8,
    "is_follow_up": True,
})
```

#### `frontend/components/Composer.tsx` — Update the questions phase

The `case "questions":` block currently shows only a `TextSend` input. It needs to be updated to handle the three question types:

1. **`free_text`**: Show the existing `TextSend` component (no change).
2. **`single_select_with_other`**: Show option cards (like `CampaignTargetCards`) with a recommended badge, PLUS an "Other" free-text input at the bottom.
3. **`multi_select_with_other`**: Show option cards with **checkboxes** (multi-select), PLUS an "Other" free-text input.

Create a **new component** `frontend/components/steps/QuestionWithOptions.tsx`:
- Renders options as tappable cards (like `OptionCards` but with a recommendation badge)
- Includes an "Other" text input below the options
- For multi-select: checkboxes with a "Confirm" button
- For single-select: tap to select and submit
- On submit: sends the selected value(s) or the "Other" text as the answer

#### `frontend/hooks/useCampaignChat.ts` — Update question handling

The `handleStage` and `answerQuestion` callbacks need to handle the new question payload format:
- Parse `question_type`, `options`, `is_follow_up` from the interrupt data
- Display progress as "Question 2 of 8" (using `index` and `total_fixed`)
- For follow-up questions, show them without incrementing the progress counter

---

## 5. CHANGE 4 — Add Structured File Upload Step

### Reasoning
Real estate campaigns benefit from additional marketing assets (logo, brochure, floor plans). These should be uploaded **one-by-one** with a clear explanation for each, in order of priority.

### New phase: `"file_uploads"`

Insert this phase AFTER the multi-photo upload and BEFORE the questions. It's a sequential upload flow:

```
Phase: file_uploads
  Step 1: "Upload your company logo" (required)
  Step 2: "Upload a brochure PDF if you have one" (optional — skip button)
  Step 3: "Upload floor plans if available" (optional — skip button)
  Step 4: "Upload a master plan image if available" (optional — skip button)
  Step 5: "Upload a price list if available" (optional — skip button)
```

Each step shows:
- A title explaining what to upload
- A brief explanation of WHY it helps ("We'll use your logo on the ad creative")
- A file upload dropzone
- A "Skip" button for optional files
- A "Done with uploads" button after the required file(s)

### Files to modify

#### `backend/state.py`
```python
# ADD:
logo_path: str              # path to uploaded logo
asset_paths: dict           # {"brochure": "path", "floor_plans": ["path1", ...], "master_plan": "path", "price_list": "path"}
```

#### `backend/api.py`
- Add a new endpoint for uploading assets (or extend the start endpoint):
  ```python
  @app.post("/session/{session_id}/upload-asset")
  async def upload_asset(
      session_id: str,
      asset_type: str = Form(..., description="'logo', 'brochure', 'floor_plans', 'master_plan', 'price_list'"),
      file: UploadFile = File(...),
  ):
      # Save the file and store the path in the session
  ```

#### Frontend
- Add a new `FileUploadStep.tsx` component in `frontend/components/steps/`.
- Add the `"file_uploads"` phase to `ChatPhase` type.
- In `useCampaignChat.ts`, after the image upload phase, transition to `"file_uploads"`, then to questions.

---

## 6. CHANGE 5 — HOUSING Special Ad Category Compliance

### Reasoning
Real estate ads on Meta are classified under **Special Ad Category: HOUSING**. This imposes strict targeting restrictions that MUST be enforced:

- **Age**: Must be 18–65+ (cannot narrow)
- **Gender**: Cannot target by gender (must be "all")
- **ZIP/postal code**: Cannot target by ZIP
- **Multicultural affinity**: Cannot use
- **Minimum radius**: 15 miles for location targeting
- Must declare `special_ad_categories: ["HOUSING"]` on campaign creation

### Files to modify

#### `backend/nodes/media_buying.py`
- The media buying prompt must instruct the LLM to NOT set age_min/age_max or gender restrictions.
- After the LLM returns its output, apply a **hard override**:
  ```python
  # HOUSING compliance — override any LLM targeting that violates Meta rules
  audience = media_output.get("audience", {})
  audience["age_min"] = 18
  audience["age_max"] = 65
  audience["genders"] = ["all"]
  media_output["audience"] = audience
  media_output["special_ad_category"] = "HOUSING"
  ```

#### `backend/nodes/merge.py`
- In the `campaign_bundle` assembly, add `special_ad_categories`:
  ```python
  "campaign": {
      ...
      "special_ad_categories": ["HOUSING"],
  },
  ```
- In the audience override section, force HOUSING-compliant targeting:
  ```python
  # HOUSING compliance — hard override
  audience["age_min"] = 18
  audience["age_max"] = 65
  audience["genders"] = ["all"]
  ```

#### `backend/meta_client.py`
- In `RealMetaClient.create_campaign()`, set:
  ```python
  params = {
      ...
      Campaign.Field.special_ad_categories: ["HOUSING"],
      ...
  }
  ```
- In `SimulatedMetaClient.create_campaign()`, include `"special_ad_categories": ["HOUSING"]` in the response.
- In `create_ad_set()`, ensure targeting never includes age/gender restrictions.

#### `backend/templates/locales/en/media_buying.py` and `ar/media_buying.py`
- Update the SYSTEM prompt to explicitly state HOUSING restrictions:
  ```
  "CRITICAL: This is a HOUSING campaign (real estate). Meta's Special Ad Category rules apply:\n"
  "- age_min MUST be 18, age_max MUST be 65 (cannot narrow)\n"
  "- genders MUST be ['all'] (cannot target by gender)\n"
  "- Cannot target by ZIP code or multicultural affinity\n"
  "- Must use broad geographic targeting (city-level minimum)\n"
  "- Set special_ad_category: 'HOUSING' in your output\n"
  ```

---

## 7. CHANGE 6 — Rewrite All Prompt Templates for Real Estate

### Reasoning
All LLM prompts must be rewritten to be real-estate-specific instead of generic product/business/service prompts.

### Files to rewrite (both `en/` and `ar/` locales)

#### `templates/locales/en/question_generator.py` and `ar/question_generator.py`
- Replace the generic `_TARGET_BASE` with a real-estate-specific version.
- Campaign target options should be real-estate-specific:
  ```python
  TARGET_FALLBACK_OPTIONS = [
      {"label": "Lead Generation", "description": "People leave their phone number or WhatsApp to be contacted by your sales team.",
       "goal": "generate qualified leads for the real estate project", "recommended": True},
      {"label": "Brand Awareness", "description": "More people learn about your compound and its unique features.",
       "goal": "build awareness for the compound so more people know about it", "recommended": False},
      {"label": "Website Traffic", "description": "People visit your website or landing page to see unit details and pricing.",
       "goal": "drive traffic to the project page for detailed information", "recommended": False},
      {"label": "Project Launch Event", "description": "People register for a launch event, site visit, or open house.",
       "goal": "get registrations for the project launch event or site visit", "recommended": False},
  ]
  ```
- The adaptive question SYSTEM prompt should reference real estate topics:
  ```
  coverage="compound unique features, competitive advantages, target buyer profile (investors vs home buyers, luxury vs mid-range), construction status, nearby facilities, and developer reputation"
  ```
- Change all `{kind}` placeholders from "product/business/service" to "real estate project/compound".
- No longer use a dict keyed by marketing_type — use a single string since marketing_type is always "real_estate".

#### `templates/locales/en/orchestrator.py` and `ar/orchestrator.py`
- Rewrite the SYSTEM prompt to be a senior **real estate advertising strategist**:
  ```python
  SYSTEM = (
      "You are a senior Meta advertising strategist specialising in Egyptian real estate campaigns.\n"
      "You will receive photos of a real estate compound/project and a campaign brief including "
      "compound details, unit types, pricing, payment plans, and offers.\n"
      "Return ONLY a valid JSON object matching this schema:\n"
      "{\n"
      '  "product_type": "Real Estate",\n'
      '  "product_description": "<1-2 sentence description of the compound and its key selling points>",\n'
      '  "platform": "<instagram|facebook|both>",\n'
      '  "objective": "<MESSAGES|TRAFFIC|LEADS|AWARENESS>",\n'
      '  "tone": "<tone descriptor>",\n'
      '  "target_audience_hint": "<ideal buyer profile>",\n'
      '  "key_selling_points": ["<point1>", "<point2>", "<point3>"],\n'
      '  "budget": <number>,\n'
      '  "currency": "EGP"\n'  # Egyptian real estate uses EGP
      "}\n"
      "Rules:\n"
      "- This is a HOUSING campaign — set special_ad_category to HOUSING\n"
      "- Platform: luxury compounds → instagram-heavy, mid-range → both, investment → facebook-heavy\n"
      "- Objective: LEADS for lead generation goals, MESSAGES for WhatsApp goals, AWARENESS for brand goals\n"
      "- Tone: luxury → 'exclusive and aspirational', mid-range → 'warm and family-oriented', "
      "investment → 'confident and opportunity-driven'\n"
      "- key_selling_points: focus on location, payment plan, offer, amenities\n"
      "- target_audience_hint: include buyer type (investor/home buyer), income bracket, family status"
  )
  ```

#### `templates/locales/en/creative.py` and `ar/creative.py`
- Rewrite for real estate ad copy:
  ```python
  SYSTEM = (
      "You are a scroll-stopping Meta ads copywriter who specialises in Egyptian real estate.\n"
      "The best real estate ads create urgency, highlight the offer, and make people feel they're "
      "about to miss a unique opportunity.\n"
      "You know the Egyptian real estate market: payment plans matter, location is king, "
      "and a strong offer closes the deal.\n\n"
      "Return ONLY a valid JSON object:\n"
      "{\n"
      '  "copies": ["<copy1>", "<copy2>", "<copy3>"],\n'
      '  "headlines": ["<h1>", "<h2>", "<h3>"],\n'
      '  "cta": "<cta_text>"\n'
      "}\n"
      "Copywriting frameworks — use a DIFFERENT one for each copy:\n"
      "  1. Offer-led: Lead with the payment plan or special offer (e.g. '0% down payment')\n"
      "  2. Lifestyle: Paint the dream — describe the life awaiting the buyer in this compound\n"
      "  3. Urgency/Scarcity: Limited units, prices going up, last phase — create FOMO\n"
      "Rules:\n"
      "- Each copy: under 125 characters, in the campaign's language\n"
      "- Each headline: under 40 characters\n"
      "- MUST mention: compound name, location, and either price or offer\n"
      "- CTA: LEADS → 'Sign Up', MESSAGES → 'Send Message', TRAFFIC → 'Learn More'\n"
      "- Do NOT generate a visual_prompt — we use real photos, not AI images\n"
  )
  ```
- Remove `visual_prompt` from the output schema.

#### `templates/locales/en/media_buying.py` and `ar/media_buying.py`
- Update for real estate with HOUSING compliance (see CHANGE 5 above).
- Add real estate-specific interest targeting:
  ```
  "- interests: use real-estate-relevant Meta interests such as 'Real estate', "
  "'Property investment', 'Luxury real estate', 'Home buying', 'Interior design', "
  "'New homes', 'Mortgage' — pick 3-5 most relevant based on the price tier\n"
  ```

#### `templates/locales/en/strategy.py` and `ar/strategy.py`
- Update the persona and channel strategy for real estate:
  ```
  "Adapt to the real estate project's price tier:\n"
  "- Under 2M EGP: young couples, first-time buyers → Facebook 60%/Instagram 40%\n"
  "- 2M-5M EGP: mid-income families → Facebook 50%/Instagram 50%\n"
  "- 5M-15M EGP: upper professionals → Instagram 60%/Facebook 40%\n"
  "- Above 15M EGP: high-net-worth, investors → Instagram 70%/Facebook 30%\n"
  ```

---

## 8. CHANGE 7 — Update Frontend Copy, Branding & Landing Page

### Files to modify

#### `frontend/components/Landing.tsx`
- Update the hero text for real estate:
  ```tsx
  // BEFORE:
  "Your own ad, ready to go — just answer a few simple questions."

  // AFTER:
  "Your real estate ad, ready to go — just upload photos and answer a few questions."
  ```
- Update the subtitle:
  ```tsx
  // BEFORE:
  "Share a photo (or let AI make one), pick a budget, and Mark guides you the rest of the way"

  // AFTER:
  "Upload your unit photos, share your compound details, and Mark builds a professional Meta ad campaign for you — in plain language, no marketing experience needed."
  ```
- Update feature chips:
  ```tsx
  // BEFORE:
  ["💬 Simple questions", "🖼️ Pictures made for you", "✍️ Words that sell", "🚀 Publish in one tap"]

  // AFTER:
  ["🏗️ Built for real estate", "📸 Your actual unit photos", "✍️ Ad copy that converts", "🚀 Publish to Meta in one tap"]
  ```
- Update CTA button text:
  ```tsx
  // BEFORE: "Let's make my ad →"
  // AFTER: "Create my real estate campaign →"
  ```

#### `frontend/components/ChatExperience.tsx`
- Update the header branding:
  ```tsx
  // BEFORE:
  <h1>AutoMark AI</h1>
  <p>Your friendly ad helper</p>

  // AFTER:
  <h1>AutoMark AI</h1>
  <p>Your real estate campaign assistant</p>
  ```

#### `frontend/lib/copy.ts`
- Update the `greeting` message:
  ```
  // EN:
  "Hi! I'm **Mark**, your real estate campaign assistant. ✨ Upload your unit photos, tell me about your compound, and I'll build a ready-to-publish Meta ad campaign for you — step by step, no marketing experience needed."

  // AR:
  "أهلاً! أنا **مارك**، مساعدك لحملات العقارات. ✨ ارفع صور الوحدات، قوللي عن الكمبوند، وأنا هجهزلك حملة إعلانية جاهزة للنشر على ميتا — خطوة بخطوة، ومن غير أي خبرة في التسويق."
  ```
- Update all relevant copy strings to reference "compound", "units", "project" instead of "product/business/service".

#### `frontend/components/StageRail.tsx`
- Update the stage labels:
  ```
  // BEFORE: "1. Setup" → "2. Product Questions" → "3. Image Review" → ...
  // AFTER: "1. Photos & Files" → "2. Compound Details" → "3. Campaign Setup" → "4. Photo Selection" → "5. Ad Copy Review" → "6. Publish"
  ```

---

## 9. CHANGE 8 — Smart Defaults Based on Price Range

### Reasoning
The system should auto-infer sensible defaults from the compound's price range. These become the **recommended** values in subsequent questions and the defaults for the strategy/media nodes.

### Price tier logic

```python
def get_price_tier(starting_price_egp: float) -> dict:
    """Return smart defaults based on the real estate price tier."""
    if starting_price_egp < 2_000_000:
        return {
            "tier": "affordable",
            "tone": "warm and family-oriented",
            "platform_split": {"facebook": 0.6, "instagram": 0.4},
            "buyer_type": "first-time buyers, young couples",
            "archetype": "millennial_general",
        }
    elif starting_price_egp < 5_000_000:
        return {
            "tier": "mid_range",
            "tone": "modern and aspirational",
            "platform_split": {"facebook": 0.5, "instagram": 0.5},
            "buyer_type": "mid-income families, upgraders",
            "archetype": "millennial_general",
        }
    elif starting_price_egp < 15_000_000:
        return {
            "tier": "premium",
            "tone": "exclusive and lifestyle-driven",
            "platform_split": {"facebook": 0.4, "instagram": 0.6},
            "buyer_type": "upper professionals, executive families",
            "archetype": "professionals_b2b",
        }
    else:
        return {
            "tier": "luxury",
            "tone": "exclusive and aspirational",
            "platform_split": {"facebook": 0.3, "instagram": 0.7},
            "buyer_type": "high-net-worth individuals, investors",
            "archetype": "professionals_b2b",
        }
```

### Where to apply
- Add this function in a new file `backend/real_estate_utils.py`.
- Call it in `orchestrator_node` after the questions are done, passing the `starting_price` from `real_estate_data`.
- Include the tier data in the `campaign_plan` so strategy and media nodes can use it.
- In the question interrupt for "offer", adjust the recommendation based on tier (luxury → "Discount on Cash", affordable → "Zero Down Payment").

---

## 10. CHANGE 9 — Update the Campaign Bundle & Meta Publishing

### Files to modify

#### `backend/nodes/merge.py`
- Add a `real_estate_project` section to the bundle:
  ```python
  campaign_bundle = {
      ...
      "real_estate_project": {
          "compound_name": real_estate_data.get("compound_name", ""),
          "developer": real_estate_data.get("developer", ""),
          "location": real_estate_data.get("location", ""),
          "unit_types": real_estate_data.get("unit_types", []),
          "starting_price": real_estate_data.get("starting_price", ""),
          "payment_plan": real_estate_data.get("payment_plan", ""),
          "offer": real_estate_data.get("offer", ""),
          "lead_destination": state.get("lead_destination", "whatsapp"),
      },
      ...
  }
  ```
- The `campaign` section should include `special_ad_categories: ["HOUSING"]`.
- Calculate `daily_budget` using `campaign_duration_days` instead of hardcoded 7:
  ```python
  duration = state.get("campaign_duration_days", 14)
  daily_budget = budget / duration
  ```

#### `backend/meta_client.py`
- Both `SimulatedMetaClient` and `RealMetaClient`:
  - In `create_campaign`: set `special_ad_categories: ["HOUSING"]`.
  - In `create_ad_set`: enforce HOUSING targeting restrictions.
  - In `create_ad_creative`: use the first selected photo (not AI-generated).

---

## 11. Reference Files

These are the data files provided by the user that informed this transformation. They should be consulted during implementation:

### `data/mediaBuyingQuestionsAndDocs.txt`
Contains the full list of questions a real estate media buyer would ask. We've curated these down to the 8-10 most critical questions listed in CHANGE 3 above. The remaining questions are either auto-inferred, handled by the LLM as follow-ups, or dropped as too technical.

### `data/meta_real_estate_campaign_schema.json`
Contains the Meta campaign JSON schema with all fields needed for a real estate campaign. The question flow (CHANGE 3) maps user answers to these fields:

| Schema Field | Populated From |
|-------------|---------------|
| `campaign.objective` | Campaign target question (Q7) |
| `campaign.daily_budget` | Budget ÷ campaign_duration_days |
| `campaign.special_ad_category` | Hardcoded: `"HOUSING"` |
| `campaign.start_date` / `end_date` | Today + campaign_duration_days |
| `ad_set.conversion_location` | Lead destination question (Q8) |
| `ad_set.targeting.locations` | Derived from compound location (Q2) |
| `ad_set.targeting.minimum_age` | Hardcoded: 18 (HOUSING rule) |
| `ad_set.targeting.maximum_age` | Hardcoded: 65 (HOUSING rule) |
| `ad_set.targeting.genders` | Hardcoded: "all" (HOUSING rule) |
| `ad.primary_text` | AI-generated (creative node) |
| `ad.headline` | AI-generated (creative node) |
| `ad.call_to_action` | Derived from campaign objective |
| `ad.media.images` | User's uploaded unit photos |
| `real_estate_project.*` | Direct mapping from questions Q1–Q6 |
| `client_assets.*` | File uploads (logo, brochure, etc.) |
| `kpis.*` | Auto-set by AI based on budget + market benchmarks (NOT asked) |

---

## Execution Order

Implement the changes in this order to minimize breakage:

1. **CHANGE 1** (Remove marketing type) — minimal, unblocks everything else
2. **CHANGE 6** (Rewrite prompts) — can be done in parallel with frontend changes
3. **CHANGE 3** (Real estate questions) — the biggest change, core logic
4. **CHANGE 2** (Multi-photo upload, remove AI images) — affects both frontend and backend
5. **CHANGE 4** (File uploads) — new feature, additive
6. **CHANGE 5** (HOUSING compliance) — enforcement layer on top of existing
7. **CHANGE 8** (Smart defaults) — refinement layer
8. **CHANGE 7** (Frontend copy & branding) — cosmetic, do last
9. **CHANGE 9** (Bundle & publish updates) — integration, do last

---

## New Pipeline Flow (After All Changes)

```
START
  → language selection (keep existing)
  → multi-photo upload (new — required, multiple files)
  → file uploads: logo (required), brochure/floor plans/master plan/price list (optional)
  → budget input (keep existing)
  → campaign target selection (keep existing — but real-estate-specific options)
  → real estate interview:
      Q1: Compound name (free text)
        → LLM follow-up? (optional)
      Q2: Location (options + other)
        → LLM follow-up? (optional)
      Q3: Unit types (multi-select + other)
        → LLM follow-up? (optional)
      Q4: Starting price (free text)
        → LLM follow-up? (optional)
      Q5: Payment terms (free text)
        → LLM follow-up? (optional)
      Q6: Current offer (options + other)
        → LLM follow-up? (optional)
      Q7: Lead destination (options + other)
        → LLM follow-up? (optional)
      Q8: Campaign duration (options + other)
  → orchestrator_node (real estate campaign plan)
  → strategy_node (persona + channels + timing — real estate specific)
  → fan-out:
      creative_node (real estate ad copy — NO AI image generation)
      media_buying_node (HOUSING-compliant targeting)
  → photo_select_node (user picks which uploaded photos to use)
  → text_review_node (user reviews/edits ad copy)
  → merge_node (assemble bundle with real_estate_project section)
  → done → publish to Meta (with HOUSING category)
```
