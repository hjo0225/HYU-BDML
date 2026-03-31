"""시장조사 서비스 — LangGraph 파이프라인"""
import asyncio
import re
from typing import AsyncIterator
from typing import TypedDict
from pydantic import BaseModel
from agents import Agent, Runner, WebSearchTool, ModelSettings
from langgraph.graph import StateGraph, START, END
from models.schemas import ResearchBrief
from prompts.research import (
    REFINER_PROMPT,
    KEYWORD_EXTRACTOR_PROMPT,
    SEARCHER_PROMPT,
    REPORT_SYNTHESIZER_PROMPT,
    CLAIM_EXTRACTOR_PROMPT,
    CLAIM_VERIFIER_PROMPT,
)

import services.openai_client  # noqa: F401
from services.usage_tracker import tracker


def _log_runner_usage(result, service_label: str):
    """Runner.run() 결과에서 토큰 사용량 추출·기록"""
    for resp in getattr(result, "raw_responses", []):
        usage = getattr(resp, "usage", None)
        if usage:
            tracker.log(
                service=service_label,
                model="gpt-4o-mini",
                input_tokens=getattr(usage, "input_tokens", 0),
                output_tokens=getattr(usage, "output_tokens", 0),
            )


# 한국 내 검색
_web_search = WebSearchTool(
    user_location={"type": "approximate", "country": "KR"},
    search_context_size="high",
)


# ── Pydantic 스키마 ──

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


class SearchResult(BaseModel):
    """검색 결과 구조화 출력"""
    content: str
    sources: list[str]


class ReportOutput(BaseModel):
    """최종 보고서 출력 스키마"""
    market_overview: str
    competitive_landscape: str
    target_analysis: str
    trends: str
    implications: str


# step_verify 전용 중간 모델
class ClaimItem(BaseModel):
    field: str
    original_text: str
    search_query: str


class ClaimsExtracted(BaseModel):
    claims: list[ClaimItem]


class VerifiedClaim(BaseModel):
    field: str
    original_text: str
    corrected_text: str
    correction_applied: bool
    source: str


# ── LangGraph State ──

class ResearchState(TypedDict):
    brief: ResearchBrief
    user_message: str
    keywords: SearchKeywords | None
    search_results: dict[str, str]
    report: ReportOutput | None
    verified_report: ReportOutput | None
    refined: RefinedOutput | None


# ── 에이전트 팩토리 ──

def _create_refiner(market_report: str) -> Agent:
    return Agent(
        name="연구 정보 고도화",
        instructions=REFINER_PROMPT.replace("{{market_report}}", market_report),
        model="gpt-4o-mini",
        output_type=RefinedOutput,
    )


keyword_agent = Agent(
    name="키워드 추출",
    instructions=KEYWORD_EXTRACTOR_PROMPT,
    model="gpt-4o-mini",
    output_type=SearchKeywords,
    model_settings=ModelSettings(temperature=0.3),
)


def _create_searcher(research_context: str) -> Agent:
    # .format() 대신 replace로 치환 — brief에 중괄호가 있어도 안전
    instructions = SEARCHER_PROMPT.replace("{research_context}", research_context)
    return Agent(
        name="웹 검색 리서처",
        instructions=instructions,
        model="gpt-4o-mini",
        tools=[_web_search],
    )


def _create_synthesizer(research_context: str) -> Agent:
    instructions = REPORT_SYNTHESIZER_PROMPT.replace("{research_context}", research_context)
    return Agent(
        name="보고서 종합",
        instructions=instructions,
        model="gpt-4o-mini",
        output_type=ReportOutput,
    )


def _create_claim_extractor() -> Agent:
    return Agent(
        name="수치 추출",
        instructions=CLAIM_EXTRACTOR_PROMPT,
        model="gpt-4o-mini",
        output_type=ClaimsExtracted,
        model_settings=ModelSettings(temperature=0.2),
    )


def _create_claim_verifier() -> Agent:
    return Agent(
        name="수치 검증",
        instructions=CLAIM_VERIFIER_PROMPT,
        model="gpt-4o-mini",
        tools=[_web_search],
        output_type=VerifiedClaim,
    )


# ── 유틸리티 ──

