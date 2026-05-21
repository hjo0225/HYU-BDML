"""V1·V3 평가용 자극 세트.

설계 의도:
- **V1 (응답 동기화율):** 페르소나 프롬프트에 들어가지 않은 hold-out 정성
  답변과 cosine 비교. 즉 에이전트가 *원문을 보지 못한 상태*에서 같은 질문에
  답한 결과의 의미 유사도. 진짜 "안 보고 재현" 평가.
- **V3 (페르소나 독립성):** 30명의 답변 분산을 측정하는 다양성 지표라
  anchor 자기 서술(self_aspire/ought/actual) 그대로 사용. anchor 가
  프롬프트에 있어도 다양성 측정에는 무관 — 오히려 페르소나가 잘 흡수했는지
  보는 게 핵심.

scratch_key 매핑은 seed_service 가 record.qualitative 의 평면 키 그대로
agent.scratch 에 저장하므로 일치한다.

Phase 5 에서 실데이터(Twin-2K-500 raw 234답변) 적재 시 hold-out 자극 풀을
더 늘릴 수 있다. (EVAL_SPEC.md §1, §5)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    """V1·V3 자극.

    Attributes:
        qid: 자극 식별자.
        question_ko: 사용자가 보는 한국어 질문.
        scratch_key: agent.scratch[scratch_key] 가 V1 원문 비교 대상.
                     None 이면 V1 에서 제외하고 V3 전용.
    """
    qid: str
    question_ko: str
    scratch_key: str | None


# ── V1 hold-out 자극 ─────────────────────────────────────────────────────
# 페르소나 프롬프트에 들어가지 않는 정성 답변. agent.scratch.holdout_* 와
# 매핑되며 mock 생성기 / 실데이터 적재기가 모두 채워준다.
V1_HOLDOUT_STIMULI: list[Question] = [
    Question(
        qid="recent_purchase",
        question_ko=(
            "최근 6개월 안에 본인이 한 가장 큰 소비 한 건을 떠올려서, 무엇을 샀고 "
            "왜 그렇게 결정했는지 4~6문장으로 설명해 주세요."
        ),
        scratch_key="holdout_recent_purchase",
    ),
    Question(
        qid="info_source",
        question_ko=(
            "물건이나 서비스를 결정할 때 가장 신뢰하는 정보 출처는 무엇인가요? "
            "그렇게 신뢰하게 된 이유까지 4~6문장으로 답해 주세요."
        ),
        scratch_key="holdout_info_source",
    ),
    Question(
        qid="lifestyle",
        question_ko=(
            "본인의 라이프스타일을 한 단어로 표현한다면 무엇이고, 그 단어가 왜 "
            "본인을 잘 설명하는지 4~6문장으로 풀어주세요."
        ),
        scratch_key="holdout_lifestyle",
    ),
]


# ── V3 다양성 자극 ───────────────────────────────────────────────────────
# anchor 자기 서술. 모든 에이전트가 같은 질문에 답해 답변 임베딩의 분산을
# 본다. scratch_key=None 으로 두어 V1 채점에서 제외.
V3_DIVERSITY_STIMULI: list[Question] = [
    Question(
        qid="self_aspire",
        question_ko="당신의 이상적인 삶에 대해 5문장 안팎으로 설명해 주세요. 어떤 사람이 되고 싶고, 어떤 환경에서 살고 싶나요?",
        scratch_key=None,
    ),
    Question(
        qid="self_ought",
        question_ko="당신이 사회·가족·자신에게 해야 한다고 느끼는 의무는 무엇인가요? 5문장 안팎으로 답해 주세요.",
        scratch_key=None,
    ),
    Question(
        qid="self_actual",
        question_ko="실제로 본인의 평소 성격·소비 습관·의사결정 방식을 5문장 안팎으로 묘사해 주세요.",
        scratch_key=None,
    ),
]


def v1_questions() -> list[Question]:
    """V1 평가용 — hold-out 자극만 (scratch_key 가 있는 항목)."""
    return list(V1_HOLDOUT_STIMULI)


def v3_questions() -> list[Question]:
    """V3 평가용 — V1 hold-out + V3 anchor 자극 모두 사용.

    V3 는 답변 임베딩 평균으로 페르소나 벡터를 만들기 때문에 자극이 많을수록
    노이즈에 강하다. V1 hold-out 답변도 페르소나 차이를 드러내므로 함께 활용.
    """
    return [*V1_HOLDOUT_STIMULI, *V3_DIVERSITY_STIMULI]


def all_stimuli() -> list[Question]:
    """LLM 호출 1회로 두 지표를 모두 채점하기 위한 합집합 자극."""
    return v3_questions()
