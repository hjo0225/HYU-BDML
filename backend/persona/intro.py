"""에이전트 카드용 1~2문장 한국어 소개 생성."""
from __future__ import annotations


_INCOME_LABEL = {
    "200만원 미만": "저소득층",
    "200~300만원": "중저소득층",
    "300~500만원": "중산층",
    "500~700만원": "중상위층",
    "700~1,000만원": "상위층",
    "1,000~1,500만원": "고소득층",
    "1,500만원 이상": "최상위층",
}


def build_intro_ko(persona_params: dict, demographics: dict) -> str:
    """인구통계 + 핵심 수치 기반 1~2문장 소개."""
    gender = demographics.get("gender", "")
    age_range = demographics.get("age_range", "")
    region = demographics.get("region", "")
    education = demographics.get("education", "")
    employment = demographics.get("employment", "")
    income_raw = demographics.get("household_income", "")
    income_label = _INCOME_LABEL.get(income_raw, income_raw)

    # 핵심 성향 키워드
    traits = []
    ra = persona_params.get("l1.risk_aversion", 0.5)
    if ra > 0.6:
        traits.append("위험 회피 성향")
    elif ra < 0.2:
        traits.append("위험 추구 성향")

    nfc = persona_params.get("l2.need_for_cognition", 3.0)
    if nfc >= 4.0:
        traits.append("깊은 사고를 즐기는")
    elif nfc <= 2.0:
        traits.append("직관적 판단을 선호하는")

    communal = persona_params.get("l3.communion", 5.0)
    agency = persona_params.get("l3.agency", 5.0)
    if communal > agency + 1:
        traits.append("타인 지향적 가치관")
    elif agency > communal + 1:
        traits.append("자기 주도적 가치관")

    trait_str = ", ".join(traits) if traits else "다양한 소비 성향"
    parts = []
    if gender and age_range:
        parts.append(f"{age_range}의 {gender}")
    if region:
        parts.append(f"{region} 거주")
    if employment:
        parts.append(employment)
    if income_label:
        parts.append(f"월 가구소득 {income_raw}")

    intro_first = "한국 소비자 디지털 트윈입니다."
    if parts:
        intro_first = f"{'·'.join(parts)} 한국 소비자 디지털 트윈입니다."
    intro_second = f"주요 특성: {trait_str}."
    return f"{intro_first} {intro_second}"
