"""하이브리드 페르소나 프롬프트 빌더.

build_persona(persona_params, qualitative, demographics) → 시스템 프롬프트 str
"""
from __future__ import annotations

from .compressor import trim_to_limit
from .intro import build_intro_ko
from prompts.persona_system import (
    IDENTITY_TEMPLATE,
    NUMERICAL_GUIDE_TEMPLATE,
    QUALITATIVE_ANCHOR_TEMPLATE,
    CONSTRAINTS_TEMPLATE,
    SYSTEM_PROMPT_TEMPLATE,
)


def _safe(params: dict, key: str, default=0.0):
    return params.get(key, default)


def build_persona(
    persona_params: dict,
    qualitative: dict,
    demographics: dict,
    max_tokens: int = 8000,
) -> str:
    """하이브리드 페르소나 시스템 프롬프트를 조립한다.

    Args:
        persona_params: score_all() 의 출력 dict.
        qualitative: extract_qualitative() 의 출력 dict.
        demographics: extract_demographics() 의 출력 dict.
        max_tokens: 최대 토큰 수 (기본 8000).

    Returns:
        시스템 프롬프트 문자열 (max_tokens 이내로 자동 압축).
    """
    intro = build_intro_ko(persona_params, demographics)
    identity = IDENTITY_TEMPLATE.format(intro=intro)

    numerical = NUMERICAL_GUIDE_TEMPLATE.format(
        l1_risk_aversion=_safe(persona_params, "l1.risk_aversion"),
        l1_loss_aversion_lambda=_safe(persona_params, "l1.loss_aversion_lambda", 1.0),
        l1_mental_accounting=_safe(persona_params, "l1.mental_accounting"),
        l1_tightwad_spendthrift=_safe(persona_params, "l1.tightwad_spendthrift", 13),
        l2_maximization=_safe(persona_params, "l2.maximization", 3.0),
        l2_need_for_closure=_safe(persona_params, "l2.need_for_closure", 3.0),
        l2_need_for_cognition=_safe(persona_params, "l2.need_for_cognition", 3.0),
        l2_crt_score=int(_safe(persona_params, "l2.crt_score", 0)),
        l3_regulatory_focus=_safe(persona_params, "l3.regulatory_focus", 4.0),
        l3_agency=_safe(persona_params, "l3.agency", 5.0),
        l3_communion=_safe(persona_params, "l3.communion", 5.0),
        l3_need_for_uniqueness=_safe(persona_params, "l3.need_for_uniqueness", 3.0),
        l4_self_monitoring=_safe(persona_params, "l4.self_monitoring", 2.5),
        l4_horizontal_individualism=_safe(persona_params, "l4.horizontal_individualism", 3.0),
        l4_vertical_individualism=_safe(persona_params, "l4.vertical_individualism", 3.0),
        l4_horizontal_collectivism=_safe(persona_params, "l4.horizontal_collectivism", 3.0),
        l4_vertical_collectivism=_safe(persona_params, "l4.vertical_collectivism", 3.0),
        l4_empathy=_safe(persona_params, "l4.empathy", 3.0),
        l4_dictator_send_ratio=_safe(persona_params, "l4.dictator_send_ratio", 0.4),
        l5_minimalism=_safe(persona_params, "l5.minimalism", 3.0),
        l5_green_values=_safe(persona_params, "l5.green_values", 3.0),
        l6_discount_rate_annual=_safe(persona_params, "l6.discount_rate_annual", 0.5),
        l6_present_bias_beta=_safe(persona_params, "l6.present_bias_beta", 0.0),
        l6_conscientiousness=int(_safe(persona_params, "l6.conscientiousness", 4)),
        ability_financial_literacy=int(_safe(persona_params, "ability.financial_literacy", 4)),
        ability_numeracy=int(_safe(persona_params, "ability.numeracy", 4)),
    )

    qual_anchors = QUALITATIVE_ANCHOR_TEMPLATE.format(
        self_aspire=qualitative.get("self_aspire", ""),
        self_ought=qualitative.get("self_ought", ""),
        self_actual=qualitative.get("self_actual", ""),
    )

    constraints = CONSTRAINTS_TEMPLATE

    full_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        identity=identity,
        numerical_guides=numerical,
        qualitative_anchors=qual_anchors,
        constraints=constraints,
    )

    return trim_to_limit(full_prompt, max_tokens)
