"""데모 진입 라우터 (plan 0008).

POST /api/demo/session  무인증 — 데모 user/project/에이전트를 보장하고 데모 토큰 발급.

로그인 없이 '데모 이용해보기'로 들어온 사용자가 실제 백엔드(대화·평가·FGI)를
데모 프로젝트 스코프에서 그대로 사용하게 한다.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.schemas import UserOut
from services import demo_service
from services.auth_service import create_access_token

router = APIRouter(tags=["demo"])


@router.post("/api/demo/session")
async def start_demo_session(db: AsyncSession = Depends(get_db)):
    """데모 세션 시작 — 방문마다 격리된 임시 데모 user/project 생성 후 토큰 + 프로젝트 id 반환.

    여러 사용자가 동시에 데모를 써도 대화·FGI·평가가 섞이지 않도록 세션마다 독립 스코프를 둔다
    (plan 0016). 오래된 임시 데모는 TTL 로 정리된다.
    """
    result = await demo_service.create_ephemeral_demo(db)
    user = result["user"]
    token = create_access_token(user.id, user.email, user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": UserOut.model_validate(user),
        "project_id": result["project_id"],
        "n_agents": result["n_agents"],
    }
