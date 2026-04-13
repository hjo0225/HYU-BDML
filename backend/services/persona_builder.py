"""
페르소나 빌드 서비스.
DB에서 패널 데이터 + 메모리 조회 → AgentSchema 변환.
CSV/파일 시스템 의존 없이 Cloud SQL에서 직접 데이터를 가져온다.
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal, Panel, PanelMemory
from rag.panel_selector import load_panels, select_representative_panels
from rag.embedder import embed

# 에이전트 카드 색상 팔레트 (panel_id 인덱스 기반)
_COLORS = [
    "#1B4B8C", "#2E6DB4", "#3A7BC8", "#1565C0", "#0277BD",
    "#00695C", "#2E7D32", "#558B2F", "#F57C00", "#E65100",
]


def get_age_group(age: int | None) -> str:
    """나이 정수 → '30대' 형식 문자열."""
    if not age or age <= 0:
        return "나이 미상"
    decade = (age // 10) * 10
    return f"{decade}대"


async def load_persona_from_db(session: AsyncSession, panel_id: str) -> dict | None:
    """DB에서 panel scratch + memories(임베딩 포함)를 persona dict로 조회."""
    # Panel 조회
    result = await session.execute(
        select(Panel).where(Panel.panel_id == panel_id)
    )
    panel = result.scalar_one_or_none()
    if not panel:
        return None

    # scratch 파싱
    scratch = panel.scratch
    if isinstance(scratch, str):
        scratch = json.loads(scratch)

    # 메모리 조회
    mem_result = await session.execute(
        select(PanelMemory).where(PanelMemory.panel_id == panel_id)
    )
    memories_rows = mem_result.scalars().all()

    memories = []
    for m in memories_rows:
        emb = m.embedding
        if isinstance(emb, str):
            emb = json.loads(emb)
        memories.append({
            "category": m.category,
            "text": m.text,
            "importance": m.importance,
            "embedding": emb,
        })

    return {
        "panel_id": panel_id,
        "scratch": scratch,
        "memories": memories,
        "n_memories": len(memories),
    }


def persona_to_agent_schema(
    persona: dict,
    agent_id: str,
    name: str,
    emoji: str,
    color: str,
    tags: list[str],
) -> dict:
    """
    완성된 persona dict → AgentSchema-compatible dict.
    scratch에서 demographics 추출, memory_count 계산.
    """
    scratch = persona.get("scratch", {})
    age = scratch.get("age")
    gender_raw = scratch.get("gender", "")
    occupation = scratch.get("occupation", "직업 미상")
    region = scratch.get("region", "지역 미상")

    demographics = {
        "age_group": get_age_group(age),
        "gender": gender_raw or "미상",
        "occupation": occupation,
        "region": region,
    }

    memory_count = persona.get("n_memories", len(persona.get("memories", [])))

    return {
        "id": agent_id,
        "type": "customer",
        "name": name,
        "emoji": emoji,
        "description": f"{demographics['age_group']} {gender_raw} {occupation} ({region})",
        "tags": tags,
        "system_prompt": "",  # RAG 에이전트는 runtime에 메모리에서 구성
        "color": color,
        "panel_id": persona["panel_id"],
        "demographics": demographics,
        "memory_count": memory_count,
    }


def _generate_panel_name(scratch: dict, index: int) -> tuple[str, str]:
    """scratch 정보로 가상의 이름과 이모지를 생성한다."""
    gender = scratch.get("gender", "")

    female_names = ["김지연", "이수진", "박민지", "최유나", "정하은", "윤서연", "한채원", "임소은"]
    male_names = ["김민준", "이도현", "박지호", "최준혁", "정성훈", "윤재원", "한승우", "임태양"]

    if "여" in gender:
        name = female_names[index % len(female_names)]
        emoji = "👩"
    elif "남" in gender:
        name = male_names[index % len(male_names)]
        emoji = "👨"
    else:
        name = f"참여자 {index + 1}"
        emoji = "👤"

    return name, emoji


def _default_tags(scratch: dict) -> list[str]:
    """scratch에서 의미 있는 태그 2-3개 추출."""
    tags = []
    occupation = scratch.get("occupation", "")
    if occupation:
        tags.append(occupation)

    region = scratch.get("region", "")
    if region:
        tags.append(region)

    traits = scratch.get("strong_traits", [])
    if traits:
        tags.append(traits[0])

    return tags[:3]


async def load_panel_memories_bulk(
    session: AsyncSession,
    panel_ids: list[str],
) -> dict[str, list[dict]]:
    """필터링된 패널들의 메모리를 한 번에 조회. 임베딩 포함."""
    result = await session.execute(
        select(PanelMemory).where(PanelMemory.panel_id.in_(panel_ids))
    )
    rows = result.scalars().all()
    out: dict[str, list[dict]] = {pid: [] for pid in panel_ids}
    for r in rows:
        emb = r.embedding
        if isinstance(emb, str):
            emb = json.loads(emb)
        out[r.panel_id].append({
            "text": r.text,
            "importance": r.importance,
            "embedding": emb,
        })
    return out


async def build_personas_stream(
    target_customer: str = "",
    n_agents: int = 5,
    topic: str = "",
) -> AsyncGenerator[dict, None]:
    """
    DB에서 패널 선정 → persona 조회 → 진행 이벤트 yield.
    각 이벤트는 AgentBuildProgressEvent 형태의 dict.
    topic이 주어지면 주제 관련성을 반영해 패널을 선정한다.
    """
    total = n_agents

    # ── Step 1: DB에서 패널 목록 조회 ──
    yield {
        "type": "build_progress",
        "step": "selecting",
        "current": 0,
        "total": total,
        "panel_id": None,
        "message": "클러스터 다양성 기반 패널 선정 중..."
            + (f" (주제: {topic[:30]}...)" if len(topic) > 30 else f" (주제: {topic})" if topic else ""),
    }

    try:
        async with AsyncSessionLocal() as session:
            panels = await load_panels(session)
    except Exception as e:
        yield {
            "type": "build_progress",
            "step": "error",
            "current": 0,
            "total": total,
            "panel_id": None,
            "message": f"패널 데이터 조회 실패: {e}",
        }
        return

    if not panels:
        yield {
            "type": "build_progress",
            "step": "error",
            "current": 0,
            "total": total,
            "panel_id": None,
            "message": "DB에 패널 데이터가 없습니다. seed_panels 스크립트를 실행해주세요.",
        }
        return

    # ── Step 2: 클러스터 다양성 + 주제 관련성 기반 선정 ──
    try:
        # 주제가 있으면 topic 임베딩 + 패널 메모리로 주제 관련성 반영
        topic_embedding = None
        panel_memories = None
        if topic.strip():
            topic_embedding = await asyncio.to_thread(embed, topic)
            async with AsyncSessionLocal() as session:
                candidate_ids = [p["panel_id"] for p in panels]
                panel_memories = await load_panel_memories_bulk(session, candidate_ids)

        selected_ids = select_representative_panels(
            panels, n_agents,
            topic_embedding=topic_embedding,
            panel_memories=panel_memories,
        )
    except Exception as e:
        yield {
            "type": "build_progress",
            "step": "error",
            "current": 0,
            "total": total,
            "panel_id": None,
            "message": f"패널 선정 실패: {e}",
        }
        return

    # ── Step 3: 각 패널 persona 조회 ──
    built_agents: list[dict] = []

    async with AsyncSessionLocal() as session:
        for idx, panel_id in enumerate(selected_ids):
            yield {
                "type": "build_progress",
                "step": "building",
                "current": idx + 1,
                "total": total,
                "panel_id": panel_id,
                "message": f"패널 {idx + 1}/{total} 조회 중: {panel_id}",
            }

            try:
                persona = await load_persona_from_db(session, panel_id)
                if not persona:
                    yield {
                        "type": "build_progress",
                        "step": "error",
                        "current": idx + 1,
                        "total": total,
                        "panel_id": panel_id,
                        "message": f"{panel_id} 패널을 DB에서 찾을 수 없습니다.",
                    }
                    continue

                mem_count = persona.get("n_memories", 0)

                yield {
                    "type": "build_progress",
                    "step": "embedding",
                    "current": idx + 1,
                    "total": total,
                    "panel_id": panel_id,
                    "message": f"메모리 로드 완료 ({mem_count}개)",
                }

                # AgentSchema dict 변환
                scratch = persona.get("scratch", {})
                name, emoji = _generate_panel_name(scratch, idx)
                tags = _default_tags(scratch)
                color = _COLORS[idx % len(_COLORS)]

                agent_id = f"panel-{panel_id}"
                agent_dict = persona_to_agent_schema(persona, agent_id, name, emoji, color, tags)
                built_agents.append(agent_dict)

            except Exception as e:
                yield {
                    "type": "build_progress",
                    "step": "error",
                    "current": idx + 1,
                    "total": total,
                    "panel_id": panel_id,
                    "message": f"{panel_id} 조회 실패: {e}",
                }

    # ── Step 4: 완료 ──
    yield {
        "type": "build_progress",
        "step": "done",
        "current": len(built_agents),
        "total": total,
        "panel_id": None,
        "message": f"패널 선정 완료 ({len(built_agents)}명)",
        "agents": built_agents,
    }
