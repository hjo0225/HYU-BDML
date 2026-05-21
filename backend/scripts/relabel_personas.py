"""relabel_personas.py — package 페르소나 라벨 교체 (plan 0010).

기존 DB 의 source_type='package' 에이전트(원본 + 데모 복제본 모두)에 대해:
  - display_name: "20대 여성 · 페르소나 01" → "20대 여성 · 김서연" (가명)
  - intro_ko: "(Twin-2K-500 + 6-Lens reflection)" 문구 제거

display_name 의 "페르소나 NN" 패턴으로 성별·번호를 파싱해 결정적으로 가명을 배정한다.
이미 가명으로 바뀐 행("페르소나" 미포함)은 건너뛰어 멱등하다.

사용법:
  python -m scripts.relabel_personas            # 적용
  python -m scripts.relabel_personas --dry-run  # 미리보기
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import Agent, AsyncSessionLocal, init_db
from scripts.import_agent_package import pick_pseudonym

_PERSONA_RE = re.compile(r"페르소나\s*(\d+)")


def _relabel(display_name: str) -> tuple[str, str] | None:
    """현재 display_name → (이름만 표시되는 새 display_name, 새 intro_ko). 대상 아니면 None.

    두 형식을 모두 처리하고 멱등하다.
      - "20대 여성 · 페르소나 001"  → 가명 결정 배정
      - "20대 여성 · 김서연"        → 기존 가명 유지(이름만 남김)
      - "김서연" (이미 이름만)      → None (건너뜀)
    """
    name = display_name or ""
    if "·" not in name:
        return None  # 이미 이름만 표시 → 건너뜀
    left, _, right = name.partition("·")
    label = left.strip()        # 예: "20대 여성"
    right = right.strip()       # "페르소나 001" 또는 "김서연"
    m = _PERSONA_RE.search(right)
    if m:
        gender = "남" if "남" in label else ("여" if "여" in label else "")
        pseudonym = pick_pseudonym(gender, int(m.group(1)))
    else:
        pseudonym = right       # 이미 가명 → 그대로 사용
    new_intro = f"{label} 인터뷰 기반 페르소나" if label and label != "응답자" else "인터뷰 기반 페르소나"
    return pseudonym, new_intro


async def _run(dry_run: bool) -> None:
    await init_db()
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(Agent).where(Agent.source_type == "package").order_by(Agent.created_at.asc())
        )).scalars().all()
        changed = 0
        for a in rows:
            res = _relabel(a.display_name or "")
            if res is None:
                continue
            new_display, new_intro = res
            print(f"  {a.id[:8]}  {a.display_name!r} → {new_display!r}")
            if not dry_run:
                a.display_name = new_display
                a.intro_ko = new_intro
            changed += 1
        if not dry_run:
            await db.commit()
        print(f"\n{'[dry-run] ' if dry_run else ''}대상 {len(rows)}명 중 {changed}명 라벨 교체"
              f"{' (미적용)' if dry_run else ' 완료'}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="package 페르소나 가명 라벨 교체")
    parser.add_argument("--dry-run", action="store_true", help="변경 없이 미리보기")
    args = parser.parse_args()
    asyncio.run(_run(args.dry_run))


if __name__ == "__main__":
    main()
