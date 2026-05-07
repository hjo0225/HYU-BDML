"""6-Lens 척도 정의 — docs/6-LENS_MAPPING.md 의 코드화 버전.

ScaleDefinition 은 이 모듈의 단일 진실 공급원.
매핑이 바뀌면 docs/6-LENS_MAPPING.md 와 동기화 필수.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ScaleGroup = Literal["L1", "L2", "L3", "L4", "L5", "L6", "C", "Q"]
ScoringMethod = Literal["mpl_ce", "mpl_lambda", "proportion_match", "sum", "mean", "count_correct", "qualitative", "categorical", "regression_fc", "raw"]


@dataclass(frozen=True)
class ScaleDefinition:
    """하나의 척도(scale)를 코드로 표현."""
    scale_id: str                     # 예: "L1-1"
    group: ScaleGroup                 # 속하는 렌즈 그룹
    name_ko: str                      # 한국어 명칭
    item_count: int                   # 문항 수
    scoring_method: ScoringMethod     # 채점 방식
    persona_keys: list[str]           # persona_params 에 저장될 키 목록
    input_keys: list[str]             # 입력 JSON 최상위 키 목록 (패턴만, 실제 키는 parser 에서)
    reverse_items: list[int] = field(default_factory=list)  # 역채점 문항 번호
    notes: str = ""


# ── 28 척도 전체 정의 ─────────────────────────────────────────────────────

LENS_DEFINITIONS: dict[str, ScaleDefinition] = {sd.scale_id: sd for sd in [
    # ── L1 경제적 합리성 ──────────────────────────────────────────────────
    ScaleDefinition(
        scale_id="L1-1", group="L1", name_ko="위험 회피 (Risk Aversion)",
        item_count=3, scoring_method="mpl_ce",
        persona_keys=["l1.risk_aversion", "l1.ce_q1", "l1.ce_q2", "l1.ce_q3"],
        input_keys=["L1-1.Q1.row_first_certain", "L1-1.Q2.row_first_certain", "L1-1.Q3.row_first_certain"],
        notes="MPL CE 추출. EV: Q1=3000, Q2=5000, Q3=5000. risk_aversion = mean((EV-CE)/EV).",
    ),
    ScaleDefinition(
        scale_id="L1-2", group="L1", name_ko="손실 회피 (Loss Aversion)",
        item_count=4, scoring_method="mpl_lambda",
        persona_keys=["l1.loss_aversion_lambda"],
        input_keys=["L1-2.Q1.row_first_certain", "L1-2.Q2.row_first_certain",
                    "L1-2.Q3.row_first_certain", "L1-2.Q4.row_first_positive"],
        notes="Q4 혼합 복권: lambda = x_gain / 8000.",
    ),
    ScaleDefinition(
        scale_id="L1-3", group="L1", name_ko="심적 회계 (Mental Accounting)",
        item_count=4, scoring_method="proportion_match",
        persona_keys=["l1.mental_accounting"],
        input_keys=["L1-3.Q1", "L1-3.Q2", "L1-3.Q3", "L1-3.Q4"],
        notes="예측 답 Q1=A, Q2=A, Q3=B, Q4=B. 일치 비율.",
    ),
    ScaleDefinition(
        scale_id="L1-4", group="L1", name_ko="구두쇠-낭비벽 (Tightwad-Spendthrift)",
        item_count=4, scoring_method="sum",
        persona_keys=["l1.tightwad_spendthrift"],
        input_keys=["L1-4.Q1", "L1-4.Q2a", "L1-4.Q2b", "L1-4.Q3"],
        reverse_items=[3, 4],  # Q2b(인덱스2), Q3(인덱스3)
        notes="합산 4~26. Q2b·Q3 역채점(역채점 최대값: Q2b=5, Q3=5).",
    ),
    ScaleDefinition(
        scale_id="L1-5", group="L1", name_ko="프레이밍 문제 (Framing)",
        item_count=1, scoring_method="raw",
        persona_keys=["l1.framing_condition", "l1.framing_response"],
        input_keys=["L1-5.Q1.condition", "L1-5.Q1.response"],
    ),
    ScaleDefinition(
        scale_id="L1-6", group="L1", name_ko="절대 vs 상대 절약 (Savings)",
        item_count=1, scoring_method="raw",
        persona_keys=["l1.savings_condition", "l1.savings_response"],
        input_keys=["L1-6.Q1.condition", "L1-6.Q1.response"],
    ),

    # ── L2 의사결정 스타일 ────────────────────────────────────────────────
    ScaleDefinition(
        scale_id="L2-1", group="L2", name_ko="극대화 척도 (Maximization Scale)",
        item_count=6, scoring_method="mean",
        persona_keys=["l2.maximization"],
        input_keys=[f"L2-1.Q{i}" for i in range(1, 7)],
    ),
    ScaleDefinition(
        scale_id="L2-2", group="L2", name_ko="인지적 종결 욕구 (Need for Closure)",
        item_count=15, scoring_method="mean",
        persona_keys=["l2.need_for_closure"],
        input_keys=[f"L2-2.Q{i}" for i in range(1, 16)],
    ),
    ScaleDefinition(
        scale_id="L2-3", group="L2", name_ko="인지 욕구 (Need for Cognition)",
        item_count=18, scoring_method="mean",
        persona_keys=["l2.need_for_cognition"],
        input_keys=[f"L2-3.Q{i}" for i in range(1, 19)],
        reverse_items=[3, 4, 5, 7, 8, 9, 12, 16, 17],
        notes="5점 척도. 역채점: Q3,4,5,7,8,9,12,16,17.",
    ),
    ScaleDefinition(
        scale_id="L2-4", group="L2", name_ko="인지 반사 검사 (CRT)",
        item_count=4, scoring_method="count_correct",
        persona_keys=["l2.crt_score"],
        input_keys=["L2-4.Q1", "L2-4.Q2", "L2-4.Q3", "L2-4.Q4"],
        notes="정답: Q1=수아, Q2=0, Q3=2, Q4=8.",
    ),

    # ── L3 동기 구조 ──────────────────────────────────────────────────────
    ScaleDefinition(
        scale_id="L3-1", group="L3", name_ko="조절초점 척도 (Regulatory Focus)",
        item_count=10, scoring_method="mean",
        persona_keys=["l3.regulatory_focus"],
        input_keys=[f"L3-1.Q{i}" for i in range(1, 11)],
        notes="7점 척도.",
    ),
    ScaleDefinition(
        scale_id="L3-2", group="L3", name_ko="자기지향/타인지향 가치 (Agentic vs Communal)",
        item_count=24, scoring_method="mean",
        persona_keys=["l3.agency", "l3.communion"],
        input_keys=[f"L3-2.V{i}" for i in range(1, 25)],
        notes="Agency: V1,2,4,6,8,10,13,15,18,20,22,24 평균. Communion: V3,5,7,9,11,12,14,16,17,19,21,23 평균. L5와 공유.",
    ),
    ScaleDefinition(
        scale_id="L3-3", group="L3", name_ko="독특성 욕구 (Need for Uniqueness)",
        item_count=12, scoring_method="mean",
        persona_keys=["l3.need_for_uniqueness"],
        input_keys=[f"L3-3.Q{i}" for i in range(1, 13)],
    ),
    ScaleDefinition(
        scale_id="L3-4", group="L3", name_ko="자기 차이 질문 (Selves Questionnaire)",
        item_count=3, scoring_method="qualitative",
        persona_keys=[],  # qualitative.* 에 저장
        input_keys=["L3-4.Q1", "L3-4.Q2", "L3-4.Q3"],
        notes="Q1=self_aspire, Q2=self_ought, Q3=self_actual.",
    ),

    # ── L4 사회적 영향 ────────────────────────────────────────────────────
    ScaleDefinition(
        scale_id="L4-1", group="L4", name_ko="자기 감시 (Self-Monitoring)",
        item_count=13, scoring_method="mean",
        persona_keys=["l4.self_monitoring"],
        input_keys=[f"L4-1.Q{i}" for i in range(1, 14)],
        reverse_items=[4, 6],
        notes="6점 척도(0~5). 역채점 Q4·Q6.",
    ),
    ScaleDefinition(
        scale_id="L4-2", group="L4", name_ko="개인주의 vs 집단주의",
        item_count=16, scoring_method="mean",
        persona_keys=["l4.horizontal_individualism", "l4.vertical_individualism",
                      "l4.horizontal_collectivism", "l4.vertical_collectivism"],
        input_keys=[f"L4-2.Q{i}" for i in range(1, 17)],
        notes="수평개인Q1-4, 수직개인Q5-8, 수평집단Q9-12, 수직집단Q13-16.",
    ),
    ScaleDefinition(
        scale_id="L4-3", group="L4", name_ko="사회적 바람직성 (Social Desirability)",
        item_count=13, scoring_method="count_correct",
        persona_keys=["l4.social_desirability"],
        input_keys=[f"L4-3.Q{i}" for i in range(1, 14)],
        notes="TRUE on Q5,7,9,10,13 + FALSE on Q1,2,3,4,6,8,11,12. 합산 0~13.",
    ),
    ScaleDefinition(
        scale_id="L4-4", group="L4", name_ko="공감 (Empathy — BES-A)",
        item_count=20, scoring_method="mean",
        persona_keys=["l4.empathy"],
        input_keys=[f"L4-4.Q{i}" for i in range(1, 21)],
        reverse_items=[1, 6, 7, 8, 13, 18, 19, 20],
        notes="5점 척도. 역채점 Q1,6,7,8,13,18,19,20.",
    ),
    ScaleDefinition(
        scale_id="L4-5", group="L4", name_ko="잘못된 합의 (False Consensus)",
        item_count=20, scoring_method="regression_fc",
        persona_keys=["l4.false_consensus_effect", "l4.policy_stance_avg"],
        input_keys=[f"L4-5.P1.Q{i}" for i in range(1, 11)] +
                   [f"L4-5.P2.Q{i}" for i in range(1, 11)],
        notes="P1: 자기입장 1~5. P2: 예측지지율 0~100. FC = 자기입장 영향 추정.",
    ),
    ScaleDefinition(
        scale_id="L4-6", group="L4", name_ko="독재자 게임 (Dictator Game)",
        item_count=1, scoring_method="raw",
        persona_keys=["l4.dictator_send", "l4.dictator_send_ratio"],
        input_keys=["L4-6.Q1"],
        notes="선택지: 0/1000/2000/4000/5000원. Thought Listing → qualitative.",
    ),

    # ── L5 가치 사슬 ──────────────────────────────────────────────────────
    ScaleDefinition(
        scale_id="L5-1", group="L5", name_ko="소비자 미니멀리즘 (Consumer Minimalism)",
        item_count=12, scoring_method="mean",
        persona_keys=["l5.minimalism"],
        input_keys=[f"L5-1.Q{i}" for i in range(1, 13)],
    ),
    ScaleDefinition(
        scale_id="L5-2", group="L5", name_ko="친환경 가치 (Green Values)",
        item_count=6, scoring_method="mean",
        persona_keys=["l5.green_values"],
        input_keys=[f"L5-2.Q{i}" for i in range(1, 7)],
    ),

    # ── L6 시간 지향 ──────────────────────────────────────────────────────
    ScaleDefinition(
        scale_id="L6-1", group="L6", name_ko="할인율 (Discount Rate)",
        item_count=3, scoring_method="mpl_ce",
        persona_keys=["l6.discount_rate_annual"],
        input_keys=["L6-1.Q1.row_first_certain", "L6-1.Q2.row_first_certain", "L6-1.Q3.row_first_certain"],
        notes="연환산: Q1·Q2=(Y/x)^52−1, Q3=(Y/x)^26−1. Y: Q1=6000, Q2=8000, Q3=10000.",
    ),
    ScaleDefinition(
        scale_id="L6-2", group="L6", name_ko="현재 편향 (Present Bias)",
        item_count=3, scoring_method="mpl_ce",
        persona_keys=["l6.present_bias_beta"],
        input_keys=["L6-2.Q1.row_first_certain", "L6-2.Q2.row_first_certain", "L6-2.Q3.row_first_certain"],
        notes="beta = mean((x_pb - x_dr) / Y). L6-1과 쌍으로 계산.",
    ),
    ScaleDefinition(
        scale_id="L6-3", group="L6", name_ko="성실성 (Conscientiousness)",
        item_count=8, scoring_method="count_correct",
        persona_keys=["l6.conscientiousness"],
        input_keys=[f"L6-3.Q{i}" for i in range(1, 9)],
        reverse_items=[5, 6, 7, 8],
        notes="9점 척도. 1~4: 응답>5인 수. 5~8(역채점): 응답<5인 수. 합 0~8.",
    ),

    # ── 통제 변수 ─────────────────────────────────────────────────────────
    ScaleDefinition(
        scale_id="C-1", group="C", name_ko="인구통계 (Demographics)",
        item_count=14, scoring_method="categorical",
        persona_keys=[],  # demographics.* 에 저장
        input_keys=[f"C-1.Q{i}" for i in range(1, 15)],
    ),
    ScaleDefinition(
        scale_id="C-2", group="C", name_ko="금융 이해력 (Financial Literacy)",
        item_count=8, scoring_method="count_correct",
        persona_keys=["ability.financial_literacy"],
        input_keys=[f"C-2.Q{i}" for i in range(1, 9)],
        notes="정답: Q1=TRUE,Q2=3,Q3=2,Q4=TRUE,Q5=2,Q6=2,Q7=TRUE,Q8=영원히.",
    ),
    ScaleDefinition(
        scale_id="C-3", group="C", name_ko="수리 능력 (Numeracy)",
        item_count=8, scoring_method="count_correct",
        persona_keys=["ability.numeracy"],
        input_keys=[f"C-3.Q{i}" for i in range(1, 9)],
        notes="정답: Q1=500,Q2=10,Q3=20,Q4=0.1,Q5=100,Q6=5,Q7=500,Q8=47.",
    ),
]}

# 그룹별 ID 목록
LENS_GROUPS: dict[str, list[str]] = {}
for _sd in LENS_DEFINITIONS.values():
    LENS_GROUPS.setdefault(_sd.group, []).append(_sd.scale_id)
