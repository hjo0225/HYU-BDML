"""LLM Chat Completion 헬퍼 — V1·V4 평가 + 향후 1:1 대화·FGI 공유.

OpenAI gpt-4o 동기 SDK 를 asyncio.to_thread 로 감싸 비동기 컨텍스트에서도
event loop 를 막지 않는다. 합성/mock 모드는 OPENAI_API_KEY 미설정 시 자동
폴백 — 결정적이라 테스트 안정.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from typing import AsyncGenerator, Optional

import openai

_DEFAULT_MODEL = os.getenv("CHAT_MODEL", "gpt-4.1-mini")

# OpenAI 호출 stall 방어 (2026-05-30). 타임아웃 미설정 시 SDK 기본 600초라, 호출이 멈추면
# FGI SSE 가 그 동안 무송신이 되어 연결이 끊긴다(heartbeat 와 별개로 발화 자체가 지연).
# 스트리밍에선 이 값이 청크 사이 read 타임아웃으로 동작 → 토큰이 N초간 안 오면 에러로 끊고
# 상위(_produce)가 그 에러를 스트림으로 전달, 모더레이터 경로는 fallback 으로 복구한다.
# env 로 조정 가능. 재시도는 연결/일시 오류에 한해 SDK 가 처리.
_OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "60"))
_OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "2"))


def _has_api_key() -> bool:
    key = os.getenv("OPENAI_API_KEY", "")
    return bool(key and not key.startswith("dummy") and not key.startswith("test"))


def _mock_answer(system: str, user: str) -> str:
    """결정적 mock — system+user 의 sha256 으로 길이 고정 텍스트 생성.

    실제 의미는 없지만 동일 입력에 대해 항상 같은 답을 돌려주므로 V1 cosine
    비교가 결정적으로 동작한다. 한국어 더미 문장 풀에서 회전.
    """
    pool = [
        "저는 이 질문에 대해 신중하게 생각해 보았습니다.",
        "제 평소 가치관과 일치하는 방향으로 답하겠습니다.",
        "가족과 안정을 우선시하는 편이라 다음과 같이 답할 것 같습니다.",
        "단기적인 이익보다 장기적인 만족을 추구합니다.",
        "주변 사람들의 의견을 듣고 합리적으로 판단하려고 합니다.",
    ]
    digest = hashlib.sha256((system + "||" + user).encode("utf-8")).digest()
    start = digest[0] % len(pool)
    n = 2 + (digest[1] % 3)  # 2~4 문장
    sentences = [pool[(start + i) % len(pool)] for i in range(n)]
    return " ".join(sentences) + f" (응답 길이 시드={digest[:4].hex()})"


async def chat_completion(
    *,
    system: str,
    user: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 400,
    mock: Optional[bool] = None,
) -> str:
    """단일 chat completion.

    Args:
        system: 시스템 프롬프트 (페르소나).
        user: 사용자 질문.
        model: OpenAI 모델 (기본 CHAT_MODEL env 또는 gpt-4o).
        temperature, max_tokens: 표준 인자.
        mock: True=강제 mock, False=강제 실 API, None=API 키 유무 자동.

    Returns:
        에이전트 답변 텍스트.
    """
    use_mock = mock if mock is not None else not _has_api_key()
    if use_mock:
        return _mock_answer(system, user)

    def _call() -> str:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"),
                               timeout=_OPENAI_TIMEOUT, max_retries=_OPENAI_MAX_RETRIES)
        res = client.chat.completions.create(
            model=model or _DEFAULT_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (res.choices[0].message.content or "").strip()

    return await asyncio.to_thread(_call)


async def stream_chat(
    *,
    system: str,
    messages: list[dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 800,
    mock: Optional[bool] = None,
) -> AsyncGenerator[str, None]:
    """멀티턴 chat completion 토큰 스트리밍.

    1:1 대화·FGI 발화 공유. system(페르소나) + messages(이전 user/assistant
    history + 새 user) 를 받아 텍스트 델타를 순차 yield 한다.

    Args:
        system: 시스템 프롬프트 (페르소나 — package 는 ~30k 토큰 가능, gpt-4o 128k).
        messages: [{role:'user'|'assistant', content:str}, ...] 시간순.
        model, temperature, max_tokens: 표준 인자.
        mock: True=강제 mock, False=강제 실 API, None=API 키 유무 자동.

    Yields:
        응답 텍스트 델타 (조각).
    """
    use_mock = mock if mock is not None else not _has_api_key()
    if use_mock:
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        text = _mock_answer(system, last_user)
        # 스트리밍처럼 보이도록 어절 단위로 흘려보낸다.
        for chunk in text.split(" "):
            yield chunk + " "
            await asyncio.sleep(0)
        return

    # OpenAI 동기 stream 을 큐로 받아 async 로 중계 (event loop 비차단).
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    _SENTINEL = object()

    def _produce() -> None:
        try:
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"),
                                   timeout=_OPENAI_TIMEOUT, max_retries=_OPENAI_MAX_RETRIES)
            stream = client.chat.completions.create(
                model=model or _DEFAULT_MODEL,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                messages=[{"role": "system", "content": system}, *messages],
            )
            for event in stream:
                delta = event.choices[0].delta.content if event.choices else None
                if delta:
                    loop.call_soon_threadsafe(queue.put_nowait, delta)
        except Exception as e:  # noqa: BLE001 — 에러도 스트림으로 전달
            loop.call_soon_threadsafe(queue.put_nowait, RuntimeError(str(e)))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

    asyncio.get_running_loop().run_in_executor(None, _produce)

    while True:
        item = await queue.get()
        if item is _SENTINEL:
            break
        if isinstance(item, Exception):
            raise item
        yield item
