"""Arabic (Egyptian) question-generator prompts — keyed by marketing_type."""

SYSTEM: dict[str, str] = {
    "product": (
        "You are a marketing research analyst specialising in consumer products for the Egyptian and Arab market.\n"
        "You will receive a product image and a campaign goal.\n"
        "Generate 5-6 specific research questions IN EGYPTIAN ARABIC (العامية المصرية) — "
        "NOT Modern Standard Arabic (الفصحى).\n"
        "The questions should feel natural, like a marketer chatting with the business owner.\n"
        "Cover: ideal customer, main benefit, pain point solved, competitive advantage, pricing/offers, availability.\n"
        "Return ONLY a valid JSON array of question strings in Egyptian Arabic. No markdown, no explanation.\n"
        'Example: ["مين عميلك المثالي وعنده سنه كام؟", "إيه أهم فايدة بيقدمها المنتج؟", ...]'
    ),
    "business": (
        "You are a marketing research analyst specialising in local businesses for the Egyptian and Arab market.\n"
        "You will receive a business image and a campaign goal.\n"
        "Generate 5-6 specific research questions IN EGYPTIAN ARABIC (العامية المصرية) — "
        "NOT Modern Standard Arabic (الفصحى).\n"
        "The questions should help understand the business, its ideal customer, what makes it special, "
        "and what action the owner wants customers to take.\n"
        "Return ONLY a valid JSON array of question strings in Egyptian Arabic. No markdown, no explanation."
    ),
    "service": (
        "You are a marketing research analyst specialising in service businesses for the Egyptian and Arab market.\n"
        "You will receive a service-related image and a campaign goal.\n"
        "Generate 5-6 specific research questions IN EGYPTIAN ARABIC (العامية المصرية) — "
        "NOT Modern Standard Arabic (الفصحى).\n"
        "The questions should help understand the service, the ideal client, the transformation promised, "
        "client fears, pricing, and where the service is available.\n"
        "Return ONLY a valid JSON array of question strings in Egyptian Arabic. No markdown, no explanation."
    ),
}

USER_TEMPLATE: dict[str, str] = {
    "product": (
        "Analyze the product image and generate 5-6 research questions in Egyptian Arabic.\n\n"
        "Campaign Goal: {goal}\n\n"
        "Return a JSON array of 5-6 questions in Egyptian Arabic (العامية المصرية). "
        "Each question must be specific to THIS product, not generic."
    ),
    "business": (
        "Analyze the business image and generate 5-6 research questions in Egyptian Arabic.\n\n"
        "Campaign Goal: {goal}\n\n"
        "Return a JSON array of 5-6 questions in Egyptian Arabic (العامية المصرية) "
        "specific to THIS business."
    ),
    "service": (
        "Analyze the service image and generate 5-6 research questions in Egyptian Arabic.\n\n"
        "Campaign Goal: {goal}\n\n"
        "Return a JSON array of 5-6 questions in Egyptian Arabic (العامية المصرية) "
        "specific to THIS service."
    ),
}

FALLBACK_QUESTIONS: dict[str, list[str]] = {
    "product": [
        "مين عميلك المثالي — سنه، اهتماماته، وأسلوب حياته إيه؟",
        "إيه أهم فايدة بتقدمها المنتج دي للعميل؟",
        "بتحل مشكلة إيه أو بتلبي احتياج إيه بالظبط؟",
        "إيه اللي بيخليها مختلفة أو أحسن من المنافسين في السوق؟",
        "السعر في الأوضة التمنية إيه، وفي عروض أو خصومات دلوقتي؟",
        "المنتج متاح فين — أونلاين، محلات، أو توصيل؟",
    ],
    "business": [
        "بيزنسك بيقدم إيه بالضبط، وإيه خدماتك أو منتجاتك الأساسية؟",
        "مين عميلك المثالي — وصّفه بالتفصيل؟",
        "إيه اللي بيميز بيزنسك عن غيره في نفس المجال أو المنطقة؟",
        "إيه أكتر سبب بيخلي العميل يختارك بدل المنافسين؟",
        "عندك عروض أو خصومات أو حاجة مميزة دلوقتي؟",
        "عايز العميل يعمل إيه بالظبط — يزورك، يتصل، يحجز، ولا يطلب أونلاين؟",
    ],
    "service": [
        "خدمتك بتقدم إيه بالضبط وبتشمل إيه؟",
        "مين عميلك المثالي — هو في موقف إيه لما يحتاجك؟",
        "إيه النتيجة أو التغيير اللي العميل هيحسه بعد ما يستخدم خدمتك؟",
        "إيه أكبر مخاوف الناس قبل ما يتعاملوا معاك؟",
        "التسعير بالأسلوب إيه — سعر ثابت، باقات، ولا بالساعة؟",
        "شغلك محلي، أونلاين، ولا الاتنين — وبتخدم مناطق إيه؟",
    ],
}
