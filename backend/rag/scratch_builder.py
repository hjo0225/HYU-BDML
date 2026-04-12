"""
scratch_builder.py
pandas row + codebook → scratch dict (LLM 호출 없음)
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

# 현재 연도 (나이 계산 기준)
CURRENT_YEAR = 2026

# dim_* 컬럼 중 0~1 비율인 것만 strong/weak 판정에 사용
# (dim_spending_level, dim_spatial_mobility, dim_app_intensity_hr, dim_place_diversity 는 raw 수치라 제외)
DIM_RATIO_COLS = [
    "dim_night_owl",
    "dim_gamer",
    "dim_social_diner",
    "dim_drinker",
    "dim_shopper",
    "dim_health",
    "dim_entertainment",
    "dim_weekend_oriented",
]

DIM_LABELS = {
    "dim_night_owl": "야행성",
    "dim_gamer": "게임 몰입",
    "dim_social_diner": "사교적 외식",
    "dim_drinker": "음주 빈도",
    "dim_shopper": "쇼핑 활동",
    "dim_health": "건강 지향",
    "dim_entertainment": "여가/오락",
    "dim_weekend_oriented": "주말 활동",
}

# 전체 3,378명 분포 기반 (P75 = strong, P25 = weak)
DIM_STRONG_THRESHOLDS = {
    "dim_night_owl":        0.1645,
    "dim_gamer":            0.1296,
    "dim_social_diner":     0.2560,
    "dim_drinker":          0.0321,
    "dim_shopper":          0.2631,
    "dim_health":           0.0156,
    "dim_entertainment":    0.0372,
    "dim_weekend_oriented": 0.2895,
}

DIM_WEAK_THRESHOLDS = {
    "dim_night_owl":        0.0960,
    "dim_gamer":            0.0051,
    "dim_social_diner":     0.1689,
    "dim_drinker":          0.0162,
    "dim_shopper":          0.1143,
    "dim_health":           0.0052,
    "dim_entertainment":    0.0046,
    "dim_weekend_oriented": 0.2240,
}

# 생애사건 컬럼 → 사건명
LIFE_EVENT_MAP = {
    "ps_X0025": "입학",
    "ps_X0026": "신규입사/취업",
    "ps_X0027": "이직",
    "ps_X0028": "결혼",
    "ps_X0029": "자녀출산",
    "ps_X0030": "이사",
    "ps_X0031": "내집마련",
    "ps_X0032": "동거가족의독립",
    "ps_X0033": "창업",
    "ps_X0034": "폐업",
    "ps_X0035": "퇴직/은퇴",
    "ps_X0036": "장기입원/수술/질병진단",
    "ps_X0037": "가족의사망",
}

# 자녀 연령대 컬럼 → 라벨
CHILDREN_MAP = {
    "ps_Y0002": "영아",
    "ps_Y0003": "유아",
    "ps_Y0004": "초등",
    "ps_Y0005": "중등",
    "ps_Y0006": "고등",
}


def _safe_val(row: dict, col: str) -> Any:
    """row에서 값 추출. NaN이면 None 반환."""
    v = row.get(col)
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _decode(row: dict, col: str, codebook: dict) -> str | None:
    """ps_ 접두사 포함 컬럼명에서 값을 읽어 codebook으로 자연어 변환."""
    raw = _safe_val(row, col)
    if raw is None:
        return None

    # codebook key는 접두사 없는 변수명
    var_key = col.replace("ps_", "") if col.startswith("ps_") else col
    entry = codebook.get(var_key)
    if entry is None:
        return None

    value_map = entry.get("value_map")
    if value_map is None:
        return str(raw) if raw != "" else None

    try:
        code = int(float(raw))
    except (ValueError, TypeError):
        return None

    return value_map.get(code) or value_map.get(str(code))


def _get_life_events(row: dict) -> list[str]:
    events = []
    for col, name in LIFE_EVENT_MAP.items():
        v = _safe_val(row, col)
        if v is not None:
            try:
                if int(float(v)) == 1:
                    events.append(name)
            except (ValueError, TypeError):
                pass
    return events


def _get_children(row: dict) -> list[str]:
    children = []
    for col, label in CHILDREN_MAP.items():
        v = _safe_val(row, col)
        if v is not None:
            try:
                if int(float(v)) == 1:
                    children.append(label)
            except (ValueError, TypeError):
                pass
    return children


def _get_traits(row: dict) -> tuple[list[str], list[str]]:
    strong, weak = [], []
    for col in DIM_RATIO_COLS:
        v = _safe_val(row, col)
        if v is None:
            continue
        try:
            score = float(v)
        except (ValueError, TypeError):
            continue
        label = DIM_LABELS[col]
        if score >= DIM_STRONG_THRESHOLDS[col]:
            strong.append(label)
        elif score <= DIM_WEAK_THRESHOLDS[col]:
            weak.append(label)
    return strong, weak


def build_scratch(row: dict, codebook: dict) -> dict:
    """
    pandas Series 또는 dict 형태의 row와 codebook을 받아 scratch dict 반환.
    NaN/매핑실패 필드는 결과에서 제외.
    """
    scratch: dict[str, Any] = {}

    # 필수 필드
    panel_id = _safe_val(row, "PANEL_ID")
    if panel_id is not None:
        scratch["panel_id"] = str(panel_id)

    cluster = _safe_val(row, "cluster")
    if cluster is not None:
        try:
            scratch["cluster"] = int(float(cluster))
        except (ValueError, TypeError):
            pass

    # 나이 / 출생년도
    birth_raw = _safe_val(row, "ps_X0002")
    if birth_raw is not None:
        try:
            birth_year = int(float(birth_raw))
            scratch["birth_year"] = birth_year
            scratch["age"] = CURRENT_YEAR - birth_year
        except (ValueError, TypeError):
            pass

    # 인구통계
    for field, col in [
        ("gender", "ps_X0001"),
        ("marital_status", "ps_X0003"),
        ("education", "ps_X0004"),
        ("occupation", "ps_X0005"),
        ("region", "ps_X0024"),
    ]:
        decoded = _decode(row, col, codebook)
        if decoded is not None:
            scratch[field] = decoded

    # 가구 정보
    for field, col in [
        ("household_size", "ps_Y0001"),
        ("household_income", "ps_Y0008"),
        ("house_type", "ps_Y0009"),
        ("house_ownership", "ps_Y0010"),
        ("house_size", "ps_Y0011"),
    ]:
        decoded = _decode(row, col, codebook)
        if decoded is not None:
            scratch[field] = decoded

    # 자녀 연령대
    children = _get_children(row)
    scratch["children_in_household"] = children

    # 생애사건
    events = _get_life_events(row)
    scratch["recent_life_events"] = events

    # 행동 차원 strong/weak
    strong, weak = _get_traits(row)
    scratch["strong_traits"] = strong
    scratch["weak_traits"] = weak

    # 소비/패션/투자 스타일
    for field, col in [
        ("fashion_style", "ps_E0040"),
        ("consumption_style", "ps_I0006"),
        ("investment_style", "ps_H0015"),
    ]:
        decoded = _decode(row, col, codebook)
        if decoded is not None:
            scratch[field] = decoded

    return scratch
