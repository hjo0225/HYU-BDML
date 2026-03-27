"""
FastAPI 엔드포인트 — Phase 2 Persona API
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from module.persona.generator import (
    _personas_dir,
    _sanitize_name,
    step_a_derive_roles,
    step_a_revise_roles,
    step_b_generate_personas,
)
from module.persona.models import PersonaApproveRequest, RolesOutput

router = APIRouter(prefix="/persona", tags=["persona"])

# 프로젝트별 대기 중인 역할 목록
_pending_roles: dict[str, RolesOutput] = {}


@router.post("/{project_name}/generate")
async def generate_roles(project_name: str):
    """Step A: Phase 1 결과를 로드하여 역할 목록을 도출."""
    try:
        roles = await step_a_derive_roles(project_name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    key = _sanitize_name(project_name)
    _pending_roles[key] = roles
    return roles.model_dump()


@router.post("/{project_name}/approve")
async def approve_roles(project_name: str, req: PersonaApproveRequest):
    """
    승인이면 Step B 실행 후 페르소나 카드 반환.
    수정이면 역할 업데이트 후 새 역할 목록 반환.
    """
    key = _sanitize_name(project_name)
    current_roles = _pending_roles.get(key)
    if current_roles is None:
        raise HTTPException(
            status_code=404,
            detail="대기 중인 역할 목록이 없습니다. 먼저 /persona/{project_name}/generate를 호출하세요.",
        )

    if req.approved:
        output = await step_b_generate_personas(project_name, current_roles)
        del _pending_roles[key]
        return output.model_dump()

    if not req.feedback:
        raise HTTPException(status_code=400, detail="approved=false일 때 feedback은 필수입니다.")

    revised = await step_a_revise_roles(project_name, current_roles, req.feedback)
    _pending_roles[key] = revised
    return revised.model_dump()


@router.get("/{project_name}/result")
async def get_persona_result(project_name: str):
    """저장된 페르소나 카드 조회."""
    pdir = _personas_dir(project_name)
    path = pdir / "persona_cards.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="페르소나 결과가 없습니다.")
    return json.loads(path.read_text(encoding="utf-8"))
