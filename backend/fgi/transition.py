"""Round 전환·세션 종료 판단 (plan 0008 v2 · §11·12).

Round 전환(OR): 발화 포화도(novelty<임계) · 최대 발화 수 · 사회자 판단 · 수동 전환.
세션 종료(OR): 전 Round 완료 · 수동 종료 · 60분 타임아웃.
novelty 는 engagement.novelty 가, 수동/타임아웃은 engine 이 처리. 여기서는 사회자 LLM 판단만.
"""
from __future__ import annotations

from fgi import config
from services.llm_client import chat_completion

_JUDGE_SYSTEM = "당신은 FGI 모더레이터입니다. 현재 소주제가 충분히 논의됐는지 판단합니다."


async def moderator_round_done(subtopic: str, recent_summary: str, *, mock: bool | None = None) -> bool:
    """사회자 LLM 판단 — 이 소주제가 충분히 논의됐으면 True. mock/실패 시 False(계속)."""
    if not config.USE_MODERATOR_JUDGE:
        return False
    user = (
        f"소주제: {subtopic}\n지금까지의 발언 요지:\n{recent_summary}\n\n"
        "이 소주제가 더 들을 새 관점 없이 충분히 논의됐습니까? "
        'JSON 한 줄만: {"done": true 또는 false, "reason": "..."}'
    )
    try:
        raw = (await chat_completion(system=_JUDGE_SYSTEM, user=user, model=config.CHAT_MODEL,
                                     temperature=0.0, max_tokens=80, mock=mock)).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        import json
        return bool(json.loads(raw).get("done"))
    except Exception:  # noqa: BLE001
        return False
