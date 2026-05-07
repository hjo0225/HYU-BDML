"""페르소나 프롬프트 토큰 카운트 + 압축."""
from __future__ import annotations

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))

except ImportError:
    def count_tokens(text: str) -> int:
        """tiktoken 없으면 문자 수 / 3 근사치."""
        return len(text) // 3


MAX_TOKENS = 8000


def trim_to_limit(text: str, max_tokens: int = MAX_TOKENS) -> str:
    """텍스트를 max_tokens 이내로 자른다.

    섹션 구분자([SECTION])를 기준으로 말미 섹션부터 제거.
    """
    if count_tokens(text) <= max_tokens:
        return text

    lines = text.splitlines()
    while lines and count_tokens("\n".join(lines)) > max_tokens:
        lines.pop()

    trimmed = "\n".join(lines)
    trimmed += "\n\n[일부 내용이 토큰 제한으로 생략됨]"
    return trimmed
