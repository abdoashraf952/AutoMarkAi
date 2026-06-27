// ------------------------------------------------------------------ //
// Conversational copy for the chatbot, bilingual (en / ar).           //
// Real estate campaign assistant ("Mark").                            //
// ------------------------------------------------------------------ //

import type { Language } from "./types";

type Dict = Record<string, string>;

const EN = {
  greeting:
    "Hi! I'm **Mark**, your real estate campaign assistant. ✨ Upload your unit photos, tell me about your compound, and I'll build a ready-to-publish Meta ad campaign for you — step by step, no marketing experience needed.",
  askLanguage: "First — which language feels most comfortable?",
  // Photos
  askUnitPhotos: "Upload photos of the units you want to advertise 📸",
  photoRequired: "At least one unit photo is required.",
  photosAdded: "Your unit photos",
  imageInvalid: "Please use JPG, PNG, or WebP images.",
  yourPhoto: "Your photo",
  // File uploads
  uploadsIntro:
    "Great. Now let's add your marketing assets — I'll ask for them one at a time. The logo is required; the rest are optional.",
  askLogo: "Upload your company logo",
  logoWhy: "We'll place your logo on the ad creative so the brand stands out.",
  askBrochure: "Upload a brochure PDF (optional)",
  brochureWhy: "Helps me pull accurate project details and selling points.",
  askFloorPlans: "Upload floor plans (optional)",
  floorPlansWhy: "Useful for highlighting layouts buyers care about.",
  askMasterPlan: "Upload a master plan image (optional)",
  masterPlanWhy: "Shows the full compound layout and amenities.",
  askPriceList: "Upload a price list (optional)",
  priceListWhy: "Lets me reference accurate pricing in the ad copy.",
  fileSkip: "Skip",
  fileDoneBtn: "Done with uploads →",
  fileAdded: "Uploaded ✓",
  // Budget
  askBudget: "How much would you like to spend in total? (in USD) 💰",
  budgetPlaceholder: "500",
  // Campaign target
  askTarget:
    "Here's what I'd aim for based on your units. Which goal sounds right? I've starred my top pick. 👇",
  // Questions
  questionsIntro:
    "Thanks! A few quick questions about your compound so the ad fits perfectly. I'll ask one at a time. 👇",
  questionProgress: "Question {n} of {total}",
  followUpProgress: "Quick follow-up",
  thinkingNextQ: "Thinking of the next question…",
  otherOption: "Other",
  otherPlaceholder: "Type your answer…",
  confirmMulti: "Confirm",
  // Building
  buildingCampaign: "Great answers! Now I'm putting your whole campaign together…",
  // Photo select
  photoSelectIntro: "Pick which photos to include in your ad 📸",
  photoSelectHint: "Tap photos to select, then confirm ☝️",
  confirmPhotos: "Use these photos",
  // Text review
  textReviewPickIntro:
    "Pick the copy and headline you like best — and tweak the wording if you want. ✍️",
  pickEditHint: "Pick & edit your copy above, then confirm ☝️",
  confirmSelection: "Confirm & continue",
  chooseCopy: "Choose your ad copy",
  chooseHeadline: "Choose your headline",
  ctaLabel: "Call to action",
  editIfNeeded: "Edit if needed",
  // Done / publish
  doneIntro:
    "🎉 Your campaign is ready! Here's the full package. Review it, then publish whenever you're ready.",
  publishBtn: "Publish to Meta",
  publishing: "Sending your campaign to Meta…",
  publishedSim:
    "✅ Done! Your campaign was published **(demo mode)** — a paused sponsored ad and an organic post were created.",
  publishedLive:
    "✅ Published live to Meta! Your sponsored ad is created (paused) and your organic post is up.",
  startOver: "Want to create another campaign, or wrap up here?",
  endGoodbye: "Thanks for using **AutoMark AI**! 👋 Your campaign is all set. See you next time.",
  endBtn: "End & exit",
  newCampaign: "New campaign",
  // generic
  approve: "Approve",
  send: "Send",
  submitAnswer: "Send answer",
} satisfies Dict;

