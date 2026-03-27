"""
Phase 2 — Persona Generation Pipeline
=======================================
Step A: 역할 도출
Step B: 페르소나 카드 생성
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from openai import AsyncOpenAI

from .models import PersonaOutput, RolesOutput
from .prompts import STEP_A_REVISE_SYSTEM, STEP_A_SYSTEM, STEP_B_SYSTEM

# ── 설정값 ──────────────────────────────────────────────────
LLM_MODEL = "gpt-4o"
RAW_BASE = Path("raw")


# ── 유틸 ────────────────────────────────────────────────────

def _sanitize_name(name: str) -> str:
    return re.sub(r"[^\w가-힣-]", "_", name).strip("_")


def _personas_dir(project_name: str) -> Path:
    return RAW_BASE / _sanitize_name(project_name) / "personas"


def _research_dir(project_name: str) -> Path:
    return RAW_BASE / _sanitize_name(project_name) / "research"


def _init_openai() -> AsyncOpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.startswith("sk-your"):
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")
    return AsyncOpenAI(api_key=key)


async def _call_llm(
    client: AsyncOpenAI,
    system: str,
    user_msg: str,
    temperature: float = 0.4,
) -> dict:
    response = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def load_research_output(project_name: str) -> dict:
    """Phase 1 결과를 raw/{project_name}/research/output.json에서 로드."""
    path = _research_dir(project_name) / "output.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Phase 1 결과가 없습니다: {path}. 먼저 /research/start → approve를 실행하세요."
        )
    return json.loads(path.read_text(encoding="utf-8"))


# ── Step A: 역할 도출 ──────────────────────────────────────

async def step_a_derive_roles(project_name: str) -> RolesOutput:
    """Phase 1 결과 → 역할 목록 3~5개."""
    client = _init_openai()
    research = load_research_output(project_name)

    user_msg = (
        "아래 리서치 결과를 분석하여 회의에 필요한 전문가 역할을 도출해주세요.\n\n"
        f"topic: {research.get('topic', '')}\n"
        f"purpose: {research.get('purpose', '')}\n\n"
        f"## research_frame\n{json.dumps(research.get('research_frame', {}), ensure_ascii=False, indent=2)}\n\n"
        f"## gaps_remaining\n{json.dumps(research.get('gaps_remaining', []), ensure_ascii=False)}"
    )

    result = await _call_llm(client, STEP_A_SYSTEM, user_msg, temperature=0.4)
    roles_output = RolesOutput(**result)

    # 저장
    pdir = _personas_dir(project_name)
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "roles.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return roles_output


async def step_a_revise_roles(
    project_name: str, current_roles: RolesOutput, feedback: str
) -> RolesOutput:
    """사용자 피드백을 반영하여 역할 목록 수정."""
    client = _init_openai()
    research = load_research_output(project_name)

    user_msg = (
        f"현재 역할 목록:\n{json.dumps(current_roles.model_dump(), ensure_ascii=False, indent=2)}\n\n"
        f"리서치 주제: {research.get('topic', '')}\n"
        f"purpose: {research.get('purpose', '')}\n\n"
        f'사용자 수정 요청:\n"{feedback}"\n\n'
        "수정사항을 반영한 역할 목록을 JSON으로 출력하세요."
    )

    result = await _call_llm(client, STEP_A_REVISE_SYSTEM, user_msg, temperature=0.4)
    roles_output = RolesOutput(**result)

    # 저장
    pdir = _personas_dir(project_name)
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "roles.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return roles_output


# ── Step B: 페르소나 생성 ──────────────────────────────────

async def step_b_generate_personas(
    project_name: str, roles: RolesOutput
) -> PersonaOutput:
    """승인된 역할 목록 + research_frame → 페르소나 카드."""
    client = _init_openai()
    research = load_research_output(project_name)

    user_msg = (
        "아래 역할 목록과 리서치 결과를 기반으로 각 역할의 페르소나 카드를 생성해주세요.\n\n"
        f"## 기본 정보\n"
        f"topic: {research.get('topic', '')}\n"
        f"purpose: {research.get('purpose', '')}\n\n"
        f"## 역할 목록\n{json.dumps(roles.model_dump(), ensure_ascii=False, indent=2)}\n\n"
        f"## research_frame\n{json.dumps(research.get('research_frame', {}), ensure_ascii=False, indent=2)}\n\n"
        f"## gaps_remaining\n{json.dumps(research.get('gaps_remaining', []), ensure_ascii=False)}"
    )

    result = await _call_llm(client, STEP_B_SYSTEM, user_msg, temperature=0.5)

    persona_output = PersonaOutput(
        project_name=_sanitize_name(project_name),
        topic=research.get("topic", ""),
        purpose=research.get("purpose", ""),
        meeting_agenda=result.get("meeting_agenda", ""),
        personas=result.get("personas", []),
        discussion_seeds=result.get("discussion_seeds", []),
    )

    # 저장
    pdir = _personas_dir(project_name)
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "persona_cards.json").write_text(
        json.dumps(persona_output.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return persona_output
