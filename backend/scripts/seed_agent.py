"""seed_agent.py — Twin/Survey 응답을 DB에 적재하는 CLI.

사용법:
  python -m scripts.seed_agent \\
    --input tests/_fixtures/mock_twin_30.json \\
    --project-id <uuid> \\
    [--dry-run] [--limit N] [--synthetic-embeddings]

핵심 로직은 services/seed_service.py 가 보유 — CLI 와 라우터가 공유한다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import init_db
from services.seed_service import (
    build_memory_texts as _build_memory_texts,  # noqa: F401 — tests 호환
    process_record,
    recluster_project,
)


def _load_records(input_path: str) -> list[dict]:
    """JSON (list or dict) 또는 CSV 로드."""
    path = Path(input_path)
    if path.suffix.lower() == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return [data] if isinstance(data, dict) else data
    if path.suffix.lower() == ".csv":
        import csv
        with open(path, encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    raise ValueError(f"지원하지 않는 파일 형식: {path.suffix}")


# 테스트 호환용 wrapper — 신규 시그니처는 services/seed_service.process_record
async def _process_record(record, project_id, dry_run=False, refresh_prompt=False,
                          synthetic_embeddings: bool | None = None):
    """test_seed_agent.py 가 import 하는 레거시 alias."""
    return await process_record(
        record,
        project_id=project_id,
        dry_run=dry_run,
        synthetic_embeddings=synthetic_embeddings,
    )


async def main_async(args) -> None:
    await init_db()
    records = _load_records(args.input)
    if args.limit:
        records = records[: args.limit]

    print(f"[SEED] 총 {len(records)}건 처리 시작 (dry_run={args.dry_run})")
    ok = 0
    for record in records:
        result = await process_record(
            record,
            project_id=args.project_id or "00000000-0000-0000-0000-000000000000",
            dry_run=args.dry_run,
            synthetic_embeddings=args.synthetic_embeddings,
        )
        status = result.get("status")
        if status in ("ok", "dry-run"):
            ok += 1
            label = result.get("display_name") or result["respondent_id"]
            print(f"  [{status}] {label}")
        else:
            print(f"  [FAIL] {result['respondent_id']}")

    print(f"\n[SEED] 완료: {ok}/{len(records)} 성공")

    if not args.dry_run and args.project_id:
        k = await recluster_project(args.project_id, k=args.cluster_k)
        if k:
            print(f"[KMEANS] {len(records)}명 → {k} 클러스터 재배정 완료.")
        else:
            print("[KMEANS] 클러스터링 skip (sklearn 미설치 또는 에이전트 < 2).")


def main():
    parser = argparse.ArgumentParser(description="Ditto 에이전트 적재 CLI")
    parser.add_argument("--input", required=True, help="응답 파일 경로 (.json / .csv)")
    parser.add_argument("--project-id", default=None, help="ResearchProject UUID")
    parser.add_argument("--dry-run", action="store_true", help="DB INSERT 없이 검증만")
    parser.add_argument("--limit", type=int, default=None, help="처리할 최대 레코드 수")
    parser.add_argument("--cluster-k", type=int, default=5, help="KMeans K (기본 5)")
    parser.add_argument(
        "--synthetic-embeddings",
        action="store_true",
        help="OPENAI_API_KEY 없이 결정적 합성 임베딩 사용",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
