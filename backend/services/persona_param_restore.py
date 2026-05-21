"""persona_params LLM 복원 (plan 0008 v2 · item 3).

package 에이전트는 구조화 responses 가 없어 persona_params 가 NULL → V1=0, 수치 표시 불가.
persona_text(설문 응답 원문)를 LLM 이 읽어 L1~L6 해석 가능한 척도 점수를 추출·적재한다.
정밀 채점(CE·λ 등 공식 계산)이 아닌 척도 수준 추정 — 데모 표시·V3·레이더용 (decision: LLM 복원).
키 없으면 결정적 mock 폴백.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from services.llm_client import chat_completion

# 복원 대상 척도 (키, 한국어명, 척도범위). 6-LENS_MAPPING.md 의 해석 가능한 Likert 계열.
TARGET_PARAMS: list[tuple[str, str, str]] = [
    ("l1.tightwad_spendthrift", "구두쇠–낭비벽", "4~26 (낮을수록 구두쇠)"),
    ("l1.risk_aversion", "위험 회피", "0~1 (높을수록 회피)"),
    ("l1.mental_accounting", "심적 회계 일치도", "0~1"),
    ("l2.maximization", "극대화 성향", "1~5"),
    ("l2.need_for_closure", "인지적 종결 욕구", "1~5"),
    ("l2.need_for_cognition", "인지 욕구", "1~5"),
    ("l2.crt_score", "인지 반사(CRT)", "0~4"),
    ("l3.regulatory_focus", "조절초점", "1~7"),
    ("l3.agency", "자기지향 가치", "1~9"),
    ("l3.communion", "타인지향 가치", "1~9"),
    ("l3.need_for_uniqueness", "독특성 욕구", "1~5"),
    ("l4.self_monitoring", "자기 감시", "1~5"),
    ("l4.horizontal_individualism", "수평적 개인주의", "1~5"),
    ("l4.vertical_individualism", "수직적 개인주의", "1~5"),
    ("l4.horizontal_collectivism", "수평적 집단주의", "1~5"),
    ("l4.vertical_collectivism", "수직적 집단주의", "1~5"),
    ("l4.empathy", "공감", "1~5"),
    ("l5.minimalism", "소비자 미니멀리즘", "1~5"),
    ("l5.green_values", "친환경 가치", "1~5"),
    ("l6.conscientiousness", "성실성", "0~8"),
    ("l6.present_bias_beta", "현재 편향 β", "0~1 (낮을수록 현재 편향 큼)"),
    ("ability.financial_literacy", "금융 이해력", "0~5"),
    ("ability.numeracy", "수리 능력", "0~11"),
]

_RANGE = {
    "l1.tightwad_spendthrift": (4, 26), "l1.risk_aversion": (0, 1), "l1.mental_accounting": (0, 1),
    "l2.maximization": (1, 5), "l2.need_for_closure": (1, 5), "l2.need_for_cognition": (1, 5), "l2.crt_score": (0, 4),
    "l3.regulatory_focus": (1, 7), "l3.agency": (1, 9), "l3.communion": (1, 9), "l3.need_for_uniqueness": (1, 5),
    "l4.self_monitoring": (1, 5), "l4.horizontal_individualism": (1, 5), "l4.vertical_individualism": (1, 5),
    "l4.horizontal_collectivism": (1, 5), "l4.vertical_collectivism": (1, 5), "l4.empathy": (1, 5),
    "l5.minimalism": (1, 5), "l5.green_values": (1, 5),
    "l6.conscientiousness": (0, 8), "l6.present_bias_beta": (0, 1),
    "ability.financial_literacy": (0, 5), "ability.numeracy": (0, 11),
}

_SYSTEM = "당신은 설문 응답 원문을 읽고 심리측정 척도 점수를 추정하는 채점 전문가입니다."


def _build_prompt(persona_text: str) -> str:
    lines = [f'- "{k}" ({ko}, 범위 {rng})' for k, ko, rng in TARGET_PARAMS]
    schema = "\n".join(lines)
    return (
        "다음은 한 응답자의 설문 응답 원문입니다(범용 6-Lens 배터리 + 도메인 설문 + 인터뷰).\n"
        "응답 내용에 근거하여 아래 각 척도의 점수를 추정해 주세요. 추측을 최소화하고 실제 응답에 맞추세요.\n\n"
        f"=== 응답 원문 ===\n{persona_text[:60000]}\n=== 끝 ===\n\n"
        f"채점할 척도(키 · 범위):\n{schema}\n\n"
        "각 키를 범위 내 숫자로 채운 JSON 객체 하나만 출력하세요. 설명·코드펜스 없이 JSON 만."
    )


def _clamp(key: str, val: Any) -> float | None:
    try:
        v = float(val)
    except (TypeError, ValueError):
        return None
    lo, hi = _RANGE.get(key, (None, None))
    if lo is not None:
        v = max(lo, min(hi, v))
    return round(v, 4)


def _mock_params(seed: str) -> dict[str, float]:
    """결정적 mock — seed 해시로 범위 내 값 분배 (키 없을 때)."""
    out: dict[str, float] = {}
    for i, (k, _ko, _rng) in enumerate(TARGET_PARAMS):
        lo, hi = _RANGE[k]
        h = int(hashlib.sha256(f"{seed}|{k}".encode()).hexdigest()[:8], 16)
        frac = (h % 1000) / 1000.0
        v = lo + frac * (hi - lo)
        out[k] = round(v, 4)
    return out


async def restore_params(persona_text: str, *, seed: str = "", mock: bool | None = None) -> dict[str, float]:
    """persona_text → persona_params dict (해석 가능 척도). 실패/키없음 시 mock."""
    from services.llm_client import _has_api_key  # noqa: PLC0415
    use_mock = mock if mock is not None else not _has_api_key()
    if use_mock:
        return _mock_params(seed or persona_text[:64])
    try:
        raw = await chat_completion(
            system=_SYSTEM, user=_build_prompt(persona_text),
            model="gpt-4o-mini", temperature=0.0, max_tokens=900, mock=False,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(raw)
        out: dict[str, float] = {}
        for k, _ko, _rng in TARGET_PARAMS:
            cv = _clamp(k, data.get(k))
            if cv is not None:
                out[k] = cv
        return out or _mock_params(seed or persona_text[:64])
    except Exception:  # noqa: BLE001
        return _mock_params(seed or persona_text[:64])
