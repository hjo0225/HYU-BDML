"""회의 주제 → 라운드별 질문 제안 (plan 0009 · item 6).

프로젝트 의뢰서(목적·타겟·활용방안)를 컨텍스트로 LLM 이 라운드별 소주제·핵심 질문을
제안한다. API 키가 없거나 파싱 실패 시 결정적 템플릿으로 폴백.
"""
from __future__ import annotations

import json
from typing import Any

from fgi.prompts.round_suggest import ROUND_SUGGEST_SYSTEM, ROUND_SUGGEST_USER
from services.llm_client import chat_completion

_SUGGEST_MODEL = "gpt-4o-mini"

# 라운드 흐름 템플릿 — LLM 미사용 시 폴백. (도입 → 진단 → 원인 → 대안 → 정리)
# probes: 자유토론 수렴 시 의견을 갈라 재점화할 쟁점.
_TEMPLATE_ROUNDS: list[dict[str, Any]] = [
    {"subtopic": "경험 공유", "goal_question": "이 주제와 관련해 최근 겪은 경험을 자유롭게 들려주시겠어요?",
     "probes": ["가장 좋았던 점과 아쉬웠던 점 중 무엇이 더 강하게 남나요?", "혼자일 때와 함께일 때 경험이 다른가요?"]},
    {"subtopic": "문제 진단", "goal_question": "그 경험에서 가장 아쉬웠거나 불편했던 점은 무엇이었나요?",
     "probes": ["가격 문제일까요, 경험 자체의 문제일까요?", "사소한 불편일까요, 다시 안 갈 만한 결정적 문제일까요?"]},
    {"subtopic": "원인 심층", "goal_question": "왜 그렇게 느끼셨다고 생각하세요? 결정적 이유는 무엇이었나요?",
     "probes": ["내 취향 변화 때문일까요, 서비스가 변해서일까요?", "경쟁 대안이 생겨서일까요?"]},
    {"subtopic": "대안·개선", "goal_question": "어떤 점이 달라지면 생각이나 행동이 바뀔 것 같으세요?",
     "probes": ["가격을 낮추는 게 나을까요, 경험을 더 특별하게 만드는 게 나을까요?"]},
    {"subtopic": "정리·우선순위", "goal_question": "오늘 이야기 중 가장 중요하다고 생각하는 것 한 가지는 무엇인가요?",
     "probes": ["당장 바꿔야 할 것과 길게 봐야 할 것 중 무엇이 우선일까요?"]},
]


def _format_brief(brief: dict[str, Any] | None) -> str:
    if not brief:
        return "(추가 맥락 없음)"
    bits = []
    if brief.get("objective"):
        bits.append(f"- 조사 목적: {brief['objective']}")
    if brief.get("target"):
        bits.append(f"- 타겟 소비자: {brief['target']}")
    if brief.get("use_case"):
        bits.append(f"- 결과 활용 방안: {brief['use_case']}")
    return "\n".join(bits) if bits else "(추가 맥락 없음)"


def _template_rounds(n_rounds: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(n_rounds):
        base = _TEMPLATE_ROUNDS[min(i, len(_TEMPLATE_ROUNDS) - 1)]
        out.append({"round": i + 1, "subtopic": base["subtopic"], "goal_question": base["goal_question"],
                    "probes": list(base.get("probes", []))})
    return out


async def suggest_rounds(
    *,
    topic: str,
    n_rounds: int,
    brief: dict[str, Any] | None = None,
    mock: bool | None = None,
) -> list[dict[str, Any]]:
    """라운드별 {round, subtopic, goal_question} 리스트. LLM 실패 시 템플릿 폴백."""
    n_rounds = max(1, min(10, n_rounds))
    try:
        raw = (await chat_completion(
            system=ROUND_SUGGEST_SYSTEM,
            user=ROUND_SUGGEST_USER.format(
                topic=topic, brief=_format_brief(brief), n_rounds=n_rounds,
            ),
            model=_SUGGEST_MODEL, temperature=0.5, max_tokens=800, mock=mock,
        )).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(raw)
        rounds = data.get("rounds")
        if not isinstance(rounds, list) or not rounds:
            raise ValueError("rounds 누락")
        out: list[dict[str, Any]] = []
        for i, r in enumerate(rounds[:n_rounds]):
            sub = str(r.get("subtopic", "")).strip()
            q = str(r.get("goal_question", "")).strip()
            if not q:
                raise ValueError("goal_question 누락")
            raw_probes = r.get("probes") or []
            probes = [str(p).strip() for p in raw_probes if str(p).strip()][:3] if isinstance(raw_probes, list) else []
            out.append({"round": i + 1, "subtopic": sub or f"Round {i + 1}", "goal_question": q, "probes": probes})
        if not out:
            raise ValueError("빈 결과")
        return out
    except Exception:  # noqa: BLE001 — 키 없음/파싱 실패 등 모두 템플릿 폴백
        return _template_rounds(n_rounds)
