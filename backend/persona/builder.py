"""페르소나 프롬프트 빌더.

build_persona(persona_params, qualitative, demographics, responses) → 시스템 프롬프트 str

[NUMERICAL GUIDES] 수치 표 대신 [BEHAVIORAL DATA] Q&A 시나리오 (27 척도 단위)
를 주입한다. 수치는 persona_params 컬럼에 그대로 보존되어 UI 에서 노출됨.
"""
from __future__ import annotations

from .compressor import trim_to_limit
from .intro import build_intro_ko
from .qa_textualizer import build_behavioral_data
from prompts.persona_system import (
    IDENTITY_TEMPLATE,
    QUALITATIVE_ANCHOR_TEMPLATE,
    CONSTRAINTS_TEMPLATE,
    SYSTEM_PROMPT_TEMPLATE,
)


def build_persona(
    persona_params: dict,
    qualitative: dict,
    demographics: dict,
    responses: dict | None = None,
    max_tokens: int = 12000,
) -> str:
    """페르소나 시스템 프롬프트 조립.

    Args:
        persona_params: score_all() 의 출력 dict (수치 점수 — UI 표시용).
        qualitative: extract_qualitative() 출력 — anchor 3종 + V1 hold-out.
        demographics: extract_demographics() 출력 — 인구통계 dict.
        responses: validate_input() 출력 — 234문항 raw 응답. 없으면 BEHAVIORAL
                   DATA 섹션이 비어 있음 (구버전 호환).
        max_tokens: 최대 토큰 수 (기본 12000 — BEHAVIORAL DATA 포함 여유 확보).

    Returns:
        시스템 프롬프트 문자열 (max_tokens 이내로 자동 압축).
    """
    intro = build_intro_ko(persona_params, demographics)
    identity = IDENTITY_TEMPLATE.format(intro=intro)

    behavioral_data = build_behavioral_data(responses or {}, persona_params or {})

    qual_anchors = QUALITATIVE_ANCHOR_TEMPLATE.format(
        self_aspire=qualitative.get("self_aspire", ""),
        self_ought=qualitative.get("self_ought", ""),
        self_actual=qualitative.get("self_actual", ""),
    )

    constraints = CONSTRAINTS_TEMPLATE

    full_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        identity=identity,
        behavioral_data=behavioral_data,
        qualitative_anchors=qual_anchors,
        constraints=constraints,
    )

    return trim_to_limit(full_prompt, max_tokens)
