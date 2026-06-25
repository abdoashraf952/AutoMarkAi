// ------------------------------------------------------------------ //
// Conversational copy for the chatbot, bilingual (en / ar).           //
// Keeps the assistant's voice consistent and easy to tune.            //
// ------------------------------------------------------------------ //

import type { Language, MarketingType } from "./types";

type Dict = Record<string, string>;

const EN = {
  greeting:
    "Hey, I'm **Mark** — your AI media buyer. ✨ I'll turn your photo into a ready-to-publish Meta ad campaign. Let's do this step by step.",
  askLanguage: "First — which language should we work in?",
  askMarketingType: "Great. What are you marketing today?",
  askImage: "Perfect. Drop in a photo of it — this becomes the heart of your ad. 📸",
  askImageMode: "Nice shot! Should I use it as-is, or enhance it with AI for a more polished, ad-ready look?",
  askBudget: "How much do you want to invest in this campaign (total, in USD)? 💰",
  askGoal:
    "Last setup question — what's the goal? Tell me in your own words what you want this campaign to achieve.",
  startingPipeline: "Love it. Give me a moment to study your product…",
  questionsIntro:
    "I studied your product and I have a few quick questions so the campaign fits perfectly. I'll ask them one at a time. 👇",
  questionProgress: "Question {n} of {total}",
  buildingCampaign: "Brilliant answers. Now I'm building your whole campaign…",
  imageReviewIntro: "Here's your ad visual. What do you think?",
  imageConfirmIntro: "Here's the photo we'll use for your ad. Looks good?",
  regenerating: "On it — reworking the visual with your notes…",
  regensLeft: "You can re-tweak this {n} more time(s) — after that I'll show you all the versions to pick from.",
  regensNoneLeft:
    "Heads up — this is your last version. If it's not the one, I'll show you all the versions to pick your favourite.",
  seeAllVersions: "Show me all the versions",
  gatheringVersions: "Gathering all your versions…",
  maxRegenIntro:
    "We've hit the re-enhancement limit. Here's every version we created — pick the one you like best:",
  textReviewIntro: "Now the words. Here's the copy I wrote for your ad:",
  editingCopy: "Got it — rewriting the copy with your direction…",
  doneIntro:
    "🎉 Your campaign is ready! Here's the full package. Review it, then publish whenever you're ready.",
  publishing: "Sending your campaign to Meta…",
  publishedSim:
    "✅ Done! Your campaign was published **(demo mode)** — a paused sponsored ad and an organic post were created.",
  publishedLive:
    "✅ Published live to Meta! Your sponsored ad is created (paused) and your organic post is up.",
  startOver: "Want to create another campaign, or wrap up here?",
  endGoodbye: "Thanks for using **AutoMark AI**! 👋 Your campaign is all set. See you next time.",
  // labels
  endBtn: "End & exit",
  pickAbove: "Tap an image above to choose it ☝️",
  yourPhoto: "Your photo",
  enhancedImage: "AI-enhanced visual",
  approve: "Approve",
  regenerate: "Tweak it",
  send: "Send",
  submitAnswer: "Send answer",
  approveCopy: "Approve copy",
  requestChanges: "Request changes",
  thinkingNextQ: "Thinking of the next question…",
  textReviewPickIntro:
    "Pick the copy and headline you like best — and tweak the wording if you want. ✍️",
  chooseCopy: "Choose your ad copy",
  chooseHeadline: "Choose your headline",
  ctaLabel: "Call to action",
  editIfNeeded: "Edit if needed",
  confirmSelection: "Confirm & continue",
  pickEditHint: "Pick & edit your copy above, then confirm ☝️",
  publishBtn: "Publish to Meta",
  newCampaign: "New campaign",
  useOriginal: "Use my photo",
  enhanceAI: "Enhance with AI",
  feedbackPlaceholderImg: "What should change? e.g. brighter background, remove the text…",
  feedbackPlaceholderText: "e.g. make the tone more urgent and shorten the copies",
  budgetPlaceholder: "500",
  goalPlaceholder: "e.g. get WhatsApp leads for my luxury watches",
} satisfies Dict;

