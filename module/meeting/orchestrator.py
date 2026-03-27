"""
오케스트레이터 — 회의 진행자 에이전트.
발언자 선택 + 합의 판단.
"""

from __future__ import annotations

import json

from openai import AsyncOpenAI

from module.persona.models import PersonaCard

from .models import MeetingEntry, OrchestratorDecision
from .prompts import ORCHESTRATOR_SYSTEM

LLM_MODEL = "gpt-4o"


def _format_participants(personas: list[PersonaCard]) -> str:
    lines: list[str] = []
    for p in personas:
        lines.append(f"- {p.id} ({p.role}): 목표 — {p.goal_in_meeting}")
    return "\n".join(lines)


def _format_log(meeting_log: list[MeetingEntry]) -> str:
    if not meeting_log:
        return "(아직 발언 없음)"
    lines: list[str] = []
    for e in meeting_log:
        prefix = f"[Round {e.round}] {e.speaker_role}({e.speaker_id})"
        lines.append(f"{prefix}: {e.content}")
    return "\n".join(lines)


async def decide_next_speaker(
    client: AsyncOpenAI,
    meeting_agenda: str,
    personas: list[PersonaCard],
    meeting_log: list[MeetingEntry],
) -> OrchestratorDecision:
    """오케스트레이터가 다음 발언자를 선택하고 합의 여부를 판단."""

    user_msg = (
        f"## 회의 안건\n{meeting_agenda}\n\n"
        f"## 참여자 목록\n{_format_participants(personas)}\n\n"
        f"## 지금까지의 회의록\n{_format_log(meeting_log)}\n\n"
        "다음 발언자를 선택하고, 합의 도달 여부를 판단해주세요."
    )

    response = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": ORCHESTRATOR_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    return OrchestratorDecision(**result)
