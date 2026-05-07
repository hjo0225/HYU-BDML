"""시장조사 스트리밍 파이프라인.

브리프 확장 -> 검색 계획 수립 -> 섹션별 근거 수집 -> 요약 생성 -> 최종 브리프 재정제 순서로 동작한다.
"""
import asyncio
import json
import re
from typing import AsyncGenerator

from openai import AsyncOpenAI
from pydantic import BaseModel

from models.schemas import MarketReport, ResearchBrief, ReportSection
from prompts.research import (
    KEYWORD_EXTRACTOR_PROMPT,
    PRE_REFINER_PROMPT,
    REFINER_PROMPT,
    SIMPLE_REFINER_PROMPT,
)
from services.naver_search_service import NaverSearchService, SearchResultItem
from services.openai_web_search_service import OpenAIWebSearchService
from services.research_query_planner import plan_research_queries
from services.research_source_ranker import dedupe_and_rank
from services.research_synthesizer import build_report, synthesize_section
from services.usage_tracker import tracker

_client = AsyncOpenAI()
_naver_search = NaverSearchService()
_openai_web_search = OpenAIWebSearchService(_client)

OPENAI_STEP_TIMEOUT_SECONDS = 35
OPENAI_SEARCH_TIMEOUT_SECONDS = 25
SYNTHESIZE_TIMEOUT_SECONDS = 30

_FIELD_TERMS = {
    "market_overview": ["시장", "규모", "국내", "한국"],
    "competitive_landscape": ["경쟁", "브랜드", "대체재", "서비스"],
    "target_analysis": ["타깃", "고객", "니즈", "행동"],
    "trends": ["트렌드", "MZ", "2030", "국내"],
    "implications": ["기회", "문제점", "차별화", "시사점"],
}


class RefinedOutput(BaseModel):
    refined_background: str
    refined_objective: str
    refined_usage_plan: str


class SearchKeywords(BaseModel):
    market_overview: list[str]
    competitive_landscape: list[str]
    target_analysis: list[str]
    trends: list[str]
    implications: list[str]


def _log_response_usage(response, label: str, model: str) -> None:
    usage = getattr(response, "usage", None)
    if not usage:
        return
    tracker.log(
        service=label,
        model=model,
        input_tokens=getattr(usage, "input_tokens", 0),
        output_tokens=getattr(usage, "output_tokens", 0),
    )


def _ndjson(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False) + "\n"


def _report_to_dict(report: MarketReport) -> dict:
    return report.model_dump()


def _normalize_refined_payload(payload: dict, brief: ResearchBrief) -> dict:
    """모델이 키 이름을 조금 다르게 반환해도 표준 필드명으로 정규화한다."""
    for wrapper_key in ("refined", "result", "data", "output"):
        wrapped = payload.get(wrapper_key)
        if isinstance(wrapped, dict):
            payload = wrapped
            break

    def canonicalize(value: str) -> str:
        return re.sub(r"[\s_\-:]+", "", str(value).strip().lower())

    normalized = {canonicalize(key): value for key, value in payload.items()}

    def pick(*keys: str) -> str:
        for key in keys:
            value = normalized.get(canonicalize(key))
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    refined_background = pick(
        "refined_background",
        "background",
        "연구배경",
        "연구 배경",
        "배경",
    ) or brief.background
    refined_objective = pick(
        "refined_objective",
        "objective",
        "연구목적",
        "연구 목적",
        "목적",
    ) or brief.objective
    refined_usage_plan = pick(
        "refined_usage_plan",
        "usage_plan",
        "활용방안",
        "활용 방안",
        "연구결과활용방안",
        "연구결과 활용방안",
    ) or brief.usage_plan

    return {
        "refined_background": refined_background,
        "refined_objective": refined_objective,
        "refined_usage_plan": refined_usage_plan,
    }


async def step_pre_refine(brief: ResearchBrief) -> str:
    prompt = (
        f"연구 배경: {brief.background}\n"
        f"연구 목적: {brief.objective}\n"
        f"활용방안: {brief.usage_plan}\n"
        f"카테고리: {brief.category}\n"
        f"타깃 고객: {brief.target_customer}"
    )
    response = await asyncio.wait_for(
        _client.responses.create(
            model="gpt-4.1-mini",
            instructions=PRE_REFINER_PROMPT,
            input=prompt,
            temperature=0.4,
        ),
        timeout=OPENAI_STEP_TIMEOUT_SECONDS,
    )
    _log_response_usage(response, "research/pre_refine", "gpt-4.1-mini")
    return (getattr(response, "output_text", "") or "").strip()


