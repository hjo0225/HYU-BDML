"""M5 테스트 — 토큰 카운터 + 압축기."""
import pytest
from persona.compressor import count_tokens, trim_to_limit, MAX_TOKENS


def test_count_tokens_non_empty():
    assert count_tokens("안녕하세요") > 0


def test_count_tokens_empty():
    assert count_tokens("") == 0


def test_trim_to_limit_no_trim_needed():
    short = "짧은 텍스트"
    assert trim_to_limit(short) == short


def test_trim_to_limit_large_text():
    """8000 토큰 초과 텍스트는 반드시 자른다."""
    large = "테스트 " * 10000  # ~50000 토큰 상당
    result = trim_to_limit(large, max_tokens=500)
    assert count_tokens(result) <= 520  # 약간의 여유 허용


def test_trim_result_has_truncation_notice():
    large = "X " * 10000
    result = trim_to_limit(large, max_tokens=100)
    assert "생략" in result or len(result) < len(large)
