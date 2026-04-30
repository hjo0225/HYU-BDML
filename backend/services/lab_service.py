"""실험실(Lab) — Twin-2K-500 1:1 메신저 서비스 (Toubia 풀-프롬프트 방식).

Toubia et al. (2025) 논문 방식을 그대로 채택 — 응답자의 persona_json 원본 텍스트
(~170k chars, ~42k tokens)를 매 턴 시스템 프롬프트에 통째로 주입한다. RAG 검색 없음.

핵심:
- 페르소나 로딩: panels.persona_full을 그대로 읽어 in-memory 캐시.
- 발화 LLM 프롬프트: 풀 persona_full + 한국어 응답 지시.
- 비용 주의: 매 턴 ~42k 입력 토큰 — gpt-4o-mini 기준 약 $0.0075/턴.
  논문 재현(paper-fidelity)이 필요하면 LAB_LLM_MODEL=gpt-4o로 전환 (~$0.21/턴).
"""
from __future__ import annotations

import json
import os
from typing import AsyncGenerator

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import select

import services.openai_client  # noqa: F401  (환경변수 로드)
from database import AsyncSessionLocal, Panel
from prompts.twin_utterance import TWIN_UTTERANCE_PROMPT, format_chat_history
from services.usage_tracker import tracker


_LLM_MODEL = os.getenv("LAB_LLM_MODEL", "gpt-4o-mini")
_llm = ChatOpenAI(model=_LLM_MODEL, temperature=0.7)

# in-memory 페르소나 캐시 — 같은 트윈 반복 채팅 시 DB 재조회 방지.
# value 구조: {"twin_id", "scratch", "persona_full"}
_persona_cache: dict[str, dict] = {}


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def load_twin_persona(twin_id: str) -> dict | None:
    """Twin 한 명의 scratch + persona_full 로드 (캐시 적중 시 즉시 반환)."""
    cached = _persona_cache.get(twin_id)
    if cached is not None:
        return cached

    async with AsyncSessionLocal() as session:
        # source='twin2k500' 필터로 본 서비스 데이터와 격리.
        result = await session.execute(
            select(Panel).where(
                Panel.panel_id == twin_id,
                Panel.source == "twin2k500",
            )
        )
        panel = result.scalar_one_or_none()
        if not panel:
            return None

        scratch = panel.scratch
        if isinstance(scratch, str):
            scratch = json.loads(scratch)

    persona = {
        "twin_id": twin_id,
        "scratch": scratch or {},
        "persona_full": panel.persona_full or "",
    }
    _persona_cache[twin_id] = persona
    return persona