async def step_extract_keywords(brief: ResearchBrief, expanded_context: str) -> SearchKeywords | None:
    prompt = (
        f"[원본 브리프]\n"
        f"- 연구 배경: {brief.background}\n"
        f"- 연구 목적: {brief.objective}\n"
        f"- 활용방안: {brief.usage_plan}\n"
        f"- 카테고리: {brief.category}\n"
        f"- 타깃 고객: {brief.target_customer}\n\n"
        f"[확장 맥락]\n{expanded_context}"
    )
    response = await asyncio.wait_for(
        _client.responses.create(
            model="gpt-4.1-mini",
            instructions=KEYWORD_EXTRACTOR_PROMPT,
            input=prompt,
            temperature=0.3,
        ),
        timeout=OPENAI_STEP_TIMEOUT_SECONDS,
    )
    _log_response_usage(response, "research/keywords", "gpt-4.1-mini")
    content = (getattr(response, "output_text", "") or "").strip()
    try:
        return SearchKeywords.model_validate(json.loads(_extract_json_object(content)))
    except Exception:
        return None


async def refine_research_simple(brief: ResearchBrief) -> RefinedOutput:
    prompt = (
        f"연구 배경: {brief.background}\n"
        f"연구 목적: {brief.objective}\n"
        f"활용방안: {brief.usage_plan}\n"
        f"카테고리: {brief.category}\n"
        f"타깃 고객: {brief.target_customer}\n"
    )

    response = await asyncio.wait_for(
        _client.responses.create(
            model="gpt-4.1-mini",
            instructions=(
                SIMPLE_REFINER_PROMPT
                + "\n\n반드시 JSON만 출력하세요."
                + '\n키 이름은 반드시 "refined_background", "refined_objective", "refined_usage_plan" 만 사용하세요.'
            ),
            input=prompt,
            temperature=0.4,
        ),
        timeout=OPENAI_STEP_TIMEOUT_SECONDS,
    )
    _log_response_usage(response, "research/refine_simple", "gpt-4.1-mini")
    content = getattr(response, "output_text", "") or ""
    payload = json.loads(_extract_json_object(content))
    return RefinedOutput.model_validate(_normalize_refined_payload(payload, brief))


