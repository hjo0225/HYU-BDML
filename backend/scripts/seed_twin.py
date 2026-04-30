"""Twin-2K-500 (Toubia et al. 2025) → Cloud SQL 적재 (Lab 전용).

Hugging Face `LLM-Digital-Twin/Twin-2K-500` 데이터셋을 `full_persona` config로 받아
50명을 샘플링하여 `panels.source='twin2k500'`, `panel_memories.source='twin2k500'`로 적재.

데이터셋 출처:
  Toubia, O., Gui, G. Z., Peng, T., Merlau, D. J., Li, A., & Chen, H. (2025).
  Database Report: Twin-2K-500. Marketing Science, 44(6), 1446–1455.
  https://doi.org/10.1287/mksc.2025.0262
  https://huggingface.co/datasets/LLM-Digital-Twin/Twin-2K-500

데이터셋 스키마 (config="full_persona", split="data"):
  - pid              : 응답자 ID (str)
  - persona_text     : Q/A 평문 (영어, ~130k chars)
  - persona_summary  : 정형화된 인구통계 + 심리척도 + 정성응답 (영어, ~12-18k chars)
  - persona_json     : JSON 문자열 (영어, ~170k chars) — 본 적재에서는 사용하지 않음

본 스크립트는 `persona_summary`만 사용해 scratch + 메모리 카테고리(약 32개)를 만든다.

사전 조건:
  pip install datasets huggingface_hub
  환경변수: DATABASE_URL, OPENAI_API_KEY
  사전 마이그레이션: `python -m scripts.migrate_add_source` (1회)

실행:
  cd backend && python -m scripts.seed_twin
  # 샘플 수 변경: SEED_TWIN_LIMIT=100 python -m scripts.seed_twin
  # 시드 변경:    SEED_TWIN_SEED=7 python -m scripts.seed_twin
  # 스트리밍 모드 사용 (전체 다운로드 대신): SEED_TWIN_STREAM=1 ...

주의:
  - `embedding_cache.json`을 다른 스크립트가 동시에 쓰면 JSON 파싱 오류.
    `seed_panels`와 동시 실행 금지 (CLAUDE.md IMPORTANT).
"""
from __future__ import annotations

import asyncio
import itertools
import json
import os
import random

# .env를 database/openai 모듈 import 전에 로드 (DATABASE_URL, OPENAI_API_KEY).
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database import AsyncSessionLocal, Panel, PanelMemory
from rag.embedder import embed
from rag.twin_memory_builder import build_memories
from rag.twin_scratch_builder import build_scratch


HF_DATASET = "LLM-Digital-Twin/Twin-2K-500"
HF_CONFIG = "full_persona"
HF_SPLIT = "data"

DEFAULT_LIMIT = int(os.getenv("SEED_TWIN_LIMIT", "50"))
RNG_SEED = int(os.getenv("SEED_TWIN_SEED", "42"))
USE_STREAMING = os.getenv("SEED_TWIN_STREAM", "0") == "1"

# Twin 전용 클러스터 공간. FGI(0~N)와 겹치지 않도록 100부터 시작.
# K-means K=5 → 클러스터 ID 100~104. (Lab은 1:1 채팅이라 다양성 선정에 직접 쓰진 않지만,
# `panels.cluster`가 NOT NULL 이고 향후 다양성 샘플링 가능성을 위해 정상 클러스터를 부여.)
TWIN_CLUSTER_OFFSET = 100
TWIN_CLUSTER_K = int(os.getenv("SEED_TWIN_K", "5"))


def _twin_id(pid: str | int) -> str:
    """`panels.panel_id`(VARCHAR(20)) 안에 들어가도록 정규화."""
    s = str(pid).strip()
    return f"twin_{s}"[:20]


def _sample_rows(dataset, limit: int):
    """전체 다운로드 후 무작위 limit명 추출."""
    rng = random.Random(RNG_SEED)
    rows = list(dataset)
    if len(rows) <= limit:
        return rows
    return rng.sample(rows, limit)


def _stream_first(dataset, limit: int):
    """스트리밍 모드 — 데이터셋 앞쪽에서 limit명만 가져온다 (무작위 X)."""
    return list(itertools.islice(dataset, limit))


