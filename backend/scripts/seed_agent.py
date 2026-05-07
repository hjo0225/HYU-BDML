"""seed_agent.py — Twin/Survey 응답 데이터를 DB에 적재하는 CLI.

사용법:
  python -m backend.scripts.seed_agent \\
    --input responses.json \\
    --project-id <uuid> \\
    [--dry-run] [--limit N] [--resume] [--refresh-prompt]

플로우:
  1. 입력 파일 로드 (JSON list 또는 단일 dict, CSV 지원)
  2. validate_input → 필수 키 확인
  3. score_all → persona_params dict
  4. build_persona → persona_full_prompt
  5. 메모리 텍스트 생성 + embed
  6. INSERT agents + agent_memories (dry-run 이면 skip)
  7. KMeans 재클러스터링
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import AsyncSessionLocal, Agent, AgentMemory, init_db
from lenses.parser import validate_input
from scoring.pipeline import score_all, extract_qualitative, extract_demographics
from persona.builder import build_persona
from persona.compressor import count_tokens


def _load_records(input_path: str) -> list[dict]:
    """JSON (list or dict) または CSV を読み込む。"""
    path = Path(input_path)
    if path.suffix.lower() == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return [data]
        return data
    elif path.suffix.lower() == ".csv":
        import csv
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            return list(reader)
    else:
        raise ValueError(f"지원하지 않는 파일 형식: {path.suffix}")


def _build_memory_texts(persona_params: dict, qualitative: dict, demographics: dict) -> list[dict]:
    """에이전트 메모리 텍스트 목록 생성.

    각 Lens 그룹별로 1개씩 + 정성 응답 3개 = 최소 9개 이상.
    """
    memories = []

    # L1 경제적 합리성
    ra = persona_params.get("l1.risk_aversion", 0.5)
    la = persona_params.get("l1.loss_aversion_lambda", 1.0)
    memories.append({
        "category": "l1_economic",
        "text": f"위험 회피 성향이 {ra:.2f}이며, 손실 회피 성향 λ={la:.2f}인 소비자입니다. "
                f"심적 회계 분리도 {persona_params.get('l1.mental_accounting', 0.5):.2f}, "
                f"구두쇠-낭비벽 지수 {persona_params.get('l1.tightwad_spendthrift', 13):.0f}/26.",
        "importance": 70,
    })

    # L2 의사결정 스타일
    max_scale = persona_params.get("l2.maximization", 3.0)
    nfc = persona_params.get("l2.need_for_cognition", 3.0)
    crt = persona_params.get("l2.crt_score", 0)
    memories.append({
        "category": "l2_decision",
        "text": f"극대화 성향 {max_scale:.2f}/5, 인지 욕구 {nfc:.2f}/5. "
                f"CRT 정답 {crt}/4 — {'숙고형' if crt >= 3 else '직관형'} 의사결정 스타일.",
        "importance": 65,
    })

    # L3 동기
    agency = persona_params.get("l3.agency", 5.0)
    communion = persona_params.get("l3.communion", 5.0)
    memories.append({
        "category": "l3_motivation",
        "text": f"자기지향 가치(Agency) {agency:.2f}/9, 타인지향 가치(Communion) {communion:.2f}/9. "
                f"조절초점 {persona_params.get('l3.regulatory_focus', 4.0):.2f}/7, "
                f"독특성 욕구 {persona_params.get('l3.need_for_uniqueness', 3.0):.2f}/5.",
        "importance": 65,
    })

    # L4 사회적 영향
    empathy = persona_params.get("l4.empathy", 3.0)
    sm = persona_params.get("l4.self_monitoring", 2.5)
    memories.append({
        "category": "l4_social",
        "text": f"공감 지수 {empathy:.2f}/5, 자기 감시 {sm:.2f}/5. "
                f"독재자 게임 기부 비율 {persona_params.get('l4.dictator_send_ratio', 0.4):.2f}. "
                f"수직집단주의 {persona_params.get('l4.vertical_collectivism', 3.0):.2f}/5.",
        "importance": 60,
    })

    # L5 가치
    memories.append({
        "category": "l5_values",
        "text": f"소비자 미니멀리즘 {persona_params.get('l5.minimalism', 3.0):.2f}/5, "
                f"친환경 가치 {persona_params.get('l5.green_values', 3.0):.2f}/5.",
        "importance": 55,
    })

    # L6 시간
    dr = persona_params.get("l6.discount_rate_annual", 0.5)
    pb = persona_params.get("l6.present_bias_beta", 0.0)
    memories.append({
        "category": "l6_time",
        "text": f"연간 할인율 {dr:.2f} — {'높은 미래 할인' if dr > 1.0 else '보통 시간 선호'}. "
                f"현재 편향 β={pb:.2f}, 성실성 {persona_params.get('l6.conscientiousness', 4)}/8.",
        "importance": 60,
    })

    # 능력치
    fl = persona_params.get("ability.financial_literacy", 4)
    nm = persona_params.get("ability.numeracy", 4)
    memories.append({
        "category": "ability",
        "text": f"금융 이해력 {fl}/8, 수리 능력 {nm}/8.",
        "importance": 50,
    })

    # 인구통계
    demo_text = (
        f"{demographics.get('age_range', '')} {demographics.get('gender', '')} | "
        f"{demographics.get('region', '')} | {demographics.get('employment', '')} | "
        f"월 가구소득 {demographics.get('household_income', '')} | "
        f"학력 {demographics.get('education', '')}"
    )
    memories.append({
        "category": "demographics",
        "text": demo_text.strip(),
        "importance": 40,
    })

    # 정성 응답
    if qualitative.get("self_aspire"):
        memories.append({"category": "self_aspire", "text": qualitative["self_aspire"], "importance": 80})
    if qualitative.get("self_ought"):
        memories.append({"category": "self_ought", "text": qualitative["self_ought"], "importance": 75})
    if qualitative.get("self_actual"):
        memories.append({"category": "self_actual", "text": qualitative["self_actual"], "importance": 85})

    return memories


async def _process_record(
    record: dict,
    project_id: str,
    dry_run: bool,
    refresh_prompt: bool,
) -> dict:
    """단일 응답 레코드를 처리해 결과 요약 반환."""
    respondent_id = record.get("respondent_id", f"unknown_{uuid.uuid4().hex[:6]}")
    print(f"\n[SEED] 처리 중: {respondent_id}")

    responses = validate_input(record)
    persona_params = score_all(responses)
    qualitative = extract_qualitative(record)
    demographics = extract_demographics(record)

    prompt = build_persona(persona_params, qualitative, demographics)
    token_count = count_tokens(prompt)
    print(f"  → persona_full_prompt: {token_count} tokens")

    memory_texts = _build_memory_texts(persona_params, qualitative, demographics)
    print(f"  → 메모리 {len(memory_texts)}개 생성")

    # 9 그룹 수치 가이드 출력 (dry-run 용)
    print(f"  → L1 risk_aversion={persona_params.get('l1.risk_aversion', 0):.3f}")
    print(f"  → L2 maximization={persona_params.get('l2.maximization', 0):.3f}")
    print(f"  → L3 agency={persona_params.get('l3.agency', 0):.3f}")
    print(f"  → L4 empathy={persona_params.get('l4.empathy', 0):.3f}")
    print(f"  → L5 minimalism={persona_params.get('l5.minimalism', 0):.3f}")
    print(f"  → L6 discount_rate={persona_params.get('l6.discount_rate_annual', 0):.3f}")
    print(f"  → Ability FL={persona_params.get('ability.financial_literacy', 0)} NM={persona_params.get('ability.numeracy', 0)}")
    print(f"  → Demographics: {demographics.get('gender')} / {demographics.get('age_range')}")
    print(f"  → Qualitative: self_actual length={len(qualitative.get('self_actual', ''))}")

    if dry_run:
        print(f"  [DRY-RUN] DB INSERT skip.")
        return {"respondent_id": respondent_id, "status": "dry-run", "token_count": token_count}

    # 실제 임베딩 + DB INSERT
    from embedding.embedder import embed, average_embedding

    embeddings = []
    for mem in memory_texts:
        emb = embed(mem["text"])
        mem["embedding"] = emb
        embeddings.append(emb)

    avg_emb = average_embedding(embeddings)

    agent_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        agent = Agent(
            id=agent_id,
            project_id=project_id,
            source_type="twin",
            source_ref=respondent_id,
            persona_params=persona_params,
            persona_full_prompt=prompt,
            avg_embedding=avg_emb,
        )
        db.add(agent)
        await db.flush()

        for mem in memory_texts:
            db.add(AgentMemory(
                agent_id=agent_id,
                source="base",
                category=mem["category"],
                text=mem["text"],
                importance=mem["importance"],
                embedding=mem["embedding"],
            ))
        await db.commit()

    print(f"  [DB] agents 1행 + agent_memories {len(memory_texts)}행 INSERT 완료.")
    return {"respondent_id": respondent_id, "agent_id": agent_id, "status": "ok", "memory_count": len(memory_texts)}


async def _run_kmeans(project_id: str) -> None:
    """INSERT 완료 후 프로젝트 내 에이전트 KMeans 재클러스터링."""
    from sqlalchemy import select, update
    import json

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Agent.id, Agent.avg_embedding)
            .where(Agent.project_id == project_id)
        )
        rows = result.all()

    if len(rows) < 2:
        print("[KMEANS] 에이전트 2개 미만 — 클러스터링 skip.")
        return

    try:
        from sklearn.cluster import KMeans
        import numpy as np

        agent_ids = [r[0] for r in rows]
        emb_raw = [r[1] for r in rows]
        # SQLite → str, PostgreSQL → list
        embeddings = []
        for e in emb_raw:
            if isinstance(e, str):
                embeddings.append(json.loads(e))
            else:
                embeddings.append(e)

        X = np.array(embeddings, dtype=np.float32)
        k = min(5, len(rows))
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X)

        async with AsyncSessionLocal() as db:
            for agent_id, label in zip(agent_ids, labels):
                await db.execute(
                    update(Agent).where(Agent.id == agent_id).values(cluster=int(label))
                )
            await db.commit()
        print(f"[KMEANS] {len(rows)}명 → {k} 클러스터 재배정 완료.")
    except ImportError:
        print("[KMEANS] scikit-learn 없음 — 클러스터링 skip.")


async def main_async(args) -> None:
    await init_db()

    records = _load_records(args.input)
    if args.limit:
        records = records[: args.limit]

    print(f"[SEED] 총 {len(records)}건 처리 시작 (dry_run={args.dry_run})")
    results = []
    for record in records:
        result = await _process_record(
            record,
            project_id=args.project_id or "00000000-0000-0000-0000-000000000000",
            dry_run=args.dry_run,
            refresh_prompt=args.refresh_prompt,
        )
        results.append(result)

    ok = sum(1 for r in results if r.get("status") in ("ok", "dry-run"))
    print(f"\n[SEED] 완료: {ok}/{len(results)} 성공")

    if not args.dry_run and args.project_id:
        await _run_kmeans(args.project_id)


def main():
    parser = argparse.ArgumentParser(description="Ditto 에이전트 적재 CLI")
    parser.add_argument("--input", required=True, help="응답 파일 경로 (.json / .csv)")
    parser.add_argument("--project-id", default=None, help="ResearchProject UUID")
    parser.add_argument("--dry-run", action="store_true", help="DB INSERT 없이 검증만")
    parser.add_argument("--limit", type=int, default=None, help="처리할 최대 레코드 수")
    parser.add_argument("--resume", action="store_true", help="이미 처리된 respondent_id 건너뜀 (미구현)")
    parser.add_argument("--refresh-prompt", action="store_true", help="기존 agents의 persona_full_prompt 재생성")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