async def run_research_stream(brief: ResearchBrief) -> AsyncGenerator[str, None]:
    """프론트엔드가 바로 렌더링할 수 있도록 단계별 NDJSON 이벤트를 순서대로 내보낸다."""
    yield _ndjson({"step": "pre_refine"})

    try:
        expanded_context = await step_pre_refine(brief)
    except Exception:
        expanded_context = brief.objective

    try:
        keyword_output = await step_extract_keywords(brief, expanded_context)
    except Exception:
        keyword_output = None
    plans = plan_research_queries(brief, keyword_output.model_dump() if keyword_output else None)
    yield _ndjson({"step": "planning"})

    # 섹션별로 근거를 먼저 모아 둔 뒤, 이후 요약 생성 단계에서 사용한다.
    section_evidence: dict[str, list] = {}

    for section, search_plans in plans.items():
        raw_items: list[SearchResultItem] = []
        for plan in search_plans:
            yield _ndjson(
                {
                    "step": "thinking",
                    "agent": "researcher",
                    "query": f"[{plan.source_type}] {plan.query}",
                }
            )
            try:
                raw_items.extend(
                    _naver_search.search(
                        source_type=plan.source_type,
                        query=plan.query,
                        display=plan.display,
                        start=plan.start,
                        sort=plan.sort,
                    )
                )
            except Exception as exc:
                yield _ndjson(
                    {
                        "step": "thinking",
                        "agent": "fact_checker",
                        "query": f"{plan.source_type} 검색 실패: {str(exc)[:120]}",
                    }
                )

        # OpenAI 웹 검색은 섹션당 한 번만 추가해 네이버 검색의 빈 구간을 보완한다.
        openai_query = search_plans[0].query if search_plans else f"{brief.category} {section} 한국"
        yield _ndjson(
            {
                "step": "thinking",
                "agent": "fact_checker",
                "query": f"[openai_web] {openai_query}",
            }
        )
        try:
            raw_items.extend(
                await asyncio.wait_for(
                    _openai_web_search.search(section=section, query=openai_query),
                    timeout=OPENAI_SEARCH_TIMEOUT_SECONDS,
                )
            )
        except Exception as exc:
            yield _ndjson(
                {
                    "step": "thinking",
                    "agent": "fact_checker",
                    "query": f"openai_web 검색 실패: {str(exc)[:120]}",
                }
            )

        section_terms = [brief.category, brief.target_customer, *_FIELD_TERMS.get(section, [])]
        section_evidence[section] = dedupe_and_rank(raw_items, section_terms, section=section)

    yield _ndjson({"step": "researcher"})
    yield _ndjson({"step": "fact_checker"})

    section_order = [
        "market_overview",
        "competitive_landscape",
        "target_analysis",
        "trends",
        "implications",
    ]
    synthesized: dict[str, ReportSection] = {}

    for section in section_order:
        # 앞에서 만든 섹션을 같이 넘겨 뒤 섹션이 문맥을 공유하도록 한다.
        related_sections = dict(synthesized)
        try:
            section_report = await asyncio.wait_for(
                synthesize_section(
                    client=_client,
                    brief=brief,
                    section=section,
                    evidence=section_evidence.get(section, []),
                    related_sections=related_sections,
                    research_context=expanded_context,
                ),
                timeout=SYNTHESIZE_TIMEOUT_SECONDS,
            )
        except Exception:
            # 요약 생성이 실패해도 근거 목록은 전달해 사용자가 빈 화면을 보지 않게 한다.
            fallback_evidence = section_evidence.get(section, [])
            section_report = ReportSection(
                summary="수집된 근거를 정리하는 중 지연이 발생해 보수적으로 요약했습니다.\n\n주요 근거는 아래 evidence 항목을 확인해 주세요.",
                key_claims=[item.title for item in fallback_evidence[:3]],
                evidence=fallback_evidence[:4],
                confidence="low" if not fallback_evidence else "medium",
            )
        synthesized[section] = section_report
        yield _ndjson(
            {
                "step": "section",
                "field": section,
                "content": section_report.summary,
            }
        )

    report = build_report(
        market_overview=synthesized["market_overview"],
        competitive_landscape=synthesized["competitive_landscape"],
        target_analysis=synthesized["target_analysis"],
        trends=synthesized["trends"],
        implications=synthesized["implications"],
    )

    try:
        refined = await _refine_research_from_report(brief, report)
    except Exception:
        # 마지막 정제 단계가 실패하면 원본 브리프를 그대로 유지한다.
        refined = RefinedOutput(
            refined_background=brief.background,
            refined_objective=brief.objective,
            refined_usage_plan=brief.usage_plan,
        )
    yield _ndjson(
        {
            "step": "done",
            "refined": refined.model_dump(),
            "report": _report_to_dict(report),
        }
    )


async def _refine_research_from_report(brief: ResearchBrief, report: MarketReport) -> RefinedOutput:
    report_text = (
        f"시장 개요: {report.market_overview.summary}\n"
        f"경쟁 환경: {report.competitive_landscape.summary}\n"
        f"타깃 분석: {report.target_analysis.summary}\n"
        f"트렌드: {report.trends.summary}\n"
        f"시사점: {report.implications.summary}"
    )
    instructions = (
        REFINER_PROMPT.replace("{{market_report}}", report_text)
        + "\n\n반드시 JSON만 출력하세요."
        + '\n키 이름은 반드시 "refined_background", "refined_objective", "refined_usage_plan" 만 사용하세요.'
    )
    prompt = (
        f"[원본 브리프]\n"
        f"- 연구 배경: {brief.background}\n"
        f"- 연구 목적: {brief.objective}\n"
        f"- 활용방안: {brief.usage_plan}\n"
        f"- 카테고리: {brief.category}\n"
        f"- 타깃 고객: {brief.target_customer}\n\n"
        f"[시장 개요]\n{report.market_overview.summary}\n\n"
        f"[경쟁 환경]\n{report.competitive_landscape.summary}\n\n"
        f"[타깃 분석]\n{report.target_analysis.summary}\n\n"
        f"[트렌드]\n{report.trends.summary}\n\n"
        f"[시사점]\n{report.implications.summary}\n"
    )
    response = await asyncio.wait_for(
        _client.responses.create(
            model="gpt-4.1-mini",
            instructions=instructions,
            input=prompt,
            temperature=0.3,
        ),
        timeout=OPENAI_STEP_TIMEOUT_SECONDS,
    )
    _log_response_usage(response, "research/refine_with_report", "gpt-4.1-mini")
    content = getattr(response, "output_text", "") or ""
    payload = json.loads(_extract_json_object(content))
    return RefinedOutput.model_validate(_normalize_refined_payload(payload, brief))


def _extract_json_object(text: str) -> str:
    """모델 응답에서 앞뒤 설명을 제거하고 첫 JSON 객체만 추출한다."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("JSON object not found in model response")
    return text[start : end + 1]
