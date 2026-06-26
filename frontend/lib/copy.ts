// ------------------------------------------------------------------ //
// Conversational copy for the chatbot, bilingual (en / ar).           //
// Keeps the assistant's voice consistent and easy to tune.            //
// ------------------------------------------------------------------ //

import type { Language, MarketingType } from "./types";

type Dict = Record<string, string>;

const EN = {
  greeting:
    "Hi! I'm **Mark**, your friendly ad helper. ✨ Tell me a little about what you're promoting and I'll build a ready-to-publish ad for you — one step at a time, no marketing experience needed.",
  askLanguage: "First — which language feels most comfortable?",
  askMarketingType: "Lovely. What would you like to promote?",
  askImage:
    "Got a photo of it? Drop it in below — or skip and I'll create one for you. 📸",
  askImageMode: "Nice shot! Want me to use it as-is, or give it a polished, ad-ready makeover?",
  askBudget: "How much would you like to spend in total? (in USD) 💰",
  startingPipeline: "Love it. Give me a moment to take a look…",
  // Campaign target — the one fixed question, AI-ranked choices
  askTarget:
    "Here's what I'd aim for based on what I can see. Which goal sounds right for you? I've starred my top pick. 👇",
  targetIntro: "Now, what should this ad actually achieve?",
  questionsIntro:
    "Thanks! I've got a few quick questions so your ad fits perfectly. I'll ask one at a time — just answer in your own words. 👇",
  questionProgress: "Question {n}",
  buildingCampaign: "Great answers! Now I'm putting your whole ad together…",
  generatingImage: "Creating a picture for your ad…",
  aiCreatedImage: "AI-made visual",
  skipImage: "No photo? Let AI create one ✨",
  imageInvalid: "Please use a JPG, PNG, or WebP image.",
  askDescribe:
    "No problem — I'll make the picture for you. First, tell me about it in a sentence or two: what is it, and what makes it good? ✍️",
  describePlaceholder:
    "e.g. handmade scented soy candles, long-lasting, made from natural ingredients",
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
    "أهلاً! أنا **مارك**، مساعدك للإعلانات. ✨ قوللي شوية عن اللي بتروّجله وأنا هجهزلك إعلان جاهز للنشر — خطوة بخطوة، ومن غير أي خبرة في التسويق.",
  askLanguage: "الأول — نشتغل بأنهي لغة؟",
  askMarketingType: "تمام. عايز تروّج لإيه؟",
  askImage: "عندك صورة ليه؟ ارفعها تحت — أو تخطّى وأنا أعملك واحدة. 📸",
  askImageMode:
    "صورة جميلة! أستخدمها زي ما هي، ولا أعملها لمسة احترافية تخليها أنسب للإعلان؟",
  askBudget: "عايز تصرف كام في الإجمالي؟ (بالدولار) 💰",
  startingPipeline: "تحفة. سيبني لحظة أبص على اللي عندك…",
  askTarget:
    "ده اللي أنصحك بيه حسب اللي شايفه. أنهي هدف مناسب ليك؟ علّمت اختياري المفضّل بنجمة. 👇",
  targetIntro: "طيب، الإعلان ده المفروض يحقق إيه؟",
  questionsIntro:
    "تمام! عندي كام سؤال سريع عشان الإعلان يطلع مظبوط. هسألك سؤال سؤال — جاوب بكلامك. 👇",
  questionProgress: "سؤال {n}",
  buildingCampaign: "إجابات رائعة! دلوقتي بجمّع إعلانك كله…",
  generatingImage: "بعمل صورة لإعلانك…",
  aiCreatedImage: "صورة من الذكاء الاصطناعي",
  skipImage: "مفيش صورة؟ خلّي الـ AI يعملها ✨",
  imageInvalid: "من فضلك استخدم صورة JPG أو PNG أو WebP.",
  askDescribe:
    "ولا يهمك — هعملك الصورة بنفسي. الأول قوللي عنه في جملة أو اتنين: هو إيه، وإيه اللي بيميزه؟ ✍️",
  describePlaceholder:
    "مثال: شموع صويا معطّرة هاند ميد، بتفضل فترة طويلة، ومن مكونات طبيعية",
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