const AR: Dict = {
  greeting:
    "أهلاً، أنا **مارك** — الميديا باير بتاعك بالـ AI. ✨ هحوّل صورتك لحملة إعلانية جاهزة للنشر على ميتا. يلا نبدأ خطوة بخطوة.",
  askLanguage: "الأول — نشتغل بأنهي لغة؟",
  askMarketingType: "تمام. بتسوّق إيه النهارده؟",
  askImage: "حلو. ارفع صورة للمنتج — دي هتبقى قلب الإعلان. 📸",
  askImageMode:
    "صورة جميلة! أستخدمها زي ما هي، ولا أحسّنها بالـ AI عشان تبقى أنسب للإعلانات؟",
  askBudget: "عايز تستثمر كام في الحملة دي (الإجمالي بالدولار)؟ 💰",
  askGoal: "آخر سؤال في الإعداد — إيه الهدف؟ قوللي بكلامك عايز الحملة تحقق إيه.",
  startingPipeline: "تحفة. سيبني لحظة أدرس منتجك…",
  questionsIntro:
    "درست منتجك وعندي كام سؤال سريع عشان الحملة تطلع مظبوطة. هسألك سؤال سؤال. 👇",
  questionProgress: "سؤال {n} من {total}",
  buildingCampaign: "إجابات رائعة. دلوقتي بببني حملتك كاملة…",
  imageReviewIntro: "دي صورة إعلانك. رأيك إيه؟",
  imageConfirmIntro: "دي الصورة اللي هنستخدمها في الإعلان. تمام؟",
  regenerating: "تمام — بعدّل الصورة حسب ملاحظاتك…",
  regensLeft: "فاضلك {n} محاولات تعديل. بعد كده هتختار من كل النسخ اللي عملناها.",
  regensNoneLeft:
    "خد بالك — دي آخر نسخة. لو مش عاجباك، هوريك كل النسخ تختار منهم اللي يعجبك.",
  seeAllVersions: "وريني كل النسخ",
  gatheringVersions: "بجمعلك كل النسخ…",
  maxRegenIntro:
    "وصلنا للحد الأقصى للتعديل. دي كل النسخ اللي عملناها — اختار اللي عاجباك:",
  textReviewIntro: "دلوقتي الكلام. دي النصوص اللي كتبتها لإعلانك:",
  editingCopy: "تمام — بعيد كتابة النصوص حسب توجيهك…",
  doneIntro: "🎉 حملتك جاهزة! ده الباكدج الكامل. راجعه، وبعدين انشر وقت ما تحب.",
  publishing: "ببعت حملتك لميتا…",
  publishedSim:
    "✅ تمام! حملتك اتنشرت **(وضع تجريبي)** — اتعمل إعلان ممول (متوقف) وبوست عضوي.",
  publishedLive:
    "✅ اتنشرت لايف على ميتا! الإعلان الممول اتعمل (متوقف) والبوست العضوي اتنشر.",
  startOver: "عايز تعمل حملة تانية، ولا نخلص هنا؟",
  endGoodbye: "شكراً لاستخدامك **AutoMark AI**! 👋 حملتك جاهزة. لحد ما نتقابل تاني.",
  endBtn: "إنهاء وخروج",
  pickAbove: "اختار صورة من فوق ☝️",
  yourPhoto: "صورتك",
  enhancedImage: "صورة محسّنة بالـ AI",
  approve: "موافق",
  regenerate: "عدّلها",
  send: "إرسال",
  submitAnswer: "إرسال الإجابة",
  approveCopy: "موافق على النص",
  requestChanges: "اطلب تعديلات",
  thinkingNextQ: "بفكر في السؤال اللي بعده…",
  textReviewPickIntro:
    "اختار النص والعنوان اللي عاجبينك — وعدّل الصياغة لو حابب. ✍️",
  chooseCopy: "اختار نص الإعلان",
  chooseHeadline: "اختار العنوان",
  ctaLabel: "زر الإجراء",
  editIfNeeded: "عدّل لو محتاج",
  confirmSelection: "تأكيد ومتابعة",
  pickEditHint: "اختار وعدّل النص من فوق، وبعدين أكّد ☝️",
  publishBtn: "انشر على ميتا",
  newCampaign: "حملة جديدة",
  useOriginal: "استخدم صورتي",
  enhanceAI: "حسّن بالـ AI",
  feedbackPlaceholderImg: "تغيّر إيه؟ مثلاً خلفية أفتح، شيل النص…",
  feedbackPlaceholderText: "مثلاً خلي النبرة أكثر إلحاحاً واختصر النصوص",
  budgetPlaceholder: "٥٠٠",
  goalPlaceholder: "مثال: أجيب عملاء واتساب للساعات الفاخرة",
};

export type CopyKey = keyof typeof EN;

export function t(lang: Language, key: CopyKey, vars?: Record<string, string | number>): string {
  const table = lang === "ar" ? AR : EN;
  let s = table[key] ?? EN[key];
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
    }
  }
  return s;
}

export const MARKETING_TYPE_OPTIONS: Record<
  Language,
  { value: MarketingType; label: string; sub: string; emoji: string }[]
> = {
  en: [
    { value: "product", label: "A Product", sub: "A physical or digital item you sell", emoji: "📦" },
    { value: "business", label: "A Business", sub: "A shop, clinic, restaurant, or brand", emoji: "🏪" },
    { value: "service", label: "A Service", sub: "Consulting, cleaning, tutoring, design…", emoji: "🛠️" },
  ],
  ar: [
    { value: "product", label: "منتج", sub: "حاجة بتبيعها (هاردوير، ملابس، أكل، تطبيق)", emoji: "📦" },
    { value: "business", label: "بيزنس", sub: "محل، عيادة، مطعم، أو براند", emoji: "🏪" },
    { value: "service", label: "خدمة", sub: "استشارات، تنظيف، تدريس، تصميم…", emoji: "🛠️" },
  ],
};
