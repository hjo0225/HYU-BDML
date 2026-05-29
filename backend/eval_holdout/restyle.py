"""홀드아웃 표시용 말투 통일 (LLM 후처리, plan 0023 연장).

성능평가 대시보드에서 사람·AI 답변을 나란히 둘 때, 말투(문체·어미·맞춤법) 차이로
시선이 분산되지 않도록 두 답변을 같은 구어체 존댓말 톤으로 다시 쓴다.
**내용·입장·구체 정보는 보존**하며, 결과는 *_display 필드(표시 전용)로만 저장한다.
유사도 점수는 원본 답변 기준 그대로다(여기서 만들지 않는다).
"""
from __future__ import annotations

import json

from fgi import config
from services.llm_client import chat_completion

_SYSTEM = (
    "당신은 인터뷰 응답을 다듬는 한국어 에디터입니다. "
    "말투(문체)만 통일하고 내용·입장·정보·결론은 절대 바꾸지 않습니다."
)


async def unify_tone(
    question: str,
    human_answer: str,
    agent_answer: str,
    *,
    mock: bool | None = None,
) -> dict[str, str]:
    """두 답변을 같은 구어체 존댓말 톤으로 통일해 {'human','agent'} 로 반환.

    1회 LLM 호출. 실패·키없음·파싱오류 시 원본을 그대로 돌려준다(폴백).
    어느 쪽이 사람/AI 인지 모델에 노출하지 않으려고 A/B 로 익명화해 전달한다.
    """
    if not (human_answer or agent_answer):
        return {"human": human_answer, "agent": agent_answer}
    user = (
        f"질문: {question}\n\n"
        f"[A]\n{human_answer}\n\n[B]\n{agent_answer}\n\n"
        "A 와 B 를 모두 자연스러운 구어체 존댓말로 통일해 다시 쓰세요. 규칙:\n"
        "① 말투·어미·맞춤법만 다듬는다.\n"
        "② 내용·입장·구체 정보·결론은 그대로 유지한다(없는 내용 추가·삭제 금지).\n"
        "③ 길이를 인위적으로 늘리거나 줄이지 않는다.\n"
        '오직 JSON 만 출력: {"A": "...", "B": "..."}'
    )
    try:
        raw = (
            await chat_completion(
                system=_SYSTEM,
                user=user,
                model=config.CHAT_MODEL,
                temperature=0.2,
                max_tokens=500,
                mock=mock,
            )
        ).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(raw)
        h = str(data.get("A") or "").strip()
        a = str(data.get("B") or "").strip()
        return {"human": h or human_answer, "agent": a or agent_answer}
    except Exception:  # noqa: BLE001 — 폴백: 원본 유지
        return {"human": human_answer, "agent": agent_answer}
