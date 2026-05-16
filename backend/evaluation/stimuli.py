"""V1·V3 평가용 자극 세트 (Slice 2 초기 버전).

설계 의도:
- V1 은 "agent 답변 vs 원문 답변" 코사인 → 원문이 명확한 정성 응답을 선택.
  agent.scratch 의 self_aspire/self_ought/self_actual 가 mock·실데이터 모두
  보유하므로 V1 자극으로 활용.
- V3 은 페르소나 간 다양성 → 같은 정성 질문을 모든 agent 가 답해서
  답변 임베딩 분포의 페어와이즈 거리를 본다. V1 과 자극을 공유해
  LLM 호출 비용을 절반으로 절감.

Phase 5 에서 자극 세트 확장 시 본 모듈을 stimuli/cf_set_v1.json 등
외부 JSON 으로 분리한다(EVAL_SPEC.md §5).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    """V1·V3 공유 자극.

    Attributes:
        qid: 자극 식별자.
        question_ko: 사용자가 보는 한국어 질문.
        scratch_key: agent.scratch[scratch_key] 가 V1 원문 비교 대상.
                     None 이면 V1 에서 제외하고 V3 전용.
    """
    qid: str
    question_ko: str
    scratch_key: str | None


# V1·V3 공유 자극 — agent.scratch 가 보유한 정성 키와 매핑
SHARED_STIMULI: list[Question] = [
    Question(
        qid="self_aspire",
        question_ko="당신의 이상적인 삶에 대해 5문장 안팎으로 설명해 주세요. 어떤 사람이 되고 싶고, 어떤 환경에서 살고 싶나요?",
        scratch_key="self_aspire",
    ),
    Question(
        qid="self_ought",
        question_ko="당신이 사회·가족·자신에게 해야 한다고 느끼는 의무는 무엇인가요? 5문장 안팎으로 답해 주세요.",
        scratch_key="self_ought",
    ),
    Question(
        qid="self_actual",
        question_ko="실제로 본인의 평소 성격·소비 습관·의사결정 방식을 5문장 안팎으로 묘사해 주세요.",
        scratch_key="self_actual",
    ),
]


def v1_questions() -> list[Question]:
    """V1 평가용 — scratch_key 가 있는 자극만."""
    return [q for q in SHARED_STIMULI if q.scratch_key]


def v3_questions() -> list[Question]:
    """V3 평가용 — 모든 정성 자극."""
    return list(SHARED_STIMULI)
