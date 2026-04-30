"""Twin-2K-500 풀-프롬프트(Toubia 방식) 백필 스크립트.

`panels.persona_full` 컬럼을 추가하고, 이미 적재된 twin2k500 패널의 persona_json
원본 텍스트를 채워 넣는다. Lab 채팅에서 RAG 없이 풀-프롬프트로 주입된다.

사전 조건:
  pip install datasets huggingface_hub
  환경변수 DATABASE_URL, OPENAI_API_KEY (.env)
  seed_twin.py로 50명 적재 완료 상태

실행:
  cd backend && python -m scripts.seed_twin_persona_full
"""
from __future__ import annotations

import asyncio
import itertools
import json
import os

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass

from sqlalchemy import select, text

from database import AsyncSessionLocal, Panel, engine, DATABASE_URL


HF_DATASET = "LLM-Digital-Twin/Twin-2K-500"
HF_CONFIG = "full_persona"
HF_SPLIT = "data"

IS_SQLITE = DATABASE_URL.startswith("sqlite")


async def _ensure_column() -> None:
    """`panels.persona_full TEXT` 컬럼이 없으면 추가 (멱등)."""
    async with engine.begin() as conn:
        if IS_SQLITE:
            rows = (await conn.execute(text("PRAGMA table_info(panels)"))).fetchall()
            existing = {r[1] for r in rows}
        else:
            r = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='panels'"
            ))
            existing = {row[0] for row in r}

        if "persona_full" in existing:
            print("[migrate] panels.persona_full 이미 존재 — 건너뜀")
            return

        print("[migrate] panels.persona_full TEXT 추가 중...")
        await conn.execute(text("ALTER TABLE panels ADD COLUMN persona_full TEXT"))
        print("[migrate] 추가 완료")


def _twin_panel_id(pid: str | int) -> str:
    s = str(pid).strip()
    return f"twin_{s}"[:20]


async def _existing_panel_ids() -> set[str]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Panel.panel_id).where(Panel.source == "twin2k500")
        )
        return {row[0] for row in result.all()}


async def _missing_persona_ids() -> set[str]:
    """persona_full이 비어있는(NULL/빈문자열) twin2k500 panel_id 집합."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Panel.panel_id).where(
                Panel.source == "twin2k500",
                (Panel.persona_full.is_(None)) | (Panel.persona_full == ""),
            )
        )
        return {row[0] for row in result.all()}


async def main() -> None:
    await _ensure_column()

    target_ids = await _existing_panel_ids()
    if not target_ids:
        print("[backfill] twin2k500 패널이 없습니다. 먼저 seed_twin.py를 실행하세요.")
        return

    missing = await _missing_persona_ids()
    print(f"[backfill] 적재된 twin {len(target_ids)}명 중 persona_full 없는 {len(missing)}명")
    if not missing:
        print("[backfill] 모두 채워져 있습니다 — 종료.")
        return

    try:
        from datasets import load_dataset  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "[backfill] `datasets` 패키지가 필요합니다. "
            "`pip install datasets huggingface_hub` 후 재실행."
        ) from exc

    # 스트리밍 모드 — pid를 보면서 우리가 가진 50명을 만나면 persona_json 추출
    print("[backfill] HF 스트리밍 시작...")
    ds = load_dataset(HF_DATASET, HF_CONFIG, split=HF_SPLIT, streaming=True)

    found: dict[str, str] = {}  # panel_id → persona_json 원본
    scanned = 0
    for row in ds:
        scanned += 1
        pid = row.get("pid")
        if pid is None:
            continue
        pid_str = _twin_panel_id(pid)
        if pid_str in missing and pid_str not in found:
            persona_json = row.get("persona_json") or ""
            if persona_json:
                found[pid_str] = persona_json
        if len(found) >= len(missing):
            break
        if scanned % 200 == 0:
            print(f"[backfill] 스캔 {scanned}건 — 발견 {len(found)}/{len(missing)}")

    print(f"[backfill] HF 스캔 완료 ({scanned}건) — 매칭 {len(found)}/{len(missing)}")
    if not found:
        print("[backfill] 매칭된 응답자가 없습니다. SEED_TWIN_STREAM 시드와 일치하는지 확인.")
        return

    # DB UPDATE — persona_full 채우기
    async with AsyncSessionLocal() as session:
        saved = 0
        for panel_id, persona_text in found.items():
            await session.execute(
                Panel.__table__.update()
                .where(Panel.panel_id == panel_id)
                .values(persona_full=persona_text)
            )
            saved += 1
            if saved % 10 == 0:
                print(f"[backfill] 저장 {saved}/{len(found)}")
        await session.commit()

    print(f"[backfill] 완료 — {saved}명 persona_full 채워짐")
    if len(found) < len(missing):
        gap = sorted(missing - set(found.keys()))[:5]
        print(f"[backfill] 채우지 못한 {len(missing) - len(found)}명 (예: {gap})")


if __name__ == "__main__":
    asyncio.run(main())
