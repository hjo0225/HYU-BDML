"""234문항 raw 응답 → 사람이 읽을 수 있는 시나리오 Q&A 텍스트 변환기.

설계 의도:
- 페르소나 프롬프트의 [BEHAVIORAL DATA] 섹션 생성에 사용.
- 27 척도(L1-1 ~ C-3) 단위로 한국어 시나리오 + 응답 라벨을 한 블록씩 출력.
- 응답이 의미를 가질 만한 척도(MPL CE, 객관식 정답, 정성 자유응답)는 raw 값을
  사람 친화적으로 풀어쓰고, 다항 Likert 척도는 점수 분포 + 의미 해석 한 줄.
- token 효율을 위해 모든 18~20개 Likert 답을 일일이 나열하지 않고 *평균·고저
  포인트만* 요약. 진짜 raw N=1~3 응답 (MPL, A/B 선택, CRT 정답, dictator 등) 만
  개별 문항으로 풀어쓴다.

token 예상: 27 척도 × 평균 ~150 chars ≈ 4000~5000 chars ≈ 3000~4000 tokens.

V1 hold-out 자극(holdout_recent_purchase 등)은 234문항 *바깥*이라 본 모듈을
거치지 않으므로, hold-out 평가는 그대로 유효.

EVAL_SPEC.md §1 + 6-LENS_MAPPING.md SSOT 참조.
"""
from __future__ import annotations

from typing import Any

from lenses.mapping import LENS_DEFINITIONS

# ── Likert/스케일 의미 해석 ────────────────────────────────────────────────

def _likert_label(score: float, scale_max: int, *, low: str, mid: str, high: str) -> str:
    """평균 점수 → 저/중/고 라벨."""
    if score < scale_max * 0.4:
        return low
    if score < scale_max * 0.65:
        return mid
    return high


def _avg_of_keys(responses: dict, keys: list[str]) -> float | None:
    vals = []
    for k in keys:
        v = responses.get(k)
        if isinstance(v, (int, float)):
            vals.append(float(v))
    return sum(vals) / len(vals) if vals else None


# ── L1 경제적 합리성 ─────────────────────────────────────────────────────

def _l1_1_risk_aversion(r: dict, p: dict) -> str:
    """L1-1 위험 회피 MPL CE × 3셋."""
    ce1 = r.get("L1-1.Q1.row_first_certain")
    ce2 = r.get("L1-1.Q2.row_first_certain")
    ce3 = r.get("L1-1.Q3.row_first_certain")
    ra = p.get("l1.risk_aversion")
    lines = ["[L1-1 위험 회피 — 확실한 금액 vs 도박]"]
    if ce1 is not None:
        lines.append(f"Q: 100% 확률로 받는 확실한 금액 vs 50% 확률로 6,000원을 받는 도박. 두 선택이 동등하다고 본 확실한 금액은?\nA: {int(ce1):,}원.")
    if ce2 is not None:
        lines.append(f"Q: 100% 확률 확실한 금액 vs 50% 확률 10,000원 도박. 동등 확실 금액?\nA: {int(ce2):,}원.")
    if ce3 is not None:
        lines.append(f"Q: 100% 확률 확실한 금액 vs 50% 확률 10,000원 도박(반복). 동등 확실 금액?\nA: {int(ce3):,}원.")
    if ra is not None:
        verdict = "위험을 강하게 회피" if ra >= 0.4 else "위험 중립에 가까움" if ra >= 0.1 else "위험 추구 성향"
        lines.append(f"종합: risk_aversion = {ra:.2f} ({verdict}).")
    return "\n".join(lines)


def _l1_2_loss_aversion(r: dict, p: dict) -> str:
    """L1-2 손실 회피."""
    q4 = r.get("L1-2.Q4.row_first_positive")
    lam = p.get("l1.loss_aversion_lambda")
    lines = ["[L1-2 손실 회피 — 혼합 복권]"]
    if q4 is not None:
        lines.append(f"Q: 50% 확률로 8,000원 잃거나 50% 확률로 X원 따는 복권. X 가 얼마면 수락하시겠습니까?\nA: {int(q4):,}원 이상이면 수락.")
    if lam is not None:
        verdict = "이득보다 손실에 매우 민감" if lam >= 2.0 else "다소 민감" if lam >= 1.2 else "거의 중립"
        lines.append(f"종합: λ = {lam:.2f} ({verdict}).")
    return "\n".join(lines)


