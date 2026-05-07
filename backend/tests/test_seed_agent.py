"""M7 테스트 — seed_agent dry-run smoke test."""
import asyncio
import json
import os
import pytest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lenses.parser import validate_input
from scoring.pipeline import score_all, extract_qualitative, extract_demographics
from persona.builder import build_persona
from persona.compressor import count_tokens


FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "_fixtures", "sample_response_kr_001.json")


@pytest.fixture
def sample_data():
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_fixture_file_exists():
    assert os.path.exists(FIXTURE_PATH), "fixture 파일 없음"


def test_validate_input_passes(sample_data):
    """fixture 가 validate_input 통과해야 한다."""
    responses = validate_input(sample_data)
    assert isinstance(responses, dict)
    assert len(responses) > 50


def test_score_all_succeeds(sample_data):
    """score_all 이 예외 없이 완료되어야 한다."""
    responses = validate_input(sample_data)
    params = score_all(responses)
    assert isinstance(params, dict)
    assert len(params) >= 24  # 최소 24개 키


def test_persona_prompt_within_8k_tokens(sample_data):
    """persona_full_prompt 가 8000 tokens 이내여야 한다."""
    responses = validate_input(sample_data)
    params = score_all(responses)
    qualitative = extract_qualitative(sample_data)
    demographics = extract_demographics(sample_data)
    prompt = build_persona(params, qualitative, demographics)
    tokens = count_tokens(prompt)
    assert tokens < 8000, f"persona_full_prompt 가 {tokens} tokens — 8000 초과"


def test_memory_count_at_least_9(sample_data):
    """메모리가 9개 이상이어야 한다 (7 lens + 인구통계 + 3 qualitative)."""
    from scripts.seed_agent import _build_memory_texts
    responses = validate_input(sample_data)
    params = score_all(responses)
    qualitative = extract_qualitative(sample_data)
    demographics = extract_demographics(sample_data)
    memories = _build_memory_texts(params, qualitative, demographics)
    assert len(memories) >= 9, f"메모리 {len(memories)}개 — 9개 미만"


def test_dry_run_no_db_write(sample_data, tmp_path):
    """dry-run 은 DB INSERT 없이 완료되어야 한다."""
    import os
    os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/test.db")

    from scripts.seed_agent import _process_record

    async def _run():
        result = await _process_record(
            record=sample_data,
            project_id="00000000-0000-0000-0000-000000000000",
            dry_run=True,
            refresh_prompt=False,
        )
        return result

    result = asyncio.run(_run())
    assert result["status"] == "dry-run"
    assert result["token_count"] < 8000
