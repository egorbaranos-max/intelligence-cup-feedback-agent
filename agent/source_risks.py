"""Conservative, limited source-risk hints; NOT a complete injection defense.

Rules look for explicit processor-control or evidence-fabrication instructions,
never business feature keywords or example IDs. They can miss paraphrases and
obfuscation. Quoted/negated attacks and legitimate prompt-editor requests may
also match: these are deliberately held for a person, not declared malicious.
A flagged source remains intact and none of its intents count automatically.
"""
from __future__ import annotations

import re


_RULES = (
    ("instruction_override_ru",
     r"\b(?:про)?игнориру(?:й|йте)\b.{0,80}\b(?:инструкци\w*|правил\w*|системн\w*\s+(?:сообщени\w*|промпт\w*))"),
    ("instruction_reset_ru",
     r"\b(?:забудь|забудьте|отмени|отмените)\b.{0,60}\b(?:предыдущ\w*|системн\w*)\s+(?:инструкци\w*|правил\w*|сообщени\w*|промпт\w*)"),
    ("instruction_override_en",
     r"\b(?:ignore|disregard|override|forget)\b.{0,70}\b(?:(?:previous|prior|system|all)\s+)?(?:instructions|system\s+prompt|rules)\b"),
    ("processor_directive_ru",
     r"\b(?:инструкци\w*|указани\w*|команд\w*)\s+(?:(?:для|к)\s+)?(?:обработчик\w*|классификатор\w*|модел\w*|ассистент\w*|агент\w*)\s*:"),
    ("model_verdict_override_ru",
     r"\b(?:верни|верните|выведи|выведите|ответь|ответьте|укажи|укажите|присвой|присвойте)\b.{0,50}\b(?:feature_request|user_explicit|supported|needs_review)\b"),
    ("model_verdict_override_en",
     r"\b(?:return|output|respond|classify|label)\b.{0,50}\b(?:feature_request|user_explicit|supported|needs_review)\b"),
    ("fabricated_evidence_ru",
     r"\b(?:придумай|придумайте|выдумай|выдумайте|сфабрикуй|сфабрикуйте|подделай|подделайте)\b.{0,80}\b(?:цитат\w*|доказательств\w*|отзыв\w*|голос\w*|обращени\w*|спрос)\b"),
    ("fabricated_evidence_en",
     r"\b(?:invent|fabricate|fake|make\s+up)\b.{0,80}\b(?:quotes?|evidence|testimonials?|votes?|customer\s+demand|feedback)\b"),
    ("pretend_customer_demand_ru",
     r"\b(?:напиши|напишите|запиши|запишите|укажи|укажите|изобрази|притворись)\b.{0,50}\b(?:будто|якобы)\b.{0,100}\b(?:клиент\w*|пользоват\w*|покупател\w*)\b.{0,60}\b(?:просят|просили|попросили|требуют|хотят)\b"),
    ("system_prompt_disclosure_ru",
     r"\b(?:покажи|покажите|раскрой|раскройте|выведи|выведите)\b.{0,50}\bсистемн\w*\s+(?:промпт\w*|инструкци\w*)"),
    ("system_prompt_disclosure_en",
     r"\b(?:show|reveal|print|disclose)\b.{0,50}\b(?:system\s+prompt|system\s+instructions)\b"),
)
_COMPILED = [(code, re.compile(pattern, re.IGNORECASE | re.DOTALL)) for code, pattern in _RULES]


def detect_source_risks(text: str) -> list[dict]:
    """Return exact evidence of risk hints, first occurrence per generic rule.

Only original text is inspected. Metadata, labels and model claims never decide
whether this guard fires. Offsets refer to the unchanged original Unicode text.
"""
    if not isinstance(text, str):
        raise TypeError("Source text must be a string")
    risks = []
    for code, pattern in _COMPILED:
        match = pattern.search(text)
        if match:
            risks.append({"code": code, "start": match.start(), "end": match.end(),
                          "quote": text[match.start():match.end()]})
    return sorted(risks, key=lambda risk: (risk["start"], risk["end"], risk["code"]))