def _clean_inline_citations(text: str) -> str:
    text = re.sub(r'\s*\(\[([^\]]*)\]\([^\)]+\)\)', '', text)
    text = re.sub(r'\[([^\]]*)\]\(https?://[^\)]+\)', r'\1', text)
    text = re.sub(r'\s*\(https?://[^\)]+\)', '', text)
    text = re.sub(r'\s*\([a-zA-Z0-9.-]+\.(com|co|org|net|io|kr)[^\)]*\)', '', text)
    text = re.sub(r'turn\d+search\d+', '', text)
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'  +', ' ', text).strip()
    return text


def _clean_sources(text: str) -> str:
    def _repl_wrapped(m):
        url = re.sub(r'\?utm_source=[^&)\s]+', '', m.group(2))
        return f"{m.group(1)} ({url})"
    text = re.sub(r'\(\[([^\]]*)\]\((https?://[^\)]+)\)\)', _repl_wrapped, text)

    def _repl(m):
        url = re.sub(r'\?utm_source=[^&)\s]+', '', m.group(2))
        return f"{m.group(1)} ({url})"
    text = re.sub(r'\[([^\]]*)\]\((https?://[^\)]+)\)', _repl, text)
    text = re.sub(r'\?utm_source=[^&)\s]+', '', text)
    return text.strip()


def _clean_report(report: ReportOutput) -> dict:
    return {
        "market_overview": _clean_inline_citations(report.market_overview),
        "competitive_landscape": _clean_inline_citations(report.competitive_landscape),
        "target_analysis": _clean_inline_citations(report.target_analysis),
        "trends": _clean_inline_citations(report.trends),
        "implications": _clean_inline_citations(report.implications),
        "sources": _clean_sources(report.sources),
    }


def _report_to_text(report: ReportOutput) -> str:
    return (
        f"시장 개요: {report.market_overview}\n"
        f"경쟁 환경: {report.competitive_landscape}\n"
        f"타깃 분석: {report.target_analysis}\n"
        f"트렌드: {report.trends}\n"
        f"시사점: {report.implications}"
    )


# ── Step 함수들 (단독 호출 가능) ──

async def step_extract_keywords(user_message: str) -> SearchKeywords:
    """단계 1: 연구 정보 → 카테고리별 검색 키워드 추출"""
    result = await Runner.run(keyword_agent, user_message)
    _log_runner_usage(result, "research/keywords")
    return result.final_output


async def step_search(
    keywords: SearchKeywords,
    research_context: str,
) -> AsyncIterator[tuple[str, str]]:
    """단계 2-6: 카테고리별 병렬 웹검색, (field, text) 쌍을 완료 순으로 yield"""
    searcher = _create_searcher(research_context)

    search_fields = [
        ("market_overview",       keywords.market_overview),
        ("competitive_landscape", keywords.competitive_landscape),
        ("target_analysis",       keywords.target_analysis),
        ("trends",                keywords.trends),
        ("implications",          keywords.implications),
    ]

    async def _search_one(field: str, queries: list[str]) -> tuple[str, str]:
        combined = "다음 키워드들을 각각 검색하여 결과를 통합하세요:\n" + "\n".join(f"- {q}" for q in queries)
        r = await Runner.run(searcher, combined)
        _log_runner_usage(r, f"research/search/{field}")
        return field, r.final_output

    tasks = [_search_one(field, queries) for field, queries in search_fields]
    for coro in asyncio.as_completed(tasks):
        field, text = await coro
        yield field, text


async def step_synthesize(
    search_results: dict[str, str],
    research_context: str,
) -> ReportOutput:
    """단계 7a: 검색 결과 종합 → 보고서 초안"""
    synthesizer = _create_synthesizer(research_context)
    synthesis_input = "\n\n".join(
        f"[{field}]\n{text}" for field, text in search_results.items()
    )
    result = await Runner.run(synthesizer, synthesis_input)
    _log_runner_usage(result, "research/synthesizer")
    return result.final_output


