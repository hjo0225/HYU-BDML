"""시장조사 서비스 — 키워드 추출 → 병렬 검색 → 종합 보고서"""
import asyncio
import json
import re
from typing import AsyncGenerator
from pydantic import BaseModel
from agents import Agent, Runner, WebSearchTool, ModelSettings
from models.schemas import ResearchBrief
from prompts.research import (
    REFINER_PROMPT,
    KEYWORD_EXTRACTOR_PROMPT,
    SEARCHER_PROMPT,
    REPORT_SYNTHESIZER_PROMPT,
)

# Agents SDK 환경 로드
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

# 진행 단계 정의
RESEARCH_STEPS = [
    "검색 키워드 추출 중...",
    "시장 규모 검색 중...",
    "경쟁 환경 검색 중...",
    "타깃 고객 검색 중...",
    "트렌드 검색 중...",
    "시사점 검색 중...",
    "보고서 종합 중...",
    "연구 정보 고도화 중...",
]

# 한국 내 검색
_web_search = WebSearchTool(
    user_location={"type": "approximate", "country": "KR"},
    search_context_size="high",
)


# ── 1. 고도화 에이전트 (시장조사 보고서 기반) ──
class RefinedOutput(BaseModel):
    refined_background: str
    refined_objective: str
    refined_usage_plan: str


def _create_refiner(market_report: str) -> Agent:
    """시장조사 보고서를 주입한 고도화 에이전트 생성"""
    return Agent(
        name="연구 정보 고도화",
        instructions=REFINER_PROMPT.replace("{{market_report}}", market_report),
        model="gpt-4o-mini",
        output_type=RefinedOutput,
    )


# ── 2. 키워드 추출 에이전트 ──
class SearchKeywords(BaseModel):
    market_overview: list[str]
    competitive_landscape: list[str]
    target_analysis: list[str]
    trends: list[str]
    implications: list[str]


keyword_agent = Agent(
    name="키워드 추출",
    instructions=KEYWORD_EXTRACTOR_PROMPT,
    model="gpt-4o-mini",
    output_type=SearchKeywords,
    model_settings=ModelSettings(temperature=0.3),
)


# ── 3. 검색 에이전트 (키워드별 웹검색) ──
# 연구 맥락이 주입된 인스턴스를 동적으로 생성
def _create_searcher(research_context: str) -> Agent:
    return Agent(
        name="웹 검색 리서처",
        instructions=SEARCHER_PROMPT.format(research_context=research_context),
        model="gpt-4o-mini",
        tools=[_web_search],
    )


# ── 4. 종합 보고서 에이전트 ──
class ReportOutput(BaseModel):
    market_overview: str
    competitive_landscape: str
    target_analysis: str
    trends: str
    implications: str
    sources: str


def _create_synthesizer(research_context: str) -> Agent:
    return Agent(
        name="보고서 종합",
        instructions=REPORT_SYNTHESIZER_PROMPT.format(research_context=research_context),
        model="gpt-4o-mini",
        output_type=ReportOutput,
    )


def _clean_inline_citations(text: str) -> str:
    """본문에 섞인 인라인 출처 링크/마커 제거"""
    text = re.sub(r'\s*\(\[([^\]]*)\]\([^\)]+\)\)', '', text)
    text = re.sub(r'\[([^\]]*)\]\(https?://[^\)]+\)', r'\1', text)
    text = re.sub(r'\s*\(https?://[^\)]+\)', '', text)
    text = re.sub(r'\s*\([a-zA-Z0-9.-]+\.(com|co|org|net|io|kr)[^\)]*\)', '', text)
    text = re.sub(r'turn\d+search\d+', '', text)
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'  +', ' ', text).strip()
    return text


def _clean_sources(text: str) -> str:
    """출처 필드 정리"""
    def _repl_wrapped(m):
        title = m.group(1)
        url = re.sub(r'\?utm_source=[^&)\s]+', '', m.group(2))
        return f"{title} ({url})"
    text = re.sub(r'\(\[([^\]]*)\]\((https?://[^\)]+)\)\)', _repl_wrapped, text)
    def _repl(m):
        title = m.group(1)
        url = re.sub(r'\?utm_source=[^&)\s]+', '', m.group(2))
        return f"{title} ({url})"
    text = re.sub(r'\[([^\]]*)\]\((https?://[^\)]+)\)', _repl, text)
    text = re.sub(r'\?utm_source=[^&)\s]+', '', text)
    return text.strip()


