"""Twin/Survey 응답 → Agent 적재 서비스.

CLI(scripts/seed_agent.py) 와 라우터(POST /projects/{id}/agents/seed-twin) 가
공유. 응답 1건을 받아 score → persona prompt → 메모리 텍스트 + 임베딩 →
agents + agent_memories INSERT.

진행률 콜백(on_event)을 받아 NDJSON 라우터·CLI 로그 양쪽에 사용한다.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import Agent, AgentMemory, AsyncSessionLocal
from embedding.embedder import average_embedding, embed
from lenses.parser import validate_input
from persona.builder import build_persona
from persona.compressor import count_tokens
from scoring.pipeline import extract_demographics, extract_qualitative, score_all


# ── 메모리 텍스트 합성 ────────────────────────────────────────────────────

def build_memory_texts(
    persona_params: dict[str, Any],
    qualitative: dict[str, Any],
    demographics: dict[str, Any],
) -> list[dict[str, Any]]:
    """단일 에이전트의 메모리 텍스트 목록 합성.

    각 Lens 그룹별 1건 + 능력 + 인구통계 + 정성 3건 ≈ 12 건.
    importance 는 int 0~100 (DATA_MODEL.md 정합).
    """
    memories: list[dict[str, Any]] = []

    ra = persona_params.get("l1.risk_aversion", 0.5)
    la = persona_params.get("l1.loss_aversion_lambda", 1.0)
    memories.append({
        "category": "l1_economic",
        "text": (
            f"위험 회피 성향이 {ra:.2f}이며, 손실 회피 성향 λ={la:.2f}인 소비자입니다. "
            f"심적 회계 분리도 {persona_params.get('l1.mental_accounting', 0.5):.2f}, "
            f"구두쇠-낭비벽 지수 {persona_params.get('l1.tightwad_spendthrift', 13):.0f}/26."
        ),
        "importance": 70,
    })

    max_scale = persona_params.get("l2.maximization", 3.0)
    nfc = persona_params.get("l2.need_for_cognition", 3.0)
    crt = persona_params.get("l2.crt_score", 0)
    memories.append({
        "category": "l2_decision",
        "text": (
            f"극대화 성향 {max_scale:.2f}/7, 인지 욕구 {nfc:.2f}/5. "
            f"CRT 정답 {crt}/4 — {'숙고형' if crt >= 3 else '직관형'} 의사결정 스타일."
        ),
        "importance": 65,
    })

    memories.append({
        "category": "l3_motivation",
        "text": (
            f"자기지향 가치(Agency) {persona_params.get('l3.agency', 5.0):.2f}/9, "
            f"타인지향 가치(Communion) {persona_params.get('l3.communion', 5.0):.2f}/9. "
            f"조절초점 {persona_params.get('l3.regulatory_focus', 4.0):.2f}/7, "
            f"독특성 욕구 {persona_params.get('l3.need_for_uniqueness', 3.0):.2f}/5."
        ),
        "importance": 65,
    })

    memories.append({
        "category": "l4_social",
        "text": (
            f"공감 지수 {persona_params.get('l4.empathy', 3.0):.2f}/5, "
            f"자기 감시 {persona_params.get('l4.self_monitoring', 2.5):.2f}/5. "
            f"독재자 게임 기부 비율 {persona_params.get('l4.dictator_send_ratio', 0.4):.2f}. "
            f"수직집단주의 {persona_params.get('l4.vertical_collectivism', 3.0):.2f}/7."
        ),
        "importance": 60,
    })

    memories.append({
        "category": "l5_values",
        "text": (
            f"소비자 미니멀리즘 {persona_params.get('l5.minimalism', 3.0):.2f}/5, "
            f"친환경 가치 {persona_params.get('l5.green_values', 3.0):.2f}/5."
        ),
        "importance": 55,
    })

    dr = persona_params.get("l6.discount_rate_annual", 0.5)
    pb = persona_params.get("l6.present_bias_beta", 0.0)
    memories.append({
        "category": "l6_time",
        "text": (
            f"연간 할인율 {dr:.2f} — {'높은 미래 할인' if dr > 1.0 else '보통 시간 선호'}. "
            f"현재 편향 β={pb:.2f}, 성실성 {persona_params.get('l6.conscientiousness', 4)}/8."
        ),
        "importance": 60,
    })

    memories.append({
        "category": "ability",
        "text": (
            f"금융 이해력 {persona_params.get('ability.financial_literacy', 4)}/8, "
            f"수리 능력 {persona_params.get('ability.numeracy', 4)}/8."
        ),
        "importance": 50,
    })

    demo_text = (
        f"{demographics.get('age_range', '')} {demographics.get('gender', '')} | "
        f"{demographics.get('region', '')} | {demographics.get('employment', '')} | "
        f"월 가구소득 {demographics.get('household_income', '')} | "
        f"학력 {demographics.get('education', '')}"
    )
    memories.append({"category": "demographics", "text": demo_text.strip(), "importance": 40})

    if qualitative.get("self_aspire"):
        memories.append({"category": "self_aspire", "text": qualitative["self_aspire"], "importance": 80})
    if qualitative.get("self_ought"):
        memories.append({"category": "self_ought", "text": qualitative["self_ought"], "importance": 75})
    if qualitative.get("self_actual"):
        memories.append({"category": "self_actual", "text": qualitative["self_actual"], "importance": 85})

    return memories


# ── 카드 표시용 display_name / emoji / intro_ko 합성 ─────────────────────

_ARCHETYPE_EMOJI = {
    "frugal_planner": "💰",
    "trend_adopter": "🌟",
    "social_collectivist": "🤝",
    "minimalist_idealist": "🌱",
    "rational_analytic": "📊",
    "value_traditional": "🏛️",
}
_ARCHETYPE_LABEL = {
    "frugal_planner": "절약 계획형",
    "trend_adopter": "트렌드 추종형",
    "social_collectivist": "공동체 지향형",
    "minimalist_idealist": "미니멀 가치형",
    "rational_analytic": "합리 분석형",
    "value_traditional": "전통 가치형",
}


def derive_display(record: dict[str, Any], demographics: dict[str, Any]) -> tuple[str, str, str]:
    """카드용 (display_name, emoji, intro_ko) 도출."""
    archetype = record.get("archetype")
    age = demographics.get("age_range") or ""
    gender = demographics.get("gender") or ""
    job = demographics.get("employment") or ""
    label = _ARCHETYPE_LABEL.get(archetype or "", "응답자")
    name = f"{age} {gender} · {label}".strip()
    emoji = _ARCHETYPE_EMOJI.get(archetype or "", "👤")
    intro_bits = [b for b in [age, gender, job, label] if b]
    intro = " · ".join(intro_bits)
    return name, emoji, intro


# ── 단일 레코드 적재 ──────────────────────────────────────────────────────

EventCallback = Optional[Callable[[dict[str, Any]], Awaitable[None]]]


async def process_record(
    record: dict[str, Any],
    project_id: str,
    *,
    dry_run: bool = False,
    synthetic_embeddings: bool | None = None,
    on_event: EventCallback = None,
) -> dict[str, Any]:
    """단일 응답을 처리해 결과 요약 반환.

    Args:
        record: 응답 dict (responses/qualitative/demographics 포함).
        project_id: 적재 대상 프로젝트 UUID.
        dry_run: True 면 DB INSERT 없이 검증만.
        synthetic_embeddings: True=강제 합성, False=강제 API, None=자동.
        on_event: 비동기 콜백(dict) — NDJSON 스트림에 사용.
    """
    respondent_id = record.get("respondent_id", f"unknown_{uuid.uuid4().hex[:6]}")

    responses = validate_input(record)
    persona_params = score_all(responses)
    qualitative = extract_qualitative(record)
    demographics = extract_demographics(record)
    prompt = build_persona(persona_params, qualitative, demographics)
    token_count = count_tokens(prompt)

    memory_texts = build_memory_texts(persona_params, qualitative, demographics)
    display_name, emoji, intro_ko = derive_display(record, demographics)

    if on_event:
        await on_event({
            "type": "record_scored",
            "respondent_id": respondent_id,
            "token_count": token_count,
            "memory_count": len(memory_texts),
        })

    if dry_run:
        return {"respondent_id": respondent_id, "status": "dry-run", "token_count": token_count}

    # 임베딩 — 합성 모드는 즉시(blocking 0ms 수준), 실 API 는 외부 호출
    embeddings = [embed(m["text"], synthetic=synthetic_embeddings) for m in memory_texts]
    avg_emb = average_embedding(embeddings)

    agent_id = str(uuid.uuid4())
    scratch = {**demographics, **{k: v for k, v in qualitative.items() if isinstance(v, str)}}

    async with AsyncSessionLocal() as db:
        db.add(Agent(
            id=agent_id,
            project_id=project_id,
            source_type="twin",
            source_ref=respondent_id,
            display_name=display_name,
            emoji=emoji,
            intro_ko=intro_ko,
            persona_params=persona_params,
            persona_full_prompt=prompt,
            scratch=scratch,
            avg_embedding=avg_emb,
        ))
        await db.flush()

        for mem, emb in zip(memory_texts, embeddings):
            db.add(AgentMemory(
                agent_id=agent_id,
                source="base",
                category=mem["category"],
                text=mem["text"],
                importance=mem["importance"],
                embedding=emb,
            ))
        await db.commit()

    if on_event:
        await on_event({
            "type": "agent_created",
            "respondent_id": respondent_id,
            "agent_id": agent_id,
            "memory_count": len(memory_texts),
        })

    return {
        "respondent_id": respondent_id,
        "agent_id": agent_id,
        "display_name": display_name,
        "status": "ok",
        "memory_count": len(memory_texts),
    }


# ── KMeans 재클러스터링 ──────────────────────────────────────────────────

async def recluster_project(project_id: str, k: int = 5) -> int:
    """프로젝트 내 에이전트 avg_embedding 으로 KMeans 라벨 갱신.

    Returns: 클러스터 개수 (실제 사용). 에이전트 < 2 면 0 반환.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Agent.id, Agent.avg_embedding).where(Agent.project_id == project_id)
        )
        rows = result.all()
    if len(rows) < 2:
        return 0

    try:
        from sklearn.cluster import KMeans  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return 0

    agent_ids = [r[0] for r in rows]
    raw = [r[1] for r in rows]
    embeddings = []
    for e in raw:
        if isinstance(e, str):
            try:
                embeddings.append(json.loads(e))
            except json.JSONDecodeError:
                embeddings.append([0.0] * 1536)
        elif isinstance(e, list):
            embeddings.append(e)
        else:
            embeddings.append([0.0] * 1536)

    X = np.array(embeddings, dtype=np.float32)
    k_use = min(k, len(rows))
    km = KMeans(n_clusters=k_use, random_state=42, n_init=10)
    labels = km.fit_predict(X)

    async with AsyncSessionLocal() as db:
        for agent_id, label in zip(agent_ids, labels):
            await db.execute(
                update(Agent).where(Agent.id == agent_id).values(cluster=int(label))
            )
        await db.commit()
    return k_use
