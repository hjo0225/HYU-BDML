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

V1 자극 셋은 두 갈래:
- **V1_HOLDOUT_STIMULI (기본):** 진짜 hold-out — 패키지 인터뷰 답변을 ground
  truth 로 쓰고 페르소나 프롬프트에서 그 답변을 제거. Park(2024) 인터뷰
  가이드 Part A·B 6개. package 에이전트(jeongoheo 6명)에 적용.
- **V1_SYNTHETIC_STIMULI (옛 30개):** LLM 으로 합성한 답변과 같은 LLM의
  재답변을 비교 — 사실상 "모델 일관성" 측정. Twin mock 30명에는 유효하지만
  package 에이전트에는 진짜 hold-out 이 아님. 호환성을 위해 보존.

기본 진입점은 v1_questions() — 환경변수 EVAL_V1_MODE 로 'holdout'(기본) /
'synthetic' / 'both' 선택. all_stimuli() 는 LLM 호출 1회로 V1+V3 모두 채점하기
위한 합집합이라 의미상 V3 자극만 포함하면 충분(V1 은 별도 generate).
"""

from __future__ import annotations

import os
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


# ── V1 진짜 hold-out 자극 (인터뷰 Part A·B 기반) ─────────────────────────
# 패키지 6명 인터뷰의 공통 Q6/Q7/Q8/Q11/Q12/Q13 답변이 ground truth.
# DEMO_INTERVIEW (frontend/src/lib/demoScenario.ts) 와 매칭되는 6개 — Part A
# 소비 인생사 3개 + Part B 자기 인식 3개. 포토부스 도메인(Part C·D)은 일반
# V1 으로는 도메인 편향 커서 제외.
#
# 평가 시 페르소나 프롬프트에서 인터뷰 섹션을 제거(rebuild_holdouts_from_interview)
# 한 상태로 동일 질문을 던지므로 "안 보고 재현" 가능.
#
# scratch_key 는 holdout_iv_<part><n> 형식 — 백필 스크립트가 채움.
V1_HOLDOUT_STIMULI: list[Question] = [
    Question(
        qid="iv_a1_regret_satisfy",
        question_ko="최근 1년 사이에 본인이 한 구매 중 가장 후회한 것과 가장 만족한 것을 각각 떠올려서, 무엇을 샀고 왜 그랬는지 4~6문장으로 설명해 주세요.",
        scratch_key="holdout_iv_a1",
    ),
    Question(
        qid="iv_a2_spend_categories",
        question_ko="본인의 소비 중 '돈 쓰기 가장 아까운 영역' 과 '돈 안 아까운 영역' 을 각각 떠올려서, 그게 왜 그렇게 갈리는지 4~6문장으로 설명해 주세요.",
        scratch_key="holdout_iv_a2",
    ),
    Question(
        qid="iv_a3_buy_priority",
        question_ko="물건이나 서비스를 살 때 '친환경 · 가격 · 품질 · 브랜드' 중 본인에게 가장 중요한 요소는 무엇이고, 그 이유는 무엇인지 4~6문장으로 답해 주세요.",
        scratch_key="holdout_iv_a3",
    ),
    Question(
        qid="iv_b1_decision_style",
        question_ko="본인이 결정을 내릴 때 어떤 스타일이라고 생각하세요? '빠르게 직감' 인지 '충분히 비교' 인지, 본인의 평소 모습을 사례와 함께 4~6문장으로 설명해 주세요.",
        scratch_key="holdout_iv_b1",
    ),
    Question(
        qid="iv_b2_influence_source",
        question_ko="본인이 무언가를 결정할 때 가장 영향을 많이 받는 사람이나 정보원은 누구·무엇이고, 왜 그 사람·매체의 영향을 받는지 4~6문장으로 답해 주세요.",
        scratch_key="holdout_iv_b2",
    ),
    Question(
        qid="iv_b3_waiting_tolerance",
        question_ko="본인은 기다림에 강한 편인가요, 약한 편인가요? 예를 들어 할인 기다리기·배송 기다리기 같은 상황에서 본인이 보이는 패턴을 4~6문장으로 설명해 주세요.",
        scratch_key="holdout_iv_b3",
    ),
]

# 패키지 인터뷰 Q번호 ↔ V1 자극 매핑 — rebuild_holdouts_from_interview 가 사용.
# 6명 모두 같은 Q5~Q29 답변을 가짐 (Park 2024 Expert Reflection 인터뷰 가이드).
HOLDOUT_INTERVIEW_MAPPING: dict[str, str] = {
    "holdout_iv_a1": "6",   # 후회/만족 구매
    "holdout_iv_a2": "7",   # 돈 아까운/안 아까운 영역
    "holdout_iv_a3": "8",   # 친환경·가격·품질·브랜드
    "holdout_iv_b1": "11",  # 결정 스타일
    "holdout_iv_b2": "12",  # 영향 받는 사람·정보원
    "holdout_iv_b3": "13",  # 기다림 강한/약한
}


# ── V1 합성 자극 (구버전 30개 · 호환용) ───────────────────────────────────
# Slice 2.6 PoC → V1 자극 30개 확장 시도에서 만든 합성 풀.
# scratch.holdout_* 에 LLM 생성 답변을 저장하므로 진짜 hold-out 이 아님.
# Twin mock 30명에는 archetype 일관성 측정용으로 의미 있지만, package 6명에는
# 인터뷰 답변(V1_HOLDOUT_STIMULI) 을 쓰는 게 정확.
V1_SYNTHETIC_STIMULI: list[Question] = [
    # 기존 3개 (Slice 2.6 PoC) — qid·scratch_key 변경 금지(이미 시드된 데이터)
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

    # L1 경제 — 가격 민감도·예산·저축·할인·프리미엄 (5)
    Question(
        qid="l1_price_pain",
        question_ko="지난 한 달 동안 '이건 좀 비싸다'고 느낀 구매가 있었나요? 어떤 상황이었고 결국 어떻게 결정했는지 4~6문장으로.",
        scratch_key="holdout_l1_price_pain",
    ),
    Question(
        qid="l1_budget_top",
        question_ko="본인의 한 달 지출 중 가장 큰 비중을 차지하는 항목 두 가지와, 그게 그 위치에 있는 이유를 4~6문장으로 설명해 주세요.",
        scratch_key="holdout_l1_budget_top",
    ),
    Question(
        qid="l1_saving_rule",
        question_ko="저축이나 자산 관리에 대해 평소 어떤 원칙을 가지고 있는지, 그 원칙이 어떤 경험에서 비롯됐는지 4~6문장으로.",
        scratch_key="holdout_l1_saving_rule",
    ),
    Question(
        qid="l1_discount_react",
        question_ko="할인이나 프로모션을 봤을 때 본인이 보이는 전형적인 반응은 어떤가요? 자제하는지 자주 흔들리는지 구체적인 예와 함께 4~6문장.",
        scratch_key="holdout_l1_discount_react",
    ),
    Question(
        qid="l1_premium_zone",
        question_ko="본인이 '돈을 더 내고서라도 이건 사고 싶다'고 생각하는 종류의 물건이나 서비스가 있나요? 그 이유까지 4~6문장.",
        scratch_key="holdout_l1_premium_zone",
    ),

    # L2 의사결정 — 속도·정보수집·후회·비교·리스크 (5)
    Question(
        qid="l2_decision_speed",
        question_ko="큰 구매 결정을 내릴 때 본인은 빨리 결정하는 편인가요, 오래 고민하는 편인가요? 최근 사례 하나를 들어 4~6문장으로.",
        scratch_key="holdout_l2_decision_speed",
    ),
    Question(
        qid="l2_info_threshold",
        question_ko="새 제품을 살 때 어디까지 정보를 모으고 결정하는지 — 본인의 '충분히 알아봤다'라는 기준을 4~6문장으로.",
        scratch_key="holdout_l2_info_threshold",
    ),
    Question(
        qid="l2_regret_handle",
        question_ko="구매 후 후회한 경험이 있다면 어떻게 다뤘는지(반품·그냥 씀·다음에 반영) 4~6문장.",
        scratch_key="holdout_l2_regret_handle",
    ),
    Question(
        qid="l2_compare_axis",
        question_ko="두 가지 옵션 중 하나를 골라야 할 때 주로 쓰는 비교 기준은 무엇이고, 그게 본인에게 중요한 이유 4~6문장.",
        scratch_key="holdout_l2_compare_axis",
    ),
    Question(
        qid="l2_new_brand_try",
        question_ko="검증되지 않은 새 브랜드나 제품을 시도해보는 데 본인은 적극적인 편인가요, 신중한 편인가요? 구체 사례 4~6문장.",
        scratch_key="holdout_l2_new_brand_try",
    ),

    # L3 신뢰 — 리뷰·추천·광고·브랜드·전문가 (5)
    Question(
        qid="l3_review_trust",
        question_ko="온라인 리뷰를 보면 어떤 리뷰가 본인에게 가장 신뢰가 가나요? 무엇 때문에 그렇게 느끼는지 4~6문장.",
        scratch_key="holdout_l3_review_trust",
    ),
    Question(
        qid="l3_recommender",
        question_ko="주변 사람의 추천을 얼마나 신뢰하는 편이고, 그 사람이 어떤 사람일 때 더 신뢰가 가는지 4~6문장.",
        scratch_key="holdout_l3_recommender",
    ),
    Question(
        qid="l3_ad_effect",
        question_ko="광고를 보고 실제로 무언가를 구매한 적이 최근에 있었나요? 어떤 종류의 광고가 본인에게 효과가 있는지 4~6문장.",
        scratch_key="holdout_l3_ad_effect",
    ),
    Question(
        qid="l3_brand_loyalty",
        question_ko="본인이 오래 쓰고 있는 브랜드가 있다면 어떤 것이고, 계속 쓰는 이유가 무엇인지 4~6문장.",
        scratch_key="holdout_l3_brand_loyalty",
    ),
    Question(
        qid="l3_expert_opinion",
        question_ko="전문가나 인플루언서의 의견을 본인은 얼마나 참고하는지, 어떤 분야에서 더 의지하는지 4~6문장.",
        scratch_key="holdout_l3_expert_opinion",
    ),

    # L4 사회 — 그룹·선물·시선·관계·갈등 (5)
    Question(
        qid="l4_group_role",
        question_ko="친구나 가족과 함께 무언가를 결정해야 할 때 본인은 어떤 역할을 주로 맡는지(주도·조율·따름) 사례와 함께 4~6문장.",
        scratch_key="holdout_l4_group_role",
    ),
    Question(
        qid="l4_gift_choice",
        question_ko="선물을 고를 때 본인은 무엇을 가장 중요하게 생각하나요? 최근 선물 사례와 함께 4~6문장.",
        scratch_key="holdout_l4_gift_choice",
    ),
    Question(
        qid="l4_social_image",
        question_ko="본인의 소비가 다른 사람의 시선에 얼마나 영향을 받는지 솔직하게 4~6문장으로 답해 주세요.",
        scratch_key="holdout_l4_social_image",
    ),
    Question(
        qid="l4_shared_activity",
        question_ko="친구·가족과 함께 시간을 보낼 때 본인이 즐기는 활동 한 가지와 그게 본인에게 어떤 의미인지 4~6문장.",
        scratch_key="holdout_l4_shared_activity",
    ),
    Question(
        qid="l4_conflict_resolve",
        question_ko="주변 사람과 소비 가치관이 부딪힐 때(예: 같이 사는 사람과 지출 우선순위가 다를 때) 본인은 어떻게 풀어가는지 4~6문장.",
        scratch_key="holdout_l4_conflict_resolve",
    ),

    # L5 정체성 — 변화·자부심·길티플레저·이상 (4)
    Question(
        qid="l5_self_change",
        question_ko="최근 1~2년 사이에 본인의 가치관이나 라이프스타일에서 달라진 점이 있다면 무엇이고, 왜 변했는지 4~6문장.",
        scratch_key="holdout_l5_self_change",
    ),
    Question(
        qid="l5_proud_choice",
        question_ko="본인의 소비 선택 중 '잘 했다'고 가장 뿌듯하게 느낀 결정 하나를 사례와 함께 4~6문장.",
        scratch_key="holdout_l5_proud_choice",
    ),
    Question(
        qid="l5_guilty_pleasure",
        question_ko="남들에게 자랑하긴 어렵지만 본인이 즐기는 작은 소비가 있다면 무엇이고 왜 좋아하는지 4~6문장.",
        scratch_key="holdout_l5_guilty_pleasure",
    ),
    Question(
        qid="l5_ideal_5yr",
        question_ko="5년 뒤 본인의 모습을 한 장면으로 그린다면 어떤 모습이고, 거기 도달하기 위해 지금 하고 있는 일이 무엇인지 4~6문장.",
        scratch_key="holdout_l5_ideal_5yr",
    ),

    # L6 시간 — 현재 vs 미래·기다림·계획 단위 (3)
    Question(
        qid="l6_now_vs_future",
        question_ko="본인은 '지금의 만족'과 '미래의 안정' 중 어느 쪽에 더 비중을 두는지, 그게 본인의 소비에 어떻게 드러나는지 4~6문장.",
        scratch_key="holdout_l6_now_vs_future",
    ),
    Question(
        qid="l6_wait_pattern",
        question_ko="할인을 기다려서 사는 편인지, 필요할 때 바로 사는 편인지, 본인의 패턴과 그 이유 4~6문장.",
        scratch_key="holdout_l6_wait_pattern",
    ),
    Question(
        qid="l6_planning_unit",
        question_ko="한 달 / 6개월 / 1년 중 본인이 가장 자연스럽게 계획을 세우는 단위는 무엇이고, 왜 그 단위가 본인에게 맞는지 4~6문장.",
        scratch_key="holdout_l6_planning_unit",
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
    """V1 평가용 자극.

    EVAL_V1_MODE 환경변수로 셋 선택 (기본 'holdout'):
    - 'holdout'   : V1_HOLDOUT_STIMULI 만 — 진짜 hold-out (인터뷰 답변 ground truth).
                    package 에이전트(jeongoheo 6명)용 권장.
    - 'synthetic' : V1_SYNTHETIC_STIMULI 만 — LLM 합성 답변. Twin mock 30 호환용.
    - 'both'      : 두 셋 합집합 — 마이그레이션 기간 비교용.
    """
    mode = os.getenv("EVAL_V1_MODE", "holdout").lower()
    if mode == "synthetic":
        return list(V1_SYNTHETIC_STIMULI)
    if mode == "both":
        return [*V1_HOLDOUT_STIMULI, *V1_SYNTHETIC_STIMULI]
    return list(V1_HOLDOUT_STIMULI)


def v3_questions() -> list[Question]:
    """V3 평가용 — V1 hold-out + V3 anchor 자극 모두 사용.

    V3 는 답변 임베딩 평균으로 페르소나 벡터를 만들기 때문에 자극이 많을수록
    노이즈에 강하다. V1 hold-out 답변도 페르소나 차이를 드러내므로 함께 활용.
    EVAL_V1_MODE 와 무관하게 V1 hold-out 6개 + V3 anchor 3개 = 9개 사용.
    """
    return [*V1_HOLDOUT_STIMULI, *V3_DIVERSITY_STIMULI]


def all_stimuli() -> list[Question]:
    """LLM 호출 1회로 두 지표를 모두 채점하기 위한 합집합 자극."""
    return v3_questions()