def _l1_3_mental_accounting(r: dict, p: dict) -> str:
    """L1-3 심적 회계 A/B 선택 4문항."""
    qs = [r.get(f"L1-3.Q{i}") for i in range(1, 5)]
    ma = p.get("l1.mental_accounting")
    lines = ["[L1-3 심적 회계 — 돈의 용도 분리]"]
    labels = [
        ("이미 산 영화표를 잃어버렸을 때 다시 사겠습니까?", "A(다시 안 산다)", "B(다시 산다)"),
        ("영화표 값과 같은 현금을 잃어버린 직후 영화표를 사겠습니까?", "A(산다)", "B(안 산다)"),
        ("작은 가전을 사기 위해 20분 떨어진 매장에서 5천원 할인을 받겠습니까?", "A(간다)", "B(안 간다)"),
        ("큰 가전을 사기 위해 같은 20분 거리 매장에서 5천원 할인을 받겠습니까?", "A(간다)", "B(안 간다)"),
    ]
    for i, (q, a, b) in enumerate(labels):
        ans = qs[i]
        if ans:
            lines.append(f"Q{i+1}: {q}\nA: {a if ans == 'A' else b}.")
    if ma is not None:
        verdict = "용도별 회계가 강함" if ma >= 0.7 else "보통" if ma >= 0.4 else "통합적 회계"
        lines.append(f"종합: mental_accounting = {ma:.2f} ({verdict}).")
    return "\n".join(lines)


def _l1_4_tightwad(r: dict, p: dict) -> str:
    """L1-4 구두쇠-낭비벽 합산 점수."""
    ts = p.get("l1.tightwad_spendthrift")
    lines = ["[L1-4 구두쇠-낭비벽]"]
    if ts is not None:
        verdict = "낭비벽 성향" if ts >= 18 else "균형" if ts >= 11 else "구두쇠 성향"
        lines.append(f"Q: 지출 통제 4문항(11점·5점 척도) 합산 점수.\nA: {ts:.0f}/26 — {verdict}.")
    return "\n".join(lines)


def _l1_5_framing(r: dict, p: dict | None = None) -> str:
    cond = r.get("L1-5.Q1.condition")
    resp = r.get("L1-5.Q1.response")
    if cond is None or resp is None:
        return ""
    frame_label = "이득 프레임(살릴 사람 수)" if cond == "gain" else "손실 프레임(죽을 사람 수)"
    a_or_b = "A(확실한 결과)" if resp <= 3 else "B(도박)"
    return (
        "[L1-5 프레이밍 효과]\n"
        f"Q: 전염병 시나리오 — {frame_label}로 제시. 두 선택지 중 어느 쪽을 선호?\nA: {a_or_b} (응답값 {resp}/6)."
    )


def _l1_6_savings(r: dict, p: dict | None = None) -> str:
    cond = r.get("L1-6.Q1.condition")
    resp = r.get("L1-6.Q1.response")
    if cond is None or resp is None:
        return ""
    item = "15,000원짜리 계산기 (5,000원 할인 = 33% 절감)" if cond == "calculator" else "125,000원짜리 재킷 (5,000원 할인 = 4% 절감)"
    return (
        "[L1-6 절대 vs 상대 절약]\n"
        f"Q: {item}을 20분 떨어진 매장에서 5천원 더 싸게 살 수 있다면 가시겠습니까?\nA: {'예' if resp == 'yes' else '아니오'}."
    )


# ── L2 의사결정 스타일 ───────────────────────────────────────────────────

def _likert_block(label: str, avg: float | None, scale_max: int, n: int, *,
                  low: str, mid: str, high: str) -> str:
    if avg is None:
        return ""
    verdict = _likert_label(avg, scale_max, low=low, mid=mid, high=high)
    return f"[{label}]\nQ: {n}문항 Likert {scale_max}점 척도 평균.\nA: {avg:.2f}/{scale_max} — {verdict}."