async def step_verify(report: ReportOutput, user_message: str) -> ReportOutput:
    """단계 7b: 주요 수치 claim 추출 → asyncio.gather 병렬 교차검증 → 보고서 반영"""

    # 1. 검증 대상 claim 추출 (최대 5개)
    extractor = _create_claim_extractor()
    extract_result = await Runner.run(extractor, _report_to_text(report))
    _log_runner_usage(extract_result, "research/verify/extract")
    claims: list[ClaimItem] = extract_result.final_output.claims[:5]

    if not claims:
        return report

    # 2. 각 claim 개별 Runner.run() → asyncio.gather 병렬 실행
    verifier = _create_claim_verifier()

    async def _verify_one(claim: ClaimItem) -> VerifiedClaim:
        verify_input = (
            f"검증 대상 필드: {claim.field}\n"
            f"원문: {claim.original_text}\n"
            f"검색 쿼리: {claim.search_query}"
        )
        r = await Runner.run(verifier, verify_input)
        _log_runner_usage(r, "research/verify/claim")
        return r.final_output

    verified: list[VerifiedClaim] = list(
        await asyncio.gather(*[_verify_one(c) for c in claims])
    )

    # 3. 수정 사항을 보고서 필드에 반영
    report_dict = report.model_dump()
    extra_sources: list[str] = []

    for vc in verified:
        if not vc.correction_applied:
            continue
        field = vc.field
        if field not in report_dict or field == "sources":
            continue
        current = report_dict[field]
        if vc.original_text in current:
            report_dict[field] = current.replace(vc.original_text, vc.corrected_text, 1)
            if vc.source:
                extra_sources.append(vc.source)

    if extra_sources:
        report_dict["sources"] = report_dict["sources"].rstrip() + "\n" + "\n".join(extra_sources)

    return ReportOutput(**report_dict)


async def step_refine(report: ReportOutput, user_message: str) -> RefinedOutput:
    """단계 8: 검증된 보고서 기반 연구 정보 고도화"""
    refiner = _create_refiner(_report_to_text(report))
    result = await Runner.run(refiner, user_message)
    _log_runner_usage(result, "research/refiner")
    return result.final_output


# ── LangGraph 노드 ──

async def _node_init(state: ResearchState) -> dict:
    """ResearchBrief → user_message 변환"""
    brief = state["brief"]
    user_message = (
        f"연구 배경: {brief.background}\n"
        f"연구 목적: {brief.objective}\n"
        f"활용방안: {brief.usage_plan}\n"
        f"카테고리: {brief.category}\n"
        f"타깃 고객: {brief.target_customer}"
    )
    return {"user_message": user_message}


async def _node_extract_keywords(state: ResearchState) -> dict:
    keywords = await step_extract_keywords(state["user_message"])
    return {"keywords": keywords}


async def _node_search(state: ResearchState) -> dict:
    """5개 카테고리 병렬 검색 (asyncio.as_completed 내부 유지)"""
    search_results: dict[str, str] = {}
    async for field, text in step_search(state["keywords"], state["user_message"]):
        search_results[field] = text
    return {"search_results": search_results}


async def _node_synthesize(state: ResearchState) -> dict:
    report = await step_synthesize(state["search_results"], state["user_message"])
    return {"report": report}


async def _node_verify(state: ResearchState) -> dict:
    verified_report = await step_verify(state["report"], state["user_message"])
    return {"verified_report": verified_report}


async def _node_refine(state: ResearchState) -> dict:
    refined = await step_refine(state["verified_report"], state["user_message"])
    return {"refined": refined}


# ── 그래프 조립 (모듈 로드 시 1회 컴파일) ──

def _build_graph():
    g = StateGraph(ResearchState)

    g.add_node("init",             _node_init)
    g.add_node("extract_keywords", _node_extract_keywords)
    g.add_node("search",           _node_search)
    g.add_node("synthesize",       _node_synthesize)
    g.add_node("verify",           _node_verify)
    g.add_node("refine",           _node_refine)

    g.add_edge(START,             "init")
    g.add_edge("init",            "extract_keywords")
    g.add_edge("extract_keywords","search")
    g.add_edge("search",          "synthesize")
    g.add_edge("synthesize",      "verify")
    g.add_edge("verify",          "refine")
    g.add_edge("refine",          END)

    return g.compile()


_research_graph = _build_graph()


# ── 공개 인터페이스 ──

async def run_research(brief: ResearchBrief) -> dict:
    """시장조사 수행 — LangGraph 그래프 실행, 최종 결과 dict 반환"""
    initial_state: ResearchState = {
        "brief":          brief,
        "user_message":   "",
        "keywords":       None,
        "search_results": {},
        "report":         None,
        "verified_report": None,
        "refined":        None,
    }
    final_state = await _research_graph.ainvoke(initial_state)
    return {
        "refined": final_state["refined"].model_dump(),
        "report":  _clean_report(final_state["verified_report"]),
    }