async def _save_one(idx: int, raw: dict) -> bool:
    """한 명을 panels + panel_memories에 적재. 이미 있으면 건너뜀."""
    pid = raw.get("pid")
    if pid is None:
        print(f"[seed_twin] idx={idx}: pid 없음 — 건너뜀")
        return False

    panel_id = _twin_id(pid)
    persona_summary = raw.get("persona_summary") or ""
    if not persona_summary.strip():
        print(f"[seed_twin] {panel_id}: persona_summary 비어 있음 — 건너뜀")
        return False

    async with AsyncSessionLocal() as session:
        existing = await session.execute(
            select(Panel).where(Panel.panel_id == panel_id)
        )
        if existing.scalar_one_or_none():
            return False

        scratch = build_scratch(str(pid), persona_summary)
        memories = build_memories(persona_summary)
        if not memories:
            print(f"[seed_twin] {panel_id}: 메모리 0개 — 스키마 변경 의심, 건너뜀")
            return False

        # 메모리 임베딩 (영어 원본 그대로)
        embeddings: list[list[float]] = []
        for _, text, _ in memories:
            try:
                embeddings.append(embed(text))
            except Exception as exc:  # noqa: BLE001
                print(f"[seed_twin] {panel_id}: 임베딩 실패 — {exc}")
                return False

        # avg_embedding (1차 스코어링용)
        if embeddings:
            dim = len(embeddings[0])
            avg = [sum(v[i] for v in embeddings) / len(embeddings) for i in range(dim)]
        else:
            avg = None

        # Panel 적재
        # 임시 placeholder cluster=TWIN_CLUSTER_OFFSET. 모든 50명 적재 후 K-means로
        # 100~(100+K-1) 범위로 재할당된다 (recluster_twin 단계).
        session.add(Panel(
            panel_id=panel_id,
            source="twin2k500",
            cluster=TWIN_CLUSTER_OFFSET,
            age=scratch.get("age"),
            gender=(scratch.get("gender") or "")[:10],
            occupation=(scratch.get("occupation") or "")[:50],
            region=(scratch.get("region") or "")[:50],
            scratch=json.dumps(scratch, ensure_ascii=False),
            avg_embedding=json.dumps(avg) if avg else None,
        ))

        # PanelMemory 적재
        for (cat, text, importance), emb in zip(memories, embeddings):
            session.add(PanelMemory(
                panel_id=panel_id,
                source="twin2k500",
                category=cat[:50],
                text=text,
                importance=importance,
                embedding=json.dumps(emb),
            ))

        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            print(f"[seed_twin] {panel_id}: 무결성 오류 — {exc}")
            return False

        print(
            f"[seed_twin] {panel_id} 적재 완료 — "
            f"메모리 {len(memories)}개 ({scratch.get('age_range')} "
            f"{scratch.get('gender')} {scratch.get('region')})"
        )
        return True


async def main() -> None:
    print(f"[seed_twin] HF 데이터셋: {HF_DATASET}")
    print(f"[seed_twin] config={HF_CONFIG} split={HF_SPLIT} 샘플 수={DEFAULT_LIMIT} 시드={RNG_SEED}")
    print(f"[seed_twin] 스트리밍={USE_STREAMING}")

    try:
        from datasets import load_dataset  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "[seed_twin] `datasets` 패키지가 필요합니다. "
            "`pip install datasets huggingface_hub` 후 재실행하세요."
        ) from exc

    if USE_STREAMING:
        ds = load_dataset(HF_DATASET, HF_CONFIG, split=HF_SPLIT, streaming=True)
        sample = _stream_first(ds, DEFAULT_LIMIT)
    else:
        ds = load_dataset(HF_DATASET, HF_CONFIG, split=HF_SPLIT)
        sample = _sample_rows(ds, DEFAULT_LIMIT)

    print(f"[seed_twin] 적재 대상 {len(sample)}명")

    saved = 0
    skipped = 0
    for i, row in enumerate(sample):
        if await _save_one(i, row):
            saved += 1
        else:
            skipped += 1

    print(f"[seed_twin] 완료 — 신규 {saved}명, 건너뜀 {skipped}명")

    await _recluster_twin()


async def _recluster_twin() -> None:
    """Twin 패널 전체에 K-means 클러스터링을 적용하여 100~(100+K-1) 범위로 재할당."""
    try:
        from sklearn.cluster import KMeans  # type: ignore
        import numpy as np
    except ImportError as exc:
        print(f"[seed_twin] recluster 스킵 — sklearn/numpy 없음: {exc}")
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Panel.panel_id, Panel.avg_embedding).where(Panel.source == "twin2k500")
        )
        rows = result.all()

    rows = [(pid, emb) for pid, emb in rows if emb]
    if len(rows) < TWIN_CLUSTER_K:
        print(f"[seed_twin] recluster 스킵 — Twin {len(rows)}명 < K={TWIN_CLUSTER_K}")
        return

    pids = [pid for pid, _ in rows]
    vectors = np.array([json.loads(emb) for _, emb in rows], dtype=np.float32)
    km = KMeans(n_clusters=TWIN_CLUSTER_K, random_state=RNG_SEED, n_init=10)
    labels = km.fit_predict(vectors)

    async with AsyncSessionLocal() as session:
        for pid, lbl in zip(pids, labels):
            await session.execute(
                Panel.__table__.update()
                .where(Panel.panel_id == pid)
                .values(cluster=int(TWIN_CLUSTER_OFFSET + lbl))
            )
        await session.commit()

    counts: dict[int, int] = {}
    for lbl in labels:
        cid = int(TWIN_CLUSTER_OFFSET + lbl)
        counts[cid] = counts.get(cid, 0) + 1
    print(f"[seed_twin] recluster 완료 — Twin {len(pids)}명 → 클러스터 {sorted(counts.items())}")


if __name__ == "__main__":
    asyncio.run(main())
