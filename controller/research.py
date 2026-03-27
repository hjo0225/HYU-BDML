"""
FastAPI 엔드포인트 — Phase 1 Research API
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from module.research.models import ApproveRequest, InputA, InputB, ResearchOutput
from module.research.pipeline import (
    _project_dir,
    _sanitize_name,
    run_pipeline,
    run_step0,
    run_step0_revise,
    save_input_b,
)

router = APIRouter(prefix="/research", tags=["research"])

# 프로젝트별 임시 B를 메모리에 보관 (승인 전까지)
_pending_b: dict[str, InputB] = {}


@router.post("/start", response_model=InputB)
async def start_research(input_a: InputA):
    """Step 0 실행: A → B 변환 후 사용자 확인용 B를 반환."""
    input_b = await run_step0(input_a)
    key = _sanitize_name(input_a.project_name)
    _pending_b[key] = input_b
    return input_b


@router.post("/{project_name}/approve")
async def approve_research(project_name: str, req: ApproveRequest):
    """
    승인이면 Step 1~3 실행 후 ResearchOutput 반환.
    수정이면 B 업데이트 후 새 B 반환.
    """
    key = _sanitize_name(project_name)
    current_b = _pending_b.get(key)
    if current_b is None:
        raise HTTPException(status_code=404, detail="해당 프로젝트의 대기 중인 조사 계획이 없습니다.")

    if req.approved:
        save_input_b(project_name, current_b)
        output = await run_pipeline(project_name, current_b)
        _save_output(project_name, output)
        del _pending_b[key]
        return output.model_dump()

    if not req.feedback:
        raise HTTPException(status_code=400, detail="approved=false일 때 feedback은 필수입니다.")

    revised_b = await run_step0_revise(current_b, req.feedback)
    _pending_b[key] = revised_b
    return revised_b.model_dump()


@router.get("/{project_name}/result")
async def get_result(project_name: str):
    """저장된 조사 결과를 조회."""
    pdir = _project_dir(project_name)
    result_path = pdir / "output.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="조사 결과가 없습니다.")
    return json.loads(result_path.read_text(encoding="utf-8"))


def _save_output(project_name: str, output: ResearchOutput) -> None:
    """ResearchOutput을 raw/{project_name}/research/output.json에 저장."""
    pdir = _project_dir(project_name)
    pdir.mkdir(parents=True, exist_ok=True)
    data = output.model_dump()
    for s in data.get("sources", []):
        s.pop("content", None)
    (pdir / "output.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
