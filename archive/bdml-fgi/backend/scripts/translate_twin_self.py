"""Twin-2K-500 패널의 `aspire` / `actual` 정성응답을 한국어로 번역하여 scratch에 저장.

본 스크립트는 1회성 후처리 (seed_twin 이후). 50명의 짧은 자기인식 응답
(예: "loving at all times", "caring, respectful, fair")을 한 번의 LLM 호출로
모두 번역하여 `scratch.aspire_ko` / `scratch.actual_ko` 필드에 저장한다.

사전 조건:
  환경변수 DATABASE_URL, OPENAI_API_KEY
  seed_twin이 먼저 실행돼서 twin2k500 50명이 적재돼 있어야 한다.

실행:
  cd backend && python -m scripts.translate_twin_self
"""
from __future__ import annotations

import asyncio
import json

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass

from sqlalchemy import select

from database import AsyncSessionLocal, Panel


SYSTEM_PROMPT = (
    "당신은 영어→한국어 번역가입니다. "
    "입력은 사람이 자기 자신을 묘사한 짧은 영어 문구입니다 "
    "(예: 'loving at all times', 'caring, respectful, fair', "
    "'more decisive and energetic'). "
    "각 항목을 자연스러운 한국어 1인칭 형용사/명사구로 번역하세요. "
    "톤은 짧고 진솔하게, 어색한 직역을 피합니다. "
    "완전한 문장이 아니라 형용구·키워드 형태로 유지합니다 "
    "(예: 'loving at all times' → '언제나 사랑이 많은 사람'). "
    "결과는 반드시 JSON 형식으로만 응답하세요. "
    "각 키는 입력의 id이고 값은 한국어 번역입니다."
)


def _build_user_prompt(items: list[dict]) -> str:
    """items: [{id, text}, ...] → JSON 문자열로 LLM에 전달."""
    payload = {"items": items}
    return (
        f"다음 {len(items)}개 영어 자기인식 문구를 한국어로 번역하세요.\n"
        f"입력 JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        f"출력 JSON 형식: {{\"translations\": {{\"id1\": \"한국어1\", \"id2\": \"한국어2\", ...}}}}"
    )


def _translate_batch(items: list[dict]) -> dict[str, str]:
    """모든 문구를 한 번의 호출로 번역. 출력 키는 입력 id와 일치."""
    if not items:
        return {}

    from openai import OpenAI
    client = OpenAI()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(items)},
        ],
    )
    raw = response.choices[0].message.content or "{}"
    parsed = json.loads(raw)
    return parsed.get("translations") or parsed  # 모델이 단순 dict로 답해도 허용


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Panel).where(Panel.source == "twin2k500")
        )
        panels = result.scalars().all()

    print(f"[translate] 대상 패널: {len(panels)}명")

    items: list[dict] = []
    panel_scratch: dict[str, dict] = {}
    for p in panels:
        scratch = p.scratch
        if isinstance(scratch, str):
            scratch = json.loads(scratch)
        scratch = scratch or {}
        panel_scratch[p.panel_id] = scratch
        if scratch.get("aspire") and not scratch.get("aspire_ko"):
            items.append({"id": f"{p.panel_id}:aspire", "text": scratch["aspire"]})
        if scratch.get("actual") and not scratch.get("actual_ko"):
            items.append({"id": f"{p.panel_id}:actual", "text": scratch["actual"]})
        # ought도 함께 번역해두면 추후 활용 가능
        if scratch.get("ought") and not scratch.get("ought_ko"):
            items.append({"id": f"{p.panel_id}:ought", "text": scratch["ought"]})

    if not items:
        print("[translate] 번역할 항목이 없습니다 (이미 모두 번역됨).")
        return

    print(f"[translate] LLM 호출 중 — 항목 {len(items)}개 (예상 비용 ~$0.001)")
    translations = _translate_batch(items)
    print(f"[translate] 번역 완료 — 결과 키 {len(translations)}개")

    # 결과를 panel_id별로 묶어 scratch에 머지
    updates: dict[str, dict] = {}
    for key, ko in translations.items():
        if ":" not in key:
            continue
        panel_id, field = key.split(":", 1)
        if panel_id not in panel_scratch:
            continue
        slot = updates.setdefault(panel_id, {})
        slot[f"{field}_ko"] = ko.strip()

    # DB 업데이트 — scratch JSON에 *_ko 필드 추가
    async with AsyncSessionLocal() as session:
        saved = 0
        for panel_id, ko_fields in updates.items():
            scratch = panel_scratch[panel_id]
            scratch.update(ko_fields)
            await session.execute(
                Panel.__table__.update()
                .where(Panel.panel_id == panel_id)
                .values(scratch=json.dumps(scratch, ensure_ascii=False))
            )
            saved += 1
        await session.commit()

    print(f"[translate] DB 업데이트 완료 — {saved}명")


if __name__ == "__main__":
    asyncio.run(main())
