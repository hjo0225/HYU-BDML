"""
seed_panels.py — CSV 패널 데이터를 DB에 적재하는 스크립트.

사용법:
    cd backend
    python -m scripts.seed_panels              # 전체 500명 (확인 없이 자동 적재)
    python -m scripts.seed_panels --limit 5    # 테스트용 5명
    python -m scripts.seed_panels --skip-embedding  # 임베딩 생략 (빠른 테스트)

특징:
    - 매 패널마다 즉시 commit → 중간에 끊겨도 적재된 데이터 유지
    - 중복 panel_id 자동 건너뜀 → 재실행 시 이어서 적재
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# backend 디렉토리를 sys.path에 추가
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import numpy as np
import pandas as pd
from sqlalchemy import text

from database import engine, AsyncSessionLocal, Base, Panel, PanelMemory
from rag.scratch_builder import build_scratch
from rag.memory_builder import build_all_memory_texts, attach_importance
from rag.embedder import embed

# 경로
CSV_PATH = BACKEND_DIR / "raw" / "fgi_500_panels.csv"
CODEBOOK_PATH = BACKEND_DIR / "rag" / "codebook_data.json"


def load_codebook() -> dict:
    with open(CODEBOOK_PATH, encoding="utf-8") as f:
        return json.load(f)


async def seed(
    limit: int | None = None,
    skip_embedding: bool = False,
    skip_importance: bool = True,
):
    """CSV → DB 적재 메인 로직."""

    # 테이블 생성
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        pass  # 이미 존재하면 무시
    print("[seed] 테이블 준비 완료")

    # CSV + codebook 로드
    df = pd.read_csv(CSV_PATH, low_memory=False)
    codebook = load_codebook()
    if limit:
        df = df.head(limit)
    total = len(df)
    print(f"[seed] CSV 로드: {total}명")

    # 기존 적재 현황 확인
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM panels"))
        existing = result.scalar() or 0

    if existing > 0:
        print(f"[seed] 기존 패널 {existing}개 존재 — 중복은 자동 건너뜁니다.")

    done_count = 0    # 이번 실행에서 새로 적재한 수
    skipped_count = 0  # 이미 존재해서 건너뛴 수

    for idx, (_, row_series) in enumerate(df.iterrows()):
        row = row_series.to_dict()
        panel_id = str(row.get("PANEL_ID", ""))
        if not panel_id:
            continue

        # 중복 체크
        async with AsyncSessionLocal() as session:
            exists = await session.execute(
                text("SELECT 1 FROM panels WHERE panel_id = :pid"),
                {"pid": panel_id},
            )
            if exists.scalar():
                skipped_count += 1
                print(f"  [{idx+1}/{total}] {panel_id} — 이미 존재, 건너뜀")
                continue

        # scratch 빌드
        scratch = build_scratch(row, codebook)

        # 메모리 빌드
        memories = build_all_memory_texts(row, codebook)
        if not skip_importance:
            memories = attach_importance(memories, no_importance=False)
        else:
            memories = attach_importance(memories, no_importance=True)

        # 임베딩 생성
        for mem in memories:
            if skip_embedding:
                mem["_embedding"] = [0.0] * 10
            else:
                try:
                    mem["_embedding"] = embed(mem["text"])
                except Exception as e:
                    print(f"    [경고] 임베딩 실패 ({mem['category']}): {e}")
                    mem["_embedding"] = [0.0] * 10

        # avg_embedding 계산 (유효한 임베딩만)
        valid_embs = [m["_embedding"] for m in memories if len(m["_embedding"]) > 100]
        avg_emb = np.mean(valid_embs, axis=0).tolist() if valid_embs else None

        # DB 적재 (1명 단위 commit)
        async with AsyncSessionLocal() as session:
            panel = Panel(
                panel_id=panel_id,
                cluster=int(float(row.get("cluster", 0))),
                age=scratch.get("age"),
                gender=scratch.get("gender"),
                occupation=scratch.get("occupation"),
                region=scratch.get("region"),
                dim_night_owl=row.get("dim_night_owl"),
                dim_gamer=row.get("dim_gamer"),
                dim_social_diner=row.get("dim_social_diner"),
                dim_drinker=row.get("dim_drinker"),
                dim_shopper=row.get("dim_shopper"),
                dim_health=row.get("dim_health"),
                dim_entertainment=row.get("dim_entertainment"),
                dim_weekend_oriented=row.get("dim_weekend_oriented"),
                scratch=json.dumps(scratch, ensure_ascii=False) if isinstance(scratch, dict) else scratch,
                avg_embedding=json.dumps(avg_emb) if avg_emb else None,
            )
            session.add(panel)

            for mem in memories:
                emb = mem.pop("_embedding")
                pm = PanelMemory(
                    panel_id=panel_id,
                    category=mem["category"],
                    text=mem["text"],
                    importance=mem.get("importance", 50),
                    embedding=json.dumps(emb) if isinstance(emb, list) else emb,
                )
                session.add(pm)

            await session.commit()

        done_count += 1
        print(f"  [{idx+1}/{total}] {panel_id} — scratch + {len(memories)}개 메모리 적재 ✓")

    print(f"\n[seed] 완료! 신규 {done_count}명 적재 / {skipped_count}명 건너뜀 / 전체 {existing + done_count}명")


def main():
    parser = argparse.ArgumentParser(description="CSV 패널 데이터를 DB에 적재")
    parser.add_argument("--limit", type=int, default=None, help="적재할 패널 수 제한 (테스트용)")
    parser.add_argument("--skip-embedding", action="store_true", help="임베딩 생략 (빠른 테스트)")
    parser.add_argument("--skip-importance", action="store_true", default=True, help="importance LLM 호출 생략")
    args = parser.parse_args()

    asyncio.run(seed(
        limit=args.limit,
        skip_embedding=args.skip_embedding,
        skip_importance=args.skip_importance,
    ))


if __name__ == "__main__":
    main()