const AR: Dict = {
  greeting:
    "أهلاً! أنا **مارك**، مساعدك لحملات العقارات. ✨ ارفع صور الوحدات، قوللي عن الكمبوند، وأنا هجهزلك حملة إعلانية جاهزة للنشر على ميتا — خطوة بخطوة، ومن غير أي خبرة في التسويق.",
  askLanguage: "الأول — نشتغل بأنهي لغة؟",
  askUnitPhotos: "ارفع صور الوحدات اللي عايز تعلن عنها 📸",
  photoRequired: "لازم صورة وحدة واحدة على الأقل.",
  photosAdded: "صور الوحدات بتاعتك",
  imageInvalid: "من فضلك استخدم صور JPG أو PNG أو WebP.",
  yourPhoto: "صورتك",
  uploadsIntro:
    "تمام. دلوقتي نضيف ملفاتك التسويقية — هطلبهم واحد واحد. اللوجو مطلوب، والباقي اختياري.",
  askLogo: "ارفع لوجو الشركة",
  logoWhy: "هنحط اللوجو على الإعلان عشان البراند يبان.",
  askBrochure: "ارفع بروشور PDF (اختياري)",
  brochureWhy: "بيساعدني أطلع تفاصيل المشروع ونقاط البيع بدقة.",
  askFloorPlans: "ارفع مخططات الوحدات (اختياري)",
  floorPlansWhy: "مفيد لإبراز التصميمات اللي العميل بيهتم بيها.",
  askMasterPlan: "ارفع صورة الماستر بلان (اختياري)",
  masterPlanWhy: "بتوضح شكل الكمبوند كله والخدمات.",
  askPriceList: "ارفع قائمة الأسعار (اختياري)",
  priceListWhy: "بتخليني أذكر أسعار دقيقة في الإعلان.",
  fileSkip: "تخطّى",
  fileDoneBtn: "خلصت الرفع →",
  fileAdded: "اترفع ✓",
  askBudget: "عايز تصرف كام في الإجمالي؟ (بالدولار) 💰",
  budgetPlaceholder: "٥٠٠",
  askTarget:
    "ده اللي أنصحك بيه حسب وحداتك. أنهي هدف مناسب ليك؟ علّمت اختياري المفضّل بنجمة. 👇",
  questionsIntro:
    "تمام! كام سؤال سريع عن الكمبوند عشان الإعلان يطلع مظبوط. هسألك سؤال سؤال. 👇",
  questionProgress: "سؤال {n} من {total}",
  followUpProgress: "سؤال متابعة سريع",
  thinkingNextQ: "بفكر في السؤال اللي بعده…",
  otherOption: "غير كده",
  otherPlaceholder: "اكتب إجابتك…",
  confirmMulti: "تأكيد",
  buildingCampaign: "إجابات رائعة! دلوقتي بجمّع حملتك كلها…",
  photoSelectIntro: "اختار الصور اللي عايز تحطها في الإعلان 📸",
  photoSelectHint: "دوس على الصور لاختيارها، وبعدين أكّد ☝️",
  confirmPhotos: "استخدم الصور دي",
  textReviewPickIntro:
    "اختار النص والعنوان اللي عاجبينك — وعدّل الصياغة لو حابب. ✍️",
  pickEditHint: "اختار وعدّل النص من فوق، وبعدين أكّد ☝️",
  confirmSelection: "تأكيد ومتابعة",
  chooseCopy: "اختار نص الإعلان",
  chooseHeadline: "اختار العنوان",
  ctaLabel: "زر الإجراء",
  editIfNeeded: "عدّل لو محتاج",
  doneIntro: "🎉 حملتك جاهزة! ده الباكدج الكامل. راجعه، وبعدين انشر وقت ما تحب.",
  publishBtn: "انشر على ميتا",
  publishing: "ببعت حملتك لميتا…",
  publishedSim:
    "✅ تمام! حملتك اتنشرت **(وضع تجريبي)** — اتعمل إعلان ممول (متوقف) وبوست عضوي.",
  publishedLive:
    "✅ اتنشرت لايف على ميتا! الإعلان الممول اتعمل (متوقف) والبوست العضوي اتنشر.",
  startOver: "عايز تعمل حملة تانية، ولا نخلص هنا؟",
  endGoodbye: "شكراً لاستخدامك **AutoMark AI**! 👋 حملتك جاهزة. لحد ما نتقابل تاني.",
  endBtn: "إنهاء وخروج",
  newCampaign: "حملة جديدة",
  approve: "موافق",
  send: "إرسال",
  submitAnswer: "إرسال الإجابة",
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
