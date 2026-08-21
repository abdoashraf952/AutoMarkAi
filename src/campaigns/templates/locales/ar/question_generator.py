"""Arabic (Egyptian) question-generator prompts — real estate.

Includes the campaign-target ranked multiple-choice prompt (always asked first)
and the follow-up decision prompt. Written in Egyptian colloquial Arabic
(العامية المصرية). Output is JSON. Every export is a plain string now.
"""

# ------------------------------------------------------------------ #
# 1. Campaign target — ranked multiple-choice                         #
# ------------------------------------------------------------------ #
TARGET_SYSTEM = (
    "بتساعد شركة عقارات مصرية تختار أحسن هدف واحد لحملة إعلانية على ميتا لمشروع/كمبوند.\n"
    "هتستلم صور الوحدات والميزانية.\n"
    "رجّع قائمة اختيارات مرتبة، الأحسن الأول، لأهداف الحملة العقارية:\n"
    "  - جمع عملاء محتملين (الناس تسيب رقمها/واتساب لفريق المبيعات)\n"
    "  - انتشار البراند (ناس أكتر تعرف الكمبوند ومميزاته)\n"
    "  - زيارات للموقع (الناس تزور صفحة تشوف الوحدات والأسعار والتفاصيل)\n"
    "  - حدث إطلاق المشروع (الناس تسجل لحضور إطلاق أو زيارة موقع)\n"
    "اختار أهم 4 مناسبين للمشروع ده، مرتبين حسب الأنسب.\n"
    "علّم واحد بس كأنه (recommended) — الأنسب، ويكون الأول (غالباً جمع عملاء محتملين).\n"
    "رجّع JSON بس بالشكل ده (من غير markdown ولا أي كلام زيادة):\n"
    "{{\n"
    '  "options": [\n'
    '    {{"label": "<اسم الهدف بشكل بسيط>", "description": "<جملة بسيطة بتوضح هيحصل إيه>", '
    '"goal": "<جملة هدف بالعربي تتبعت لمخطّط الحملة>", "recommended": true}},\n'
    "    ... 4 اختيارات، مرتبين الأحسن الأول، واحد بس recommended ...\n"
    "  ]\n"
    "}}"
)

TARGET_USER_TEMPLATE = (
    "الميزانية: ${budget}\n\n"
    "حلّل صور الوحدات ورشّح أحسن هدف للحملة. "
    "رجّع بس اختيارات JSON المرتبة الموضحة فوق."
)

TARGET_FALLBACK_OPTIONS = [
    {"label": "جمع عملاء محتملين", "description": "الناس تسيب رقمها أو واتساب عشان فريق المبيعات يكلمها.",
     "goal": "generate qualified leads for the real estate project", "recommended": True},
    {"label": "انتشار البراند", "description": "ناس أكتر تعرف الكمبوند ومميزاته.",
     "goal": "build awareness for the compound so more people know about it", "recommended": False},
    {"label": "زيارات للموقع", "description": "الناس تزور صفحتك تشوف تفاصيل الوحدات والأسعار.",
     "goal": "drive traffic to the project page for detailed information", "recommended": False},
    {"label": "حدث إطلاق المشروع", "description": "الناس تسجل لحضور إطلاق أو زيارة موقع.",
     "goal": "get registrations for the project launch event or site visit", "recommended": False},
]

# ------------------------------------------------------------------ #
# 2. Follow-up decision — one optional question after a fixed answer  #
# ------------------------------------------------------------------ #
FOLLOW_UP_SYSTEM = (
    "إنت مساعد ميديا باير عقاري. بتجمع معلومات عن كمبوند عشان تعمل حملة إعلانية على ميتا.\n"
    "بعد ما المستخدم جاوب على آخر سؤال، قرر هل في سؤال متابعة واحد قصير هيضيف قيمة "
    "قبل ما تنتقل للموضوع اللي بعده.\n"
    "قواعد:\n"
    "- اسأل متابعة بس لو الإجابة كانت مبهمة أو ناقصة أو فيها حاجة تستاهل توضيح "
    "(زي حالة التشطيب، ميزة مميزة، وكده).\n"
    "- سؤال المتابعة لازم يكون قصير ومحدد وسهل الإجابة.\n"
    "- ما تسألش متابعة عشان بس تسأل — الاختصار محترم.\n"
    "- ما تسألش عن مصطلحات تسويق (CPL، CTR، ROAS).\n"
    "- ما تكررش معلومة معروفة من إجابات قبل كده.\n"
    'رجّع JSON بس: {{"follow_up": true|false, "question": "<سؤال المتابعة أو فاضي>"}}\n'
    "لو follow_up = false، خلي question نص فاضي."
)

FOLLOW_UP_USER_TEMPLATE = (
    "المحادثة لحد دلوقتي (مقابلة عقارية):\n"
    "{qa_context}\n\n"
    "المستخدم لسه جاوب على موضوع '{topic}'.\n"
    'قرر ورجّع بس {{"follow_up": <bool>, "question": "<متابعة أو فاضي>"}}.'
)

# ------------------------------------------------------------------ #
# Legacy exports kept so i18n.get_question_prompts() still resolves.   #
# ------------------------------------------------------------------ #
SYSTEM = FOLLOW_UP_SYSTEM
USER_TEMPLATE = FOLLOW_UP_USER_TEMPLATE
FALLBACK_QUESTIONS = [
    "إيه اللي بيميز الكمبوند ده عن المشاريع المجاورة؟",
    "مين العميل المثالي — مستثمرين ولا ساكنين، عائلات ولا شباب؟",
    "تاريخ الاستلام أو حالة التشطيب إيه؟",
    "إيه أهم الخدمات أو المرافق اللي بتميز المشروع؟",
]