def _l2_maximization(r: dict, p: dict) -> str:
    return _likert_block(
        "L2-1 극대화 척도", p.get("l2.maximization"), 7, 6,
        low="만족형(충분히 좋으면 OK)", mid="중간", high="극대화형(항상 최고를 추구)",
    )


def _l2_closure(r: dict, p: dict) -> str:
    return _likert_block(
        "L2-2 인지적 종결 욕구", p.get("l2.need_for_closure"), 6, 15,
        low="모호함 잘 견딤", mid="중간", high="빠른 결론을 원함(애매한 상태 싫어함)",
    )


def _l2_cognition(r: dict, p: dict) -> str:
    return _likert_block(
        "L2-3 인지 욕구", p.get("l2.need_for_cognition"), 5, 18,
        low="복잡한 사고 회피", mid="중간", high="깊이 생각하는 것을 즐김",
    )


def _l2_crt(r: dict, p: dict) -> str:
    crt = p.get("l2.crt_score")
    raw = {f"Q{i}": r.get(f"L2-4.Q{i}") for i in range(1, 5)}
    lines = ["[L2-4 인지 반사 검사 (CRT)]"]
    crt_qs = [
        ("준수와 수아가 야구방망이와 공을 합쳐 11,000원에 샀습니다. 방망이가 공보다 10,000원 더 비싸면 공 값은? (직관: 1,000원 / 정답: 500원)", "수아"),
        ("기계 5대가 위젯 5개 만드는 데 5분 걸린다면, 100대가 100개 만드는 데 몇 분?", "0"),
        ("연못의 수련잎이 매일 두 배로 늘어 48일째에 다 덮습니다. 절반을 덮는 데 며칠?", "2"),
    ]
    given = []
    for i, (q_text, ans) in enumerate(crt_qs, start=1):
        v = raw[f"Q{i}"]
        if v is not None:
            given.append(f"Q{i}: {q_text}\nA: {v}.")
    if given:
        lines.extend(given[:2])  # token 절감 — 2개만
    if crt is not None:
        verdict = "숙고형(직관 함정 잘 피함)" if crt >= 3 else "혼합" if crt >= 1 else "직관형"
        lines.append(f"종합: CRT 정답 {int(crt)}/4 — {verdict}.")
    return "\n".join(lines)


# ── L3 동기 구조 ─────────────────────────────────────────────────────────

def _l3_regulatory(r: dict, p: dict) -> str:
    rf = p.get("l3.regulatory_focus")
    if rf is None:
        return ""
    verdict = "촉진 초점(이상·성취 지향)" if rf >= 5.0 else "혼합" if rf >= 3.5 else "예방 초점(의무·안전 지향)"
    return f"[L3-1 조절초점 척도]\nQ: 10문항 7점 척도 평균.\nA: {rf:.2f}/7 — {verdict}."


def _l3_agency_communion(r: dict, p: dict) -> str:
    ag = p.get("l3.agency")
    co = p.get("l3.communion")
    if ag is None or co is None:
        return ""
    dom = "자기지향이 우세" if ag - co > 0.5 else "타인지향이 우세" if co - ag > 0.5 else "균형"
    return (
        "[L3-2 자기지향 vs 타인지향 가치]\n"
        f"Q: 24개 가치 항목 중요도(9점) 평균.\nA: Agency(자기지향) {ag:.2f}/9, Communion(타인지향) {co:.2f}/9 — {dom}."
    )


def _l3_uniqueness(r: dict, p: dict) -> str:
    return _likert_block(
        "L3-3 독특성 욕구", p.get("l3.need_for_uniqueness"), 5, 12,
        low="동조 성향", mid="중간", high="남과 다르고 싶어함",
    )


def _l3_4_qualitative_skip() -> str:
    """L3-4 정성 anchor 는 [QUALITATIVE ANCHORS] 섹션이 별도로 처리."""
    return ""


# ── L4 사회적 영향 ───────────────────────────────────────────────────────

def _l4_self_monitoring(r: dict, p: dict) -> str:
    return _likert_block(
        "L4-1 자기 감시", p.get("l4.self_monitoring"), 5, 13,
        low="자기 모습 일관(상황 적응 적음)", mid="중간", high="상황에 맞춰 적응 잘함",
    )


