"""seed_demo.py — 데모 user/project + package 6명 복제 적재 CLI (plan 0008).

사용법:
  python -m scripts.seed_demo            # 멱등 시드 (이미 있으면 유지)
  python -m scripts.seed_demo --reset    # 데모 프로젝트 하위 데이터 초기화 후 재시드

핵심 로직은 services/demo_service.ensure_demo 가 보유 — 라우터(/api/demo/session)와 공유.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import AsyncSessionLocal, init_db
from services import demo_service


async def _run(reset: bool) -> None:
    await init_db()
    async with AsyncSessionLocal() as db:
        result = await demo_service.ensure_demo(db, reset=reset)
    print(f"✅ 데모 시드 완료")
    print(f"   user    : {result['user'].email} (id={demo_service.DEMO_USER_ID})")
    print(f"   project : {demo_service.DEMO_PROJECT_TITLE} (id={demo_service.DEMO_PROJECT_ID})")
    print(f"   agents  : {result['n_agents']}명 (원본 {demo_service.SOURCE_PROJECT_ID})")
    if result["n_agents"] == 0:
        print("   ⚠ 복제된 에이전트가 0명입니다. DEMO_SOURCE_PROJECT_ID 의 package 에이전트를 확인하세요.")


def main() -> None:
    parser = argparse.ArgumentParser(description="데모 시드 (user/project/agents)")
    parser.add_argument("--reset", action="store_true", help="데모 프로젝트 하위 데이터 초기화 후 재시드")
    args = parser.parse_args()
    asyncio.run(_run(args.reset))


if __name__ == "__main__":
    main()
