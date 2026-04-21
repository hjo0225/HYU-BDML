"""
compute_avg_embeddings.py — 기존 패널의 avg_embedding을 계산하여 저장.
메모리 임베딩의 원소별 평균을 panels.avg_embedding에 저장한다.
OpenAI 호출 없음 (이미 있는 임베딩의 평균만 계산).

사용법:
    cd backend
    python -m scripts.compute_avg_embeddings
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# 환경변수는 시스템 환경변수에서만 읽는다 (OPENAI_API_KEY, DATABASE_URL 등).

from sqlalchemy import text
from database import engine, AsyncSessionLocal, Base


async def main():
    # avg_embedding 컬럼이 없으면 추가
    async with engine.begin() as conn:
        try:
            await conn.execute(text(
                "ALTER TABLE panels ADD COLUMN IF NOT EXISTS avg_embedding JSONB"
            ))
        except Exception:
            pass  # SQLite 등에서는 무시

    # 전체 패널 ID 조회
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT panel_id FROM panels"))
        panel_ids = [r[0] for r in result.fetchall()]

    total = len(panel_ids)
    print(f"[avg_emb] 패널 {total}명 처리 시작...", flush=True)

    done = 0
    for pid in panel_ids:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text(
                "SELECT embedding FROM panel_memories WHERE panel_id = :pid"
            ), {"pid": pid})
            rows = result.fetchall()

            embeddings = []
            for r in rows:
                emb = r[0]
                if isinstance(emb, str):
                    emb = json.loads(emb)
                if isinstance(emb, list) and len(emb) > 100:
                    embeddings.append(emb)

            if not embeddings:
                done += 1
                continue

            avg = np.mean(embeddings, axis=0).tolist()
            await session.execute(
                text("UPDATE panels SET avg_embedding = :emb WHERE panel_id = :pid"),
                {"emb": json.dumps(avg), "pid": pid},
            )
            await session.commit()

        done += 1
        if done % 100 == 0:
            print(f"  [{done}/{total}] 진행 중...", flush=True)

    print(f"\n[avg_emb] 완료! {done}명 처리", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
