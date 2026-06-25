"""Arabic UI strings and labels."""

MARKETING_TYPE_LABELS = {
    "product": "منتج",
    "business": "بيزنس",
    "service": "خدمة",
}

MARKETING_TYPE_DESCRIPTIONS = {
    "product": "منتج بتبيعه — زي هاردوير، ملابس، أكل، تطبيق",
    "business": "بيزنس بتعمله ترويج — زي مطعم، عيادة، محل",
    "service": "خدمة بتقدمها — زي استشارات، تنظيف، تدريس، تصميم",
}

STAGE_LABELS = {
    "setup": "١. الإعداد",
    "questions": "٢. أسئلة عن المنتج",
    "image_review": "٣. مراجعة الصورة",
    "max_regenerations_exceeded": "٣ب. اختار صورة",
    "text_review": "٤. مراجعة النصوص",
    "done": "٥. جاهز",
}

SETUP_HEADER = "إعداد الحملة"
QUESTIONS_HEADER = "قولنا عن {marketing_type}ك"
QUESTIONS_SUBTEXT = "جاوب على الأسئلة دي عشان نعمل الحملة الأنسب ليك:"
IMAGE_REVIEW_HEADER_ORIGINAL = "راجع صورتك"
IMAGE_REVIEW_HEADER_ENHANCED = "راجع الصورة الإعلانية المحسّنة"
IMAGE_REVIEW_SUBTEXT_ORIGINAL = "تأكد إن الصورة تمام قبل ما نكمل."
IMAGE_REVIEW_SUBTEXT_ENHANCED = "راجع الصورة المحسّنة بالـ AI. وافق عليها أو اطلب تعديل."
TEXT_REVIEW_HEADER = "راجع النصوص الإعلانية"
DONE_HEADER = "الحملة جاهزة"
MAX_REGEN_HEADER = "وصلت للحد الأقصى من التوليد"
MAX_REGEN_SUBTEXT = "اختار واحدة من الصور اللي اتعملت قبل كده عشان تكمل:"

SIMULATION_BANNER = (
    "شغّال في وضع التجربة — ربط بيانات ميتا في ملف `.env` "
    "واضبط `META_SIMULATION_MODE=false` عشان تنشر فعلاً."
)
