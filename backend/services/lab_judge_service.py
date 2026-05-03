"""Lab Faithfulness — LLM-as-judge 단일 (질문, 답변) 채점 서비스.

L3 엄격 검증 버튼과 오프라인 평가(eval_lab_faithfulness) 양쪽에서 동일하게 사용.

기본 모델은 gpt-4o (LAB_JUDGE_MODEL 환경변수로 오버라이드 가능). temperature=0.
"""
from __future__ import annotations

import json
import os
from typing import Iterable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

import services.openai_client  # noqa: F401  (환경변수 로드)
from models.schemas import LabJudgeResponse
from prompts.lab_judge import LAB_JUDGE_SYSTEM, LAB_JUDGE_USER_TEMPLATE
from services.lab_citation_service import _scored_top_k  # 내부 헬퍼 재사용
from services.usage_tracker import tracker


_JUDGE_MODEL = os.getenv("LAB_JUDGE_MODEL", "gpt-4o")
_judge_llm = ChatOpenAI(model=_JUDGE_MODEL, temperature=0.0)

# 페르소나 청크 발췌 길이 — 너무 길면 비용 폭주
_CHUNK_TRIM_CHARS = 600
_CHUNK_TOPK = 6


_VALID_VERDICTS = {"consistent", "partial", "contradicts", "evasive"}


def _format_chunks(rows: Iterable[tuple[float, object]]) -> str:
    """top-k 매칭 메모리를 카테고리별 발췌로 직렬화."""
    lines: list[str] = []
    seen: set[str] = set()
    for _score, row in rows:
        category = getattr(row, "category", None)
        text = getattr(row, "text", None)
        if not category or not text:
            continue
        if category in seen:
            continue
        seen.add(category)
        snippet = text.strip()
        if len(snippet) > _CHUNK_TRIM_CHARS:
            snippet = snippet[: _CHUNK_TRIM_CHARS - 1].rstrip() + "…"
        lines.append(f"## {category}\n{snippet}")
    return "\n\n".join(lines) if lines else "(매칭된 페르소나 청크 없음)"


def _safe_json_parse(text: str) -> dict | None:
    """LLM 출력에서 첫 JSON 객체 파싱. 마크다운 코드펜스도 관용."""
    if not text:
        return None
    cleaned = text.strip()
    # 코드펜스 제거
    if cleaned.startswith("```"):
        cleaned = cleaned.lstrip("`")
        # 첫 줄 언어 표기 제거
        nl = cleaned.find("\n")
        if nl >= 0:
            cleaned = cleaned[nl + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    # 첫 { ~ 마지막 } 범위만 시도
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < 0 or end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None


async def judge_response(
    twin_id: str,
    question: str,
    answer: str,
    extra_meta: str | None = None,
) -> LabJudgeResponse:
    """단일 (질문, 답변) 쌍을 채점.

    페르소나 청크는 답변 임베딩 top-k로 자동 추출 (질문이 아닌 답변 기준 — 평가는
    "트윈이 자기 데이터를 따랐는가"를 보므로). 매칭이 빈약하면 verdict는 evasive
    또는 partial이 자연스럽게 나올 가능성이 높다.
    """
    question = (question or "").strip()
    answer = (answer or "").strip()
    if not answer:
        return LabJudgeResponse(
            verdict="evasive",
            reason="답변 내용이 비어 있어 평가가 불가능합니다.",
        )

    scored = await _scored_top_k(twin_id, answer, _CHUNK_TOPK)
    persona_chunks = _format_chunks(scored)

    user_prompt = LAB_JUDGE_USER_TEMPLATE.format(
        persona_chunks=persona_chunks,
        meta=(extra_meta or "(추가 메타 없음)").strip(),
        question=question or "(질문 없음)",
        answer=answer,
    )

    try:
        result = await _judge_llm.ainvoke([
            SystemMessage(content=LAB_JUDGE_SYSTEM),
            HumanMessage(content=user_prompt),
        ])
        raw = result.content if hasattr(result, "content") else str(result)
        # usage 로깅 (가능하면)
        usage = getattr(result, "usage_metadata", None) or {}
        tracker.log(
            service="lab/judge",
            model=_JUDGE_MODEL,
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[lab/judge] LLM 호출 실패: {exc}")
        return LabJudgeResponse(
            verdict="evasive",
            reason="채점 모델 호출에 실패했습니다. 잠시 후 다시 시도해 주세요.",
        )

    parsed = _safe_json_parse(str(raw))
    if not parsed:
        return LabJudgeResponse(
            verdict="evasive",
            reason="채점 결과를 파싱하지 못했습니다.",
        )

    verdict_raw = str(parsed.get("verdict", "")).strip().lower()
    if verdict_raw not in _VALID_VERDICTS:
        verdict_raw = "evasive"

    matched = parsed.get("matched_categories") or []
    contradicted = parsed.get("contradicted_categories") or []
    if not isinstance(matched, list):
        matched = []
    if not isinstance(contradicted, list):
        contradicted = []

    return LabJudgeResponse(
        verdict=verdict_raw,  # type: ignore[arg-type]
        reason=str(parsed.get("reason") or "").strip() or "(설명 없음)",
        matched_categories=[str(c).strip() for c in matched if c],
        contradicted_categories=[str(c).strip() for c in contradicted if c],
    )
