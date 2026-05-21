"""에이전트 헬퍼 — 카드용 short summary 합성, persona_params 필터 표현식 빌더.

목적: UI 카드에 표시할 1~2 줄 요약(persona_params + scratch 인구통계 결합) 과
6-Lens 범위 필터 SQL 표현식 생성 책임을 라우터에서 분리.
"""
from __future__ import annotations

import json
from typing import Any

from database import Agent


def _parse_jsonish(value: Any) -> dict[str, Any] | None:
    """SQLite 폴백(JSON Text) ↔ PostgreSQL JSONB 양쪽에서 dict 로 정규화."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def short_summary(agent: Agent) -> str:
    """UI 카드용 한국어 짧은 요약 (1~2 줄, ≤ 90자 목표).

    우선순위: intro_ko → scratch 인구통계 + 대표 lens 수치 → 기본 텍스트.
    """
    if agent.intro_ko:
        return agent.intro_ko.strip()

    scratch = _parse_jsonish(getattr(agent, "scratch", None)) or {}
    params = _parse_jsonish(getattr(agent, "persona_params", None)) or {}

    pieces: list[str] = []
    demo_bits = [
        scratch.get("age_range") or scratch.get("age"),
        scratch.get("gender"),
        scratch.get("employment") or scratch.get("occupation"),
    ]
    demo = " · ".join(b for b in demo_bits if b)
    if demo:
        pieces.append(demo)

    lens_bits: list[str] = []
    ra = params.get("l1.risk_aversion")
    if isinstance(ra, (int, float)):
        lens_bits.append(f"위험회피 {ra:.2f}")
    mx = params.get("l2.maximization")
    if isinstance(mx, (int, float)):
        lens_bits.append(f"극대화 {mx:.1f}/5")
    if lens_bits:
        pieces.append(" / ".join(lens_bits))

    return " — ".join(pieces) if pieces else "프로필 요약 준비 중"


def demographics(agent: Agent) -> tuple[str | None, str | None]:
    """카드/필터용 인구통계 (age_range, gender) — scratch 에서 추출.

    scratch.age_range 우선, 없으면 scratch.age. gender 는 그대로.
    """
    scratch = _parse_jsonish(getattr(agent, "scratch", None)) or {}
    age = scratch.get("age_range") or scratch.get("age")
    gender = scratch.get("gender")
    return (
        str(age).strip() if age else None,
        str(gender).strip() if gender else None,
    )


def parse_params_filter(raw: str | None) -> list[tuple[str, float, float]]:
    """`l1.risk_aversion:0.3-0.7,l2.maximization:3.0-5.0` → [(key, lo, hi), ...]"""
    if not raw:
        return []
    out: list[tuple[str, float, float]] = []
    for token in raw.split(","):
        token = token.strip()
        if not token or ":" not in token:
            continue
        key, _, rng = token.partition(":")
        if "-" not in rng:
            continue
        lo_s, _, hi_s = rng.partition("-")
        try:
            out.append((key.strip(), float(lo_s), float(hi_s)))
        except ValueError:
            continue
    return out


def agent_passes_params_filter(agent: Agent, ranges: list[tuple[str, float, float]]) -> bool:
    """ORM-side 메모리 필터 — DB 가 JSONB path 쿼리 미지원 (SQLite) 일 때 폴백."""
    if not ranges:
        return True
    params = _parse_jsonish(agent.persona_params) or {}
    for key, lo, hi in ranges:
        v = params.get(key)
        if not isinstance(v, (int, float)):
            return False
        if v < lo or v > hi:
            return False
    return True