def _l4_individualism(r: dict, p: dict) -> str:
    hi = p.get("l4.horizontal_individualism")
    vi = p.get("l4.vertical_individualism")
    hc = p.get("l4.horizontal_collectivism")
    vc = p.get("l4.vertical_collectivism")
    if None in (hi, vi, hc, vc):
        return ""
    return (
        "[L4-2 개인주의 vs 집단주의 (5점, 4그룹 × 4문항)]\n"
        f"Q: 4개 하위 차원 평균.\nA: 수평개인 {hi:.2f}, 수직개인 {vi:.2f}, 수평집단 {hc:.2f}, 수직집단 {vc:.2f} (모두 1~5)."
    )


def _l4_social_desirability(r: dict, p: dict) -> str:
    sd = p.get("l4.social_desirability")
    if sd is None:
        return ""
    verdict = "사회적 바람직성 응답 강함" if sd >= 9 else "보통" if sd >= 5 else "정직 응답 성향"
    return f"[L4-3 사회적 바람직성]\nQ: 13문항 TRUE/FALSE 정답 일치 수.\nA: {sd:.0f}/13 — {verdict}."


def _l4_empathy(r: dict, p: dict) -> str:
    return _likert_block(
        "L4-4 공감 (BES-A)", p.get("l4.empathy"), 5, 20,
        low="공감 약함", mid="보통", high="높은 공감(타인 감정 잘 읽음)",
    )


def _l4_fc(r: dict, p: dict) -> str:
    fc = p.get("l4.false_consensus_effect")
    if fc is None:
        return ""
    return f"[L4-5 잘못된 합의 효과]\nQ: 자기 정책 입장이 예상 지지율에 미친 영향.\nA: FC 효과 {fc:.2f} (양수=내 입장 더 보편적이라 봄)."


def _l4_dictator(r: dict, p: dict) -> str:
    send = p.get("l4.dictator_send")
    ratio = p.get("l4.dictator_send_ratio")
    if send is None:
        return ""
    return (
        "[L4-6 독재자 게임]\n"
        f"Q: 익명의 상대에게 0/1000/2000/4000/5000원 중 보낼 금액 선택.\n"
        f"A: {int(send):,}원 송금 (전체 5000원 중 {ratio*100:.0f}% 분배)."
    )


# ── L5 가치 사슬 ─────────────────────────────────────────────────────────

def _l5_minimalism(r: dict, p: dict) -> str:
    return _likert_block(
        "L5-1 소비자 미니멀리즘", p.get("l5.minimalism"), 5, 12,
        low="소유·소비 추구", mid="중간", high="적게 가지고 단순하게 사는 것을 선호",
    )


def _l5_green(r: dict, p: dict) -> str:
    return _likert_block(
        "L5-2 친환경 가치", p.get("l5.green_values"), 5, 6,
        low="친환경에 관심 적음", mid="보통", high="친환경 가치 강함(자연·기후 우선시)",
    )


# ── L6 시간 지향 ─────────────────────────────────────────────────────────

def _l6_discount(r: dict, p: dict) -> str:
    dr = p.get("l6.discount_rate_annual")
    if dr is None:
        return ""
    verdict = "미래 가치를 매우 낮게 봄(현재 선호)" if dr > 1.0 else "보통" if dr > 0.2 else "미래 지향(인내심 강함)"
    return f"[L6-1 할인율 — 시간에 따른 가치 감소]\nQ: 1~2주 후 받을 큰 금액 vs 지금 받을 작은 금액 MPL.\nA: 연환산 할인율 {dr:.2f} — {verdict}."


def _l6_present_bias(r: dict, p: dict) -> str:
    pb = p.get("l6.present_bias_beta")
    if pb is None:
        return ""
    verdict = "현재 편향 강함(즉시 보상 선호)" if pb > 0.05 else "거의 없음" if pb > -0.05 else "미래 편향(보상을 미룸)"
    return f"[L6-2 현재 편향 β]\nQ: 같은 시간 차이라도 \"지금 vs 1주\" 와 \"1년 vs 1년1주\" 의 선택이 다른가.\nA: β = {pb:.2f} — {verdict}."


