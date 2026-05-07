"""프로젝트 관련 서비스: LLM 제목 자동 생성."""
import asyncio
from openai import AsyncOpenAI

_client = AsyncOpenAI()

_TITLE_PROMPT = """사용자가 입력한 연구 브리프를 보고, 이 연구 프로젝트의 제목을 한국어로 짧게 한 줄(15자 이내)로 생성하세요.
형식: 제목만 출력. 따옴표, 설명, 부연 없이.
예시: "셀프 포토 스튜디오 FGI" / "20대 뷰티 소비 패턴 분석"
"""


async def generate_project_title(brief: dict) -> str:
    """브리프에서 LLM이 한 줄 프로젝트 제목을 생성한다."""
    background = brief.get("background", "")
    objective = brief.get("objective", "")
    category = brief.get("category", "")
    target = brief.get("target_customer", "")

    prompt = (
        f"연구 배경: {background}\n"
        f"연구 목적: {objective}\n"
        f"카테고리: {category}\n"
        f"타깃 고객: {target}"
    )

    try:
        response = await asyncio.wait_for(
            _client.responses.create(
                model="gpt-4o-mini",
                instructions=_TITLE_PROMPT,
                input=prompt,
                temperature=0.5,
            ),
            timeout=10.0,
        )
        title = (getattr(response, "output_text", "") or "").strip().strip('"').strip("'")
        return title[:50] if title else background[:30]
    except Exception:
        return background[:30] or "새 연구 프로젝트"
