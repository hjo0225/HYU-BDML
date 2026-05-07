"""입력 JSON 스키마 검증 — 6-LENS_MAPPING.md 규격 준수 확인."""
from __future__ import annotations

from .exceptions import MissingResponseError
from .mapping import LENS_DEFINITIONS, ScaleDefinition

# 정성 응답 키 (필수 아님 — 없으면 빈 문자열로 처리)
QUALITATIVE_KEYS = ["L3-4.Q1", "L3-4.Q2", "L3-4.Q3"]
DICTATOR_THOUGHT_KEY = "qualitative.dictator_reasoning"

# 통제 변수 — Demographics 는 responses 외부에 저장되므로 제외
_EXCLUDED_SCALE_IDS = {"C-1", "L3-4"}

# 필수 입력 키 전체 목록
REQUIRED_RESPONSE_KEYS: list[str] = []
for _sd in LENS_DEFINITIONS.values():
    if _sd.scale_id in _EXCLUDED_SCALE_IDS:
        continue
    REQUIRED_RESPONSE_KEYS.extend(_sd.input_keys)


def validate_input(data: dict) -> dict:
    """입력 dict 검증 후 `responses` sub-dict 반환.

    Args:
        data: 최상위 dict. `responses` 키 아래에 척도별 응답이 있어야 함.

    Returns:
        responses dict (정성 포함).

    Raises:
        MissingResponseError: 필수 키 누락 시.
    """
    responses: dict = data.get("responses", {})
    missing = [k for k in REQUIRED_RESPONSE_KEYS if k not in responses]
    if missing:
        raise MissingResponseError(missing)
    return responses
