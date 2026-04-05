"""토큰 사용량 조회 라우터 (관리자 전용)"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import ActivityLog, User, get_db
from services.auth_service import get_current_user, require_admin
from services.usage_tracker import tracker

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("")
async def get_usage(current_user: User = Depends(get_current_user)):
    """누적 토큰 사용량 조회 (인메모리 요약 - 현재 세션)."""
    return tracker.summary()


@router.post("/reset")
async def reset_usage(current_user: User = Depends(require_admin)):
    """사용량 기록 초기화 (관리자 전용)."""
    tracker.reset()
    return {"status": "reset"}


@router.get("/history")
async def get_history(
    limit: int = 100,
    action: str | None = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """활동 로그 이력 조회 (관리자 전용)."""
    query = select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(limit)
    if action:
        query = query.where(ActivityLog.action == action)

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "project_id": log.project_id,
            "action": log.action,
            "model": log.model,
            "input_tokens": log.input_tokens,
            "output_tokens": log.output_tokens,
            "cost_usd": float(log.cost_usd or 0),
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.get("/stats")
async def get_stats(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """기능별/유저별 집계 통계 (관리자 전용)."""
    # 기능별 집계
    by_action = await db.execute(
        select(
            ActivityLog.action,
            func.count(ActivityLog.id).label("calls"),
            func.sum(ActivityLog.input_tokens).label("input_tokens"),
            func.sum(ActivityLog.output_tokens).label("output_tokens"),
            func.sum(ActivityLog.cost_usd).label("cost_usd"),
        ).group_by(ActivityLog.action)
    )

    # 유저별 집계
    by_user = await db.execute(
        select(
            ActivityLog.user_id,
            func.count(ActivityLog.id).label("calls"),
            func.sum(ActivityLog.cost_usd).label("cost_usd"),
        )
        .where(ActivityLog.user_id.isnot(None))
        .group_by(ActivityLog.user_id)
    )

    return {
        "by_action": [
            {
                "action": row.action,
                "calls": row.calls,
                "input_tokens": int(row.input_tokens or 0),
                "output_tokens": int(row.output_tokens or 0),
                "cost_usd": float(row.cost_usd or 0),
            }
            for row in by_action
        ],
        "by_user": [
            {
                "user_id": row.user_id,
                "calls": row.calls,
                "cost_usd": float(row.cost_usd or 0),
            }
            for row in by_user
        ],
    }
