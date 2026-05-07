"""Lab Faithfulness — 카테고리별 한국어 probe 질문 생성/캐시.

각 트윈(`Panel.source='twin2k500'`)의 `PanelMemory` 카테고리마다, 그 카테고리의
응답을 자연스럽게 끌어낼 한국어 메신저 질문 1개를 LLM(gpt-4o-mini)으로 생성하여
`Panel.scratch.probe_questions = {category: question_ko}`에 캐시한다.

이 캐시는 `eval_lab_faithfulness.py`가 트윈에 던질 질문으로 사용된다.
값이 카테고리별 1문항이라 상대적으로 안정적이며, 한 번 생성하면 모델/프롬프트
변경 시까지 재사용할 수 있다.

실행:
  cd backend && python -m scripts.seed_lab_probe_questions
  # 일부 트윈만:   python -m scripts.seed_lab_probe_questions --limit 5
  # 강제 재생성:  python -m scripts.seed_lab_probe_questions --force
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import select

import services.openai_client  # noqa: F401
from database import AsyncSessionLocal, Panel, PanelMemory


_PROBE_MODEL = os.getenv("LAB_PROBE_MODEL", "gpt-4o-mini")
_llm = ChatOpenAI(model=_PROBE_MODEL, temperature=0.4)

# 너무 짧은 메모리는 의미 있는 probe를 만들기 어려움
_MIN_TEXT_CHARS = 50
# probe로 만들 가치가 별로 없는 메타 카테고리 (선택 — 필요 시 조정)
_SKIP_CATEGORIES: set[str] = set()


_PROBE_SYSTEM = """You are a Korean conversational researcher. \
For each English persona-memory snippet, write ONE casual Korean messenger-style \
question that would naturally invite the respondent to reveal the same information \
or attitude described in the snippet.

Output rules:
- Output exactly one Korean sentence. No prefixes, no quotes, no English.
- 친근한 메신저 어투. 너무 격식 차리지 말 것. 12~30자 이내.
- 절대 영어 단서를 그대로 노출하지 말 것 (예: 'Big5', 'CRT', 'G.R.E.E.N' 같은 검사 명칭).
- 너무 직접적인 추궁("당신은 외향적입니까?")보다 일상 대화처럼.
"""


def _build_user_prompt(category: str, snippet: str) -> str:
    return (
        f"[카테고리]\n{category}\n\n"
        f"[페르소나 메모리 발췌(영어)]\n{snippet[:1200]}\n\n"
        "위 메모리의 핵심을 자연스럽게 끌어낼 한국어 메신저 질문 1개를 출력하세요."
    )


def _normalize_question(text: str) -> str:
    text = (text or "").strip()
    # 따옴표/마크다운 제거
    text = text.strip("`")
    text = re.sub(r'^[\'"“”‘’]+|[\'"“”‘’]+$', "", text).strip()
    # 줄바꿈 첫 줄만
    text = text.split("\n")[0].strip()
    # 너무 길면 잘라냄
    if len(text) > 80:
        text = text[:79].rstrip() + "?"
    return text


async def _generate_probe(category: str, snippet: str) -> str | None:
    try:
        result = await _llm.ainvoke([
            SystemMessage(content=_PROBE_SYSTEM),
            HumanMessage(content=_build_user_prompt(category, snippet)),
        ])
        raw = result.content if hasattr(result, "content") else str(result)
        q = _normalize_question(str(raw))
        return q or None
    except Exception as exc:  # noqa: BLE001
        print(f"  ! probe 생성 실패 ({category}): {exc}")
        return None


async def _process_twin(panel_id: str, force: bool) -> tuple[int, int]:
    """반환: (생성된 probe 수, 스킵된 수)."""
    async with AsyncSessionLocal() as session:
        # 패널 + 메모리 로드
        panel = (await session.execute(
            select(Panel).where(
                Panel.panel_id == panel_id,
                Panel.source == "twin2k500",
            )
        )).scalar_one_or_none()
        if not panel:
            print(f"  - {panel_id}: 패널 없음 (skip)")
            return 0, 0

        memories = (await session.execute(
            select(PanelMemory).where(
                PanelMemory.panel_id == panel_id,
                PanelMemory.source == "twin2k500",
            )
        )).scalars().all()

        scratch = panel.scratch
        if isinstance(scratch, str):
            scratch = json.loads(scratch)
        scratch = scratch or {}
        existing: dict[str, str] = scratch.get("probe_questions") or {}
        if not isinstance(existing, dict):
            existing = {}

        added = 0
        skipped = 0
        for mem in memories:
            cat = mem.category
            if cat in _SKIP_CATEGORIES:
                skipped += 1
                continue
            text = (mem.text or "").strip()
            if len(text) < _MIN_TEXT_CHARS:
                skipped += 1
                continue
            if not force and cat in existing and existing[cat]:
                continue
            q = await _generate_probe(cat, text)
            if not q:
                skipped += 1
                continue
            existing[cat] = q
            added += 1

        if added > 0 or force:
            scratch["probe_questions"] = existing
            panel.scratch = scratch
            await session.commit()

    return added, skipped


async def _main(limit: int | None, force: bool) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Panel.panel_id).where(Panel.source == "twin2k500")
        )
        all_ids = [r[0] for r in result.all()]
    if limit:
        all_ids = all_ids[:limit]

    print(f"[probe] Twin {len(all_ids)}명 대상 생성 시작 (force={force})")
    total_added = 0
    total_skipped = 0
    for i, pid in enumerate(all_ids, 1):
        print(f"[{i}/{len(all_ids)}] {pid}")
        added, skipped = await _process_twin(pid, force)
        total_added += added
        total_skipped += skipped
        print(f"   + {added} added, {skipped} skipped")
    print(f"[probe] 완료. 총 added={total_added}, skipped={total_skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="처리할 트윈 수 제한")
    parser.add_argument("--force", action="store_true", help="기존 캐시 덮어쓰기")
    args = parser.parse_args()
    asyncio.run(_main(args.limit, args.force))