def _l6_conscientiousness(r: dict, p: dict) -> str:
    c = p.get("l6.conscientiousness")
    if c is None:
        return ""
    verdict = "성실성 매우 높음(체계적·근면)" if c >= 6 else "보통" if c >= 3 else "성실성 낮음(자발적·유연)"
    return f"[L6-3 성실성]\nQ: 8문항 9점 척도 (역채점 포함). 자기 통제·체계성 점수.\nA: {int(c)}/8 — {verdict}."


# ── 통제 변수 ────────────────────────────────────────────────────────────

def _c2_financial(r: dict, p: dict) -> str:
    f = p.get("ability.financial_literacy")
    if f is None:
        return ""
    verdict = "금융 이해력 높음" if f >= 6 else "보통" if f >= 3 else "낮음"
    return f"[C-2 금융 이해력]\nQ: 인플레·이자·자산 다양화 등 8문항 정답.\nA: {int(f)}/8 — {verdict}."


def _c3_numeracy(r: dict, p: dict) -> str:
    n = p.get("ability.numeracy")
    if n is None:
        return ""
    verdict = "수리 능력 높음" if n >= 6 else "보통" if n >= 3 else "낮음"
    return f"[C-3 수리 능력]\nQ: 비율·확률·소수 계산 8문항 정답.\nA: {int(n)}/8 — {verdict}."


# ── 그룹별 빌더 ─────────────────────────────────────────────────────────

_GROUP_BUILDERS = {
    "L1": [_l1_1_risk_aversion, _l1_2_loss_aversion, _l1_3_mental_accounting,
           _l1_4_tightwad, _l1_5_framing, _l1_6_savings],
    "L2": [_l2_maximization, _l2_closure, _l2_cognition, _l2_crt],
    "L3": [_l3_regulatory, _l3_agency_communion, _l3_uniqueness],
    "L4": [_l4_self_monitoring, _l4_individualism, _l4_social_desirability,
           _l4_empathy, _l4_fc, _l4_dictator],
    "L5": [_l5_minimalism, _l5_green],
    "L6": [_l6_discount, _l6_present_bias, _l6_conscientiousness],
    "C":  [_c2_financial, _c3_numeracy],
}

_GROUP_TITLES = {
    "L1": "L1. 경제적 합리성 (Economic Rationality)",
    "L2": "L2. 의사결정 스타일 (Decision-Making Style)",
    "L3": "L3. 동기 구조 (Motivation Structure)",
    "L4": "L4. 사회적 영향 (Social Influence)",
    "L5": "L5. 가치 사슬 (Means-End Values)",
    "L6": "L6. 시간 지향 (Time Orientation)",
    "C":  "보조 능력 지표",
}


def build_behavioral_data(responses: dict[str, Any], persona_params: dict[str, Any]) -> str:
    """234문항 raw 응답을 척도 단위 시나리오 텍스트로 변환.

    Args:
        responses: 입력 JSON 의 responses dict (L1-1.Q1.row_first_certain 등).
        persona_params: scoring.pipeline.score_all() 결과 (l1.risk_aversion 등).

    Returns:
        "[BEHAVIORAL DATA]\n{그룹별 블록}" 시스템 프롬프트 섹션.
    """
    if not isinstance(responses, dict):
        responses = {}
    if not isinstance(persona_params, dict):
        persona_params = {}

    sections: list[str] = ["[BEHAVIORAL DATA]"]
    sections.append(
        "다음은 응답자가 실제로 답한 27개 척도의 결과입니다. 각 블록의 "
        "Q&A 시나리오와 종합 해석을 반영해 자기 행동·의사결정을 일관성 있게 유지하세요."
    )
    for group, builders in _GROUP_BUILDERS.items():
        title = f"\n## {_GROUP_TITLES[group]}"
        blocks = []
        for fn in builders:
            block = fn(responses, persona_params)
            if block:
                blocks.append(block)
        if blocks:
            sections.append(title)
            sections.append("\n\n".join(blocks))

    return "\n".join(sections)


__all__ = ["build_behavioral_data"]
