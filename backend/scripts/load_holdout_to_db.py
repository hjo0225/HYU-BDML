"""load_holdout_to_db.py — 로컬 홀드아웃 JSON 캐시를 DB(agents.scratch)에 적재.

배포(Cloud Run)는 파일시스템이 ephemeral 이라, run_holdout_eval 로 만든 로컬
data/holdout_eval/*.json 결과를 Cloud SQL 에 영구 저장해야 품질평가 탭이 채워진다.
이 스크립트는 **재계산 없이** 기존 JSON 을 읽어 agents.scratch['holdout_eval'] 에 upsert 한다.

매칭 키는 agent.id 가 아니라 **source_ref(pid)** 다 — 로컬 SQLite 의 agent.id 와
Cloud SQL 의 agent.id 가 서로 다르기 때문(데모 소스는 별도 적재됨). source_ref 는
원본 respondent(pid_001 등) 라 DB 간 안정적이다.

기본 동작:
  데모 소스 프로젝트(61f78cf9…)의 에이전트 1명/source_ref 에만 저장한다. 데모 복제본은
  라우터(get_agent_holdout)의 source_ref 폴백이 이 원본 결과를 공유하므로 충분하다.

사용법 (Cloud SQL Proxy 가 켜진 상태에서 DATABASE_URL 을 Cloud SQL 로 지정):
  # PowerShell 예시
  $env:DATABASE_URL = "postgresql+asyncpg://USER:PASS@127.0.0.1:5432/DBNAME"
  python -m scripts.load_holdout_to_db --dry-run        # 미리보기
  python -m scripts.load_holdout_to_db                  # 데모 소스 원본에 적재
  python -m scripts.load_holdout_to_db --all-matching   # source_ref 가 같은 모든 에이전트에 적재
  python -m scripts.load_holdout_to_db --cache-dir <path>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import Agent, AsyncSessionLocal, DATABASE_URL

_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "holdout_eval"
_DEMO_SOURCE_PROJECT_ID = "61f78cf9-8329-4c24-912a-bd3eeac5bba8"
_HOLDOUT_SCRATCH_KEY = "holdout_eval"


def _load_cache(cache_dir: Path) -> dict[str, dict]:
    """source_ref → result dict. 같은 source_ref 가 여러 파일이면 마지막 것."""
    by_ref: dict[str, dict] = {}
    for path in sorted(cache_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"  ⚠ 건너뜀 {path.name}: {e}")
            continue
        ref = data.get("agent_source_ref")
        if not ref:
            print(f"  ⚠ 건너뜀 {path.name}: agent_source_ref 없음")
            continue
        by_ref[ref] = data
    return by_ref


def _scratch_dict(agent: Agent) -> dict:
    if isinstance(agent.scratch, dict):
        return dict(agent.scratch)
    if isinstance(agent.scratch, str):
        try:
            parsed = json.loads(agent.scratch)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


async def _resolve_targets(
    db, source_refs: list[str], *, all_matching: bool, project_id: str | None
) -> list[Agent]:
    """저장 대상 에이전트 목록.

    all_matching=False (기본): demo-source 프로젝트(또는 project_id)에서 source_ref 당 1명.
    all_matching=True: source_ref 가 같은 모든 에이전트.
    """
    if all_matching:
        res = await db.execute(
            select(Agent).where(Agent.source_ref.in_(source_refs)).order_by(Agent.created_at.asc())
        )
        return list(res.scalars().all())

    target_project = project_id or _DEMO_SOURCE_PROJECT_ID
    res = await db.execute(
        select(Agent)
        .where(Agent.project_id == target_project, Agent.source_ref.in_(source_refs))
        .order_by(Agent.created_at.asc())
    )
    rows = list(res.scalars().all())
    # source_ref 당 1명(가장 먼저 적재된 원본)만 유지.
    seen: set[str] = set()
    picked: list[Agent] = []
    for a in rows:
        if a.source_ref in seen:
            continue
        seen.add(a.source_ref)
        picked.append(a)
    return picked


async def _run(args: argparse.Namespace) -> None:
    cache_dir = Path(args.cache_dir)
    if not cache_dir.exists():
        raise FileNotFoundError(f"--cache-dir 없음: {cache_dir}")

    by_ref = _load_cache(cache_dir)
    if not by_ref:
        print("적재할 JSON 결과 없음.")
        return

    is_pg = not DATABASE_URL.startswith("sqlite")
    print(f"DB: {'PostgreSQL/Cloud SQL' if is_pg else 'SQLite (로컬)'}")
    print(f"캐시: {cache_dir}  ({len(by_ref)} source_ref: {', '.join(sorted(by_ref))})")
    print(f"모드: {'all-matching' if args.all_matching else f'demo-source({args.project_id or _DEMO_SOURCE_PROJECT_ID[:8]}) 원본만'}")
    if args.dry_run:
        print("** DRY-RUN — DB 변경 없음 **")

    # init_db() 는 호출하지 않는다 — 이미 마이그레이션된 기존 DB(운영/로컬) 대상이라
    # 스키마 생성·마이그레이션이 불필요하고, 운영 DB 에 마이그레이션을 돌리면 위험하다.
    async with AsyncSessionLocal() as db:
        targets = await _resolve_targets(
            db, list(by_ref), all_matching=args.all_matching, project_id=args.project_id
        )
        if not targets:
            print("\n대상 에이전트를 DB 에서 찾지 못함. source_ref 매칭 실패 — "
                  "--all-matching 또는 --project-id 를 확인하세요.")
            return

        updated = 0
        for agent in targets:
            result = by_ref.get(agent.source_ref)
            if result is None:
                continue
            # 저장본은 대상 에이전트 기준으로 self-consistent 하게 id/이름 갱신.
            payload = {**result, "agent_id": agent.id}
            if agent.display_name:
                payload["agent_display_name"] = agent.display_name

            score = result.get("agreement_score")
            print(
                f"  · {agent.source_ref} → {agent.id[:8]} "
                f"({agent.display_name or '(이름없음)'}) 일치율 {score*100:.1f}%"
                if isinstance(score, (int, float)) else
                f"  · {agent.source_ref} → {agent.id[:8]}"
            )
            if args.dry_run:
                continue
            scratch = _scratch_dict(agent)
            scratch[_HOLDOUT_SCRATCH_KEY] = payload
            agent.scratch = scratch
            updated += 1

        if not args.dry_run:
            await db.commit()
            print(f"\n✅ {updated}개 에이전트의 scratch['holdout_eval'] 적재 완료.")
        else:
            print(f"\n(dry-run) {len(targets)}개 대상 — 실제 적재하려면 --dry-run 제거.")


def main() -> None:
    p = argparse.ArgumentParser(description="로컬 홀드아웃 JSON → DB(agents.scratch) 적재")
    p.add_argument("--cache-dir", default=str(_CACHE_DIR), help="홀드아웃 JSON 디렉터리")
    p.add_argument("--project-id", default=None,
                   help="원본 저장 대상 프로젝트 (기본: 데모 소스 61f78cf9…)")
    p.add_argument("--all-matching", action="store_true",
                   help="source_ref 가 같은 모든 에이전트에 저장 (복제본 포함)")
    p.add_argument("--dry-run", action="store_true", help="DB 변경 없이 미리보기")
    args = p.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
