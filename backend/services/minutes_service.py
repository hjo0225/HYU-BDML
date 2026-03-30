"""회의록 생성 서비스 — OpenAI Agents SDK + 웹검색"""
import re
from agents import Agent, Runner, WebSearchTool
from models.schemas import MinutesRequest
from prompts.minutes import MINUTES_PROMPT

# Agents SDK 환경 로드
import services.openai_client  # noqa: F401

# 한국 내 검색 + 높은 검색 깊이
_web_search = WebSearchTool(
    user_location={"type": "approximate", "country": "KR"},
    search_context_size="high",
)

# 회의록 생성 에이전트 (웹검색으로 시장 근거 보강)
minutes_agent = Agent(
    name="회의록 작성자",
    instructions=MINUTES_PROMPT,
    model="gpt-4o",
    tools=[_web_search],
)


def _clean_citations(text: str) -> str:
    """회의록 본문의 인라인 출처 정리"""
    # ([title](url)) 통째로 제거
    text = re.sub(r'\s*\(\[([^\]]*)\]\([^\)]+\)\)', '', text)
    # [title](url) → title
    text = re.sub(r'\[([^\]]*)\]\(https?://[^\)]+\)', r'\1', text)
    # (https://...) 제거
    text = re.sub(r'\s*\(https?://[^\)]+\)', '', text)
    # (domain.com...) 제거
    text = re.sub(r'\s*\([a-zA-Z0-9.-]+\.(com|co|org|net|io|kr)[^\)]*\)', '', text)
    # turn0search 마커 제거
    text = re.sub(r'turn\d+search\d+', '', text)
    # utm 파라미터 제거
    text = re.sub(r'\?utm_source=[^&)\s]+', '', text)
    # 정리
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'  +', ' ', text)
    return text.strip()


async def generate_minutes(req: MinutesRequest) -> str:
    """회의 대화 로그를 분석하여 Markdown 회의록 생성"""

    # 대화 로그 구성
    conversation_log = "\n".join(
        f"[{msg.agent_name}]: {msg.content}" for msg in req.messages
    )

    # 에이전트 정보 구성
    agent_info = "\n".join(
        f"- {a.emoji} {a.name} ({a.type}): {a.description}" for a in req.agents
    )

    user_message = (
        f"[연구 정보]\n"
        f"- 배경: {req.brief.background}\n"
        f"- 목적: {req.brief.objective}\n"
        f"- 활용방안: {req.brief.usage_plan}\n\n"
        f"[참여 에이전트]\n{agent_info}\n\n"
        f"[회의 대화 로그]\n{conversation_log}"
    )

    result = await Runner.run(minutes_agent, user_message)
    return _clean_citations(result.final_output)
