"""restore_persona_params.py — package 에이전트 persona_params LLM 복원 CLI (plan 0008 v2).

사용법:
  python -m scripts.restore_persona_params                 # persona_params NULL 인 package 전체
  python -m scripts.restore_persona_params --project <id>  # 특정 프로젝트만
  python -m scripts.restore_persona_params --force         # 이미 있어도 재복원

핵심 로직은 services/persona_param_restore.restore_params 가 보유.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:  # 서버와 동일하게 .env 로드 (OPENAI_API_KEY)
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from sqlalchemy import select

from database import Agent, AsyncSessionLocal, init_db
from services.persona_param_restore import restore_params


async def _run(project_id: str | None, force: bool) -> None:
    await init_db()
    async with AsyncSessionLocal() as db:
        q = select(Agent).where(Agent.source_type == "package")
        if project_id:
            q = q.where(Agent.project_id == project_id)
        agents = list((await db.execute(q)).scalars().all())
        done = 0
        for a in agents:
            if a.persona_params and not force:
                print(f"  skip (이미 있음): {a.display_name}")
                continue
            text = a.persona_full_prompt or ""
            params = await restore_params(text, seed=a.id)
            a.persona_params = params
            db.add(a)
            await db.commit()
            done += 1
            print(f"  복원: {a.display_name} — {len(params)}개 척도 (예: l2.maximization={params.get('l2.maximization')})")
        print(f"\n✅ {done}/{len(agents)}명 persona_params 복원 완료")


def main() -> None:
    p = argparse.ArgumentParser(description="package 에이전트 persona_params LLM 복원")
    p.add_argument("--project", default=None, help="특정 프로젝트 id 만")
    p.add_argument("--force", action="store_true", help="이미 있어도 재복원")
    args = p.parse_args()
    asyncio.run(_run(args.project, args.force))


if __name__ == "__main__":
    main()