def _clean_report(report: ReportOutput) -> dict:
    """보고서 본문 출처 제거 + 출처 정리"""
    return {
        "market_overview": _clean_inline_citations(report.market_overview),
        "competitive_landscape": _clean_inline_citations(report.competitive_landscape),
        "target_analysis": _clean_inline_citations(report.target_analysis),
        "trends": _clean_inline_citations(report.trends),
        "implications": _clean_inline_citations(report.implications),
        "sources": _clean_sources(report.sources),
    }


async def run_research(brief: ResearchBrief) -> AsyncGenerator[str, None]:
    """시장조사 수행 — 키워드 추출 → 병렬 검색 → 종합"""

    def _status(step: int):
        return f"data: {json.dumps({'type': 'status', 'step': step, 'total': len(RESEARCH_STEPS), 'message': RESEARCH_STEPS[step - 1]}, ensure_ascii=False)}\n\n"

    user_message = (
        f"연구 배경: {brief.background}\n"
        f"연구 목적: {brief.objective}\n"
        f"활용방안: {brief.usage_plan}\n"
        f"카테고리: {brief.category}\n"
        f"타깃 고객: {brief.target_customer}"
    )

    # 연구 맥락 문자열 (검색/종합 에이전트에 주입)
    research_context = user_message

    # ── 단계 1: 검색 키워드 추출 ──
    yield _status(1)
    kw_result = await Runner.run(keyword_agent, user_message)
    _log_runner_usage(kw_result, "research/keywords")
    keywords: SearchKeywords = kw_result.final_output

    searcher = _create_searcher(research_context)

    # ── 단계 2~6: 키워드별 병렬 웹검색 ──
    search_fields = [
        ("market_overview", keywords.market_overview),
        ("competitive_landscape", keywords.competitive_landscape),
        ("target_analysis", keywords.target_analysis),
        ("trends", keywords.trends),
        ("implications", keywords.implications),
    ]

    async def _search(field: str, queries: list[str]) -> tuple[str, str]:
        """카테고리별 키워드 리스트를 하나의 검색 요청으로 전달"""
        combined_query = f"다음 키워드들을 각각 검색하여 결과를 통합하세요:\n" + "\n".join(f"- {q}" for q in queries)
        result = await Runner.run(searcher, combined_query)
        _log_runner_usage(result, f"research/search/{field}")
        return field, result.final_output

    # 5개 카테고리 병렬 검색
    tasks = [_search(field, queries) for field, queries in search_fields]
    search_results = {}
    for i, coro in enumerate(asyncio.as_completed(tasks)):
        field, text = await coro
        search_results[field] = text
        yield _status(2 + i)

    # ── 단계 7: 검색 결과 종합 → 보고서 ──
    yield _status(7)

    synthesizer = _create_synthesizer(research_context)
    synthesis_input = "\n\n".join(
        f"[{field}]\n{text}" for field, text in search_results.items()
    )
    report_result = await Runner.run(synthesizer, synthesis_input)
    _log_runner_usage(report_result, "research/synthesizer")
    report: ReportOutput = report_result.final_output

    # ── 단계 8: 보고서 기반 연구 정보 고도화 ──
    yield _status(8)

    # 보고서 내용을 텍스트로 변환하여 고도화 에이전트에 전달
    report_text = (
        f"시장 개요: {report.market_overview}\n"
        f"경쟁 환경: {report.competitive_landscape}\n"
        f"타깃 분석: {report.target_analysis}\n"
        f"트렌드: {report.trends}\n"
        f"시사점: {report.implications}"
    )
    refiner = _create_refiner(report_text)
    refined_result = await Runner.run(refiner, user_message)
    _log_runner_usage(refined_result, "research/refiner")
    refined: RefinedOutput = refined_result.final_output

    # 결과 조합
    data = {
        "refined": refined.model_dump(),
        "report": _clean_report(report),
    }
    yield f"data: {json.dumps({'type': 'result', 'data': data}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"
