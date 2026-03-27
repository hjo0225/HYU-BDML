"""
에이전트 발언 — OpenAI Streaming API + WebSocket 전송.
"""

from __future__ import annotations

from fastapi import WebSocket
from openai import AsyncOpenAI

from module.persona.models import PersonaCard

from .models import MeetingEntry

LLM_MODEL = "gpt-4o"


def _format_log_for_speaker(meeting_log: list[MeetingEntry]) -> str:
    if not meeting_log:
        return "(아직 발언 없음)"
    lines: list[str] = []
    for e in meeting_log:
        lines.append(f"[Round {e.round}] {e.speaker_role}: {e.content}")
    return "\n".join(lines)


async def speak_with_streaming(
    client: AsyncOpenAI,
    persona: PersonaCard,
    meeting_agenda: str,
    meeting_log: list[MeetingEntry],
    facilitation: str,
    websocket: WebSocket,
) -> str:
    """에이전트가 스트리밍으로 발언하고, 토큰을 WebSocket으로 전송. 전체 텍스트를 반환."""

    user_content = (
        f"## 회의 안건\n{meeting_agenda}\n\n"
        f"## 지금까지의 회의록\n{_format_log_for_speaker(meeting_log)}\n\n"
        f"## 진행자 지시\n{facilitation}\n\n"
        "위 맥락을 바탕으로 당신의 관점에서 발언해주세요."
    )

    stream = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": persona.system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.6,
        stream=True,
    )

    full_response = ""
    async for chunk in stream:
        token = chunk.choices[0].delta.content or ""
        if token:
            full_response += token
            await websocket.send_json({
                "event": "agent_speaking",
                "speaker_id": persona.id,
                "speaker_role": persona.role,
                "token": token,
            })

    await websocket.send_json({
        "event": "agent_complete",
        "speaker_id": persona.id,
        "speaker_role": persona.role,
        "full_text": full_response,
    })

    return full_response
