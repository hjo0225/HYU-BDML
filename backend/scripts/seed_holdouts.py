"""V1 hold-out 자극 답변(scratch.holdout_*)을 LLM으로 생성·적재.

배경:
- `import_agent_package.py` 로 적재된 package 에이전트는 `scratch` 에
  메타 필드만 채우고 `holdout_recent_purchase / info_source / lifestyle` 은
  누락 → V1 평가가 모두 skipped 처리되어 sync=0.0 으로 나옴.
- 데모/실 적재본을 깨끗하게 다시 import 하지 않고 in-place 백필.
- "이 페르소나라면 hold-out 질문에 어떻게 답할까?" 를 `persona_full_prompt`
  + `chat_completion` 으로 생성 → scratch 에 저장.

사용:
    # 로컬 SQLite (DATABASE_URL 미지정)
    python -m scripts.seed_holdouts --project-id 0de00000-0000-4000-8000-000000000002

    # Cloud SQL 운영 (cloud-sql-proxy + DATABASE_URL=postgresql+asyncpg://…)
    DATABASE_URL=… python -m scripts.seed_holdouts --project-id 61f78cf9-…

    # 모든 프로젝트 (관리자용)
    python -m scripts.seed_holdouts --all

    # 이미 채워진 값도 덮어쓰기
    python -m scripts.seed_holdouts --project-id … --force
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from database import Agent, AsyncSessionLocal
from evaluation.stimuli import V1_HOLDOUT_STIMULI
from services.llm_client import chat_completion


async def seed_one(db: AsyncSession, agent: Agent, *, force: bool, mock: bool | None) -> str:
    """한 에이전트의 hold-out 3문항 답변을 채운다.

    Returns: "seeded" | "skipped" | "no-prompt"
    """
    if not agent.persona_full_prompt:
        return "no-prompt"

    scratch = dict(agent.scratch or {})
    missing = [q for q in V1_HOLDOUT_STIMULI if not scratch.get(q.scratch_key)]
    if not missing and not force:
        return "skipped"

    targets = V1_HOLDOUT_STIMULI if force else missing
    for q in targets:
        ans = await chat_completion(
            system=agent.persona_full_prompt,
            user=q.question_ko,
            mock=mock,
        )
        scratch[q.scratch_key] = ans

    agent.scratch = scratch
    flag_modified(agent, "scratch")  # JSON 컬럼 mutation 강제 감지
    return "seeded"


async def run(project_id: str | None, *, all_projects: bool, force: bool, mock: bool | None) -> None:
    async with AsyncSessionLocal() as db:
        if all_projects:
            res = await db.execute(select(Agent).order_by(Agent.project_id, Agent.created_at))
        else:
            res = await db.execute(
                select(Agent).where(Agent.project_id == project_id).order_by(Agent.created_at)
            )
        agents = list(res.scalars().all())

        if not agents:
            print(f"no agents (project_id={project_id or 'ALL'})")
            return

        seeded = skipped = no_prompt = 0
        for a in agents:
            status = await seed_one(db, a, force=force, mock=mock)
            tag = {"seeded": "✓", "skipped": "·", "no-prompt": "!"}[status]
            print(f"  {tag} {a.project_id[:8]} {a.id[:8]} {a.display_name or '(no name)':<20} {status}")
            if status == "seeded":
                seeded += 1
            elif status == "skipped":
                skipped += 1
            else:
                no_prompt += 1

        await db.commit()

    print(
        f"\nprocessed {len(agents)} agents: "
        f"{seeded} seeded, {skipped} already had holdouts, {no_prompt} missing persona_full_prompt"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--project-id", help="이 프로젝트의 에이전트만 백필")
    grp.add_argument("--all", action="store_true", dest="all_projects", help="모든 프로젝트 백필 (관리자용)")
    ap.add_argument("--force", action="store_true", help="이미 채워진 holdout 도 덮어쓰기")
    ap.add_argument("--mock", action="store_true", help="LLM 호출 대신 결정적 mock (테스트용)")
    args = ap.parse_args()

    mock_flag: bool | None = True if args.mock else None
    asyncio.run(run(args.project_id, all_projects=args.all_projects, force=args.force, mock=mock_flag))


if __name__ == "__main__":
    main()
