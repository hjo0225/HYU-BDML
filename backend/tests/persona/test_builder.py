"""M5 테스트 — 페르소나 빌더."""
import json
import os
import pytest
from persona.builder import build_persona
from persona.compressor import count_tokens, trim_to_limit
from scoring.pipeline import score_all, extract_qualitative, extract_demographics


@pytest.fixture
def sample_data():
    fixture_path = os.path.join(
        os.path.dirname(__file__), "..", "_fixtures", "sample_response_kr_001.json"
    )
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def persona_components(sample_data):
    responses = sample_data["responses"]
    params = score_all(responses)
    qualitative = extract_qualitative(sample_data)
    demographics = extract_demographics(sample_data)
    return params, qualitative, demographics


def test_build_persona_returns_string(persona_components):
    params, qual, demo = persona_components
    prompt = build_persona(params, qual, demo)
    assert isinstance(prompt, str)
    assert len(prompt) > 100


def test_build_persona_contains_cite_markers(persona_components):
    """CITE 마커가 포함되어야 한다."""
    params, qual, demo = persona_components
    prompt = build_persona(params, qual, demo)
    assert "[CITE:L1]" in prompt
    assert "[CITE:L2]" in prompt


def test_build_persona_contains_qualitative(persona_components):
    """정성 서술이 포함되어야 한다."""
    params, qual, demo = persona_components
    prompt = build_persona(params, qual, demo)
    assert qual["self_aspire"][:10] in prompt


def test_build_persona_within_token_limit(persona_components):
    params, qual, demo = persona_components
    prompt = build_persona(params, qual, demo, max_tokens=8000)
    assert count_tokens(prompt) <= 8000


def test_trim_to_limit_reduces_tokens():
    long_text = "A" * 100000
    trimmed = trim_to_limit(long_text, max_tokens=100)
    assert count_tokens(trimmed) <= 100 + 20  # 약간의 여유