async def stream_chat(
    twin_id: str,
    history: list[dict],
    message: str,
) -> AsyncGenerator[str, None]:
    """1:1 채팅 SSE 제너레이터 (Toubia 풀-프롬프트).

    이벤트:
        start  -> 응답 시작 (twin 식별 정보)
        delta  -> 토큰 스트리밍
        end    -> 전체 응답
        error  -> 에러 (twin_not_found / persona_missing / internal)
    """
    persona = await load_twin_persona(twin_id)
    if not persona:
        yield _sse({"type": "error", "reason": "twin_not_found"})
        return

    persona_full = persona.get("persona_full") or ""
    if not persona_full.strip():
        # 풀 페르소나가 비어있으면 (백필 누락) 진행 불가 — 에러로 알림.
        yield _sse({"type": "error", "reason": "persona_missing"})
        return

    system_prompt = TWIN_UTTERANCE_PROMPT.format(persona_full=persona_full)
    chat_history_text = format_chat_history(history)
    human_prompt = (
        f"[지금까지의 대화]\n{chat_history_text}\n\n"
        f"[사용자의 새 메시지]\n{message}\n\n"
        "위 메시지에 한국어로 자연스럽게 답하세요."
    )

    scratch = persona["scratch"]
    twin_name = scratch.get("display_name") or persona["twin_id"]
    yield _sse({
        "type": "start",
        "twin_id": twin_id,
        "name": twin_name,
    })

    full_text = ""
    input_tokens = 0
    output_tokens = 0
    try:
        async for chunk in _llm.astream([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt),
        ]):
            delta = chunk.content
            if delta:
                full_text += delta
                yield _sse({"type": "delta", "delta": delta})
            usage = getattr(chunk, "usage_metadata", None)
            if usage:
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
    except Exception as exc:  # noqa: BLE001
        print(f"[lab] LLM 스트리밍 실패: {exc}")
        yield _sse({"type": "error", "reason": "internal"})
        return

    # usage_metadata가 누락된 경우 길이 기반 근사치
    if not input_tokens and not output_tokens:
        input_tokens = len(system_prompt + human_prompt) // 3
        output_tokens = len(full_text) // 3
    tracker.log(
        service="lab/chat",
        model=_LLM_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    yield _sse({
        "type": "end",
        "content": full_text.strip(),
    })


# ─── 카드 / 모달 미리보기용 페르소나 정보 ────────────────────────────────────────

# Big5 차원 → (높을 때 한국어 라벨, 낮을 때 한국어 라벨).
_BIG5_KO = {
    "openness":          ("개방적", "관습적"),
    "conscientiousness": ("성실함", "자유로움"),
    "extraversion":      ("외향적", "내향적"),
    "agreeableness":     ("협조적", "독립적"),
    "neuroticism":       ("예민함", "안정적"),
}

# 정치성향(political_views) → 한국어 한 단어.
_POLITICS_KO = {
    "very conservative": "강보수",
    "conservative":      "보수",
    "moderate":          "중도",
    "liberal":           "진보",
    "very liberal":      "강진보",
}

# 결혼상태(marital_status) → 한국어.
_MARITAL_KO = {
    "married":          "기혼",
    "single":           "미혼",
    "never married":    "미혼",
    "divorced":         "이혼",
    "widowed":          "사별",
    "separated":        "별거",
}


def _build_tags(scratch: dict) -> list[str]:
    """카드 미리보기용 3~5개 한국어 키워드 태그.

    우선순위:
      1) Big5에서 가장 극단적인(|p-50|이 큰) 1~2개 차원
      2) 정치성향
      3) 결혼상태
      4) 소득 구간 (고/중/저)
    """
    tags: list[str] = []

    # 1) Big5 — 가장 두드러진 차원 최대 2개
    big5_raw = scratch.get("big5") or {}
    extremes: list[tuple[int, str]] = []
    for dim, (high, low) in _BIG5_KO.items():
        entry = big5_raw.get(dim)
        if not isinstance(entry, dict):
            continue
        p = entry.get("percentile")
        if p is None:
            continue
        deviation = abs(int(p) - 50)
        if int(p) >= 70:
            extremes.append((deviation, high))
        elif int(p) <= 30:
            extremes.append((deviation, low))
    extremes.sort(reverse=True)
    for _, label in extremes[:2]:
        tags.append(label)

    # 2) 정치성향
    pv = (scratch.get("political_views") or "").strip().lower()
    if pv in _POLITICS_KO:
        tags.append(_POLITICS_KO[pv])

    # 3) 결혼상태
    ms = (scratch.get("marital_status") or "").strip().lower()
    if ms in _MARITAL_KO:
        tags.append(_MARITAL_KO[ms])

    # 4) 소득 구간 — "$75,000-$100,000" 같은 문자열에서 첫 숫자 추출
    import re
    income = scratch.get("income") or ""
    m = re.search(r"\$([\d,]+)", income)
    if m:
        try:
            n = int(m.group(1).replace(",", ""))
            if n >= 100000:
                tags.append("고소득")
            elif n >= 50000:
                tags.append("중간소득")
            else:
                tags.append("저소득")
        except ValueError:
            pass

    return tags[:5]


async def list_twins(limit: int = 50) -> list[dict]:
    """Lab 카드용 Twin 목록.

    `Panel.source='twin2k500'`인 패널만 반환. 필요 최소 정보(scratch 일부)만 노출.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Panel)
            .where(Panel.source == "twin2k500")
            .limit(limit)
        )
        rows = result.scalars().all()

    twins: list[dict] = []
    for panel in rows:
        scratch = panel.scratch
        if isinstance(scratch, str):
            scratch = json.loads(scratch)
        scratch = scratch or {}

        # Big5는 {dim: {value, percentile}} 구조 — percentile만 추출하여 0~100 정수로 평탄화
        big5_raw = scratch.get("big5") or {}
        big5: dict[str, int] = {}
        for dim in ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"):
            entry = big5_raw.get(dim)
            if isinstance(entry, dict) and entry.get("percentile") is not None:
                big5[dim] = int(entry["percentile"])

        twins.append({
            "twin_id": panel.panel_id,
            "name": scratch.get("display_name") or panel.panel_id,
            "emoji": scratch.get("emoji") or "🧑",
            "age": panel.age or scratch.get("age"),
            "age_range": scratch.get("age_range"),
            "gender": panel.gender or scratch.get("gender"),
            "occupation": panel.occupation or scratch.get("occupation"),
            "region": panel.region or scratch.get("region"),
            "intro": scratch.get("intro_ko") or "(소개 정보 없음)",
            "race": scratch.get("race"),
            "education": scratch.get("education"),
            "marital_status": scratch.get("marital_status"),
            "religion": scratch.get("religion"),
            "income": scratch.get("income"),
            "household_size": (
                str(scratch["household_size"]) if scratch.get("household_size") not in (None, "") else None
            ),
            "political_views": scratch.get("political_views"),
            "political_affiliation": scratch.get("political_affiliation"),
            "big5": big5 or None,
            "traits": scratch.get("traits") or [],
            "tags": _build_tags(scratch),
            "aspire": scratch.get("aspire"),
            "aspire_ko": scratch.get("aspire_ko"),
            "actual": scratch.get("actual"),
            "actual_ko": scratch.get("actual_ko"),
        })
    return twins
