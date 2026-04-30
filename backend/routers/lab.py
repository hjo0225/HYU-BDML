"""실험실(Lab) — 게스트 공개 라우터.

- 인증 의존성 없음 (`/api/lab/*` 전체 공개).
- IP 단위 일일 메시지 30회 한도 (인메모리 카운터).
- Twin-2K-500 데이터셋(`Panel.source='twin2k500'`)만 사용.

ADR: docs/adr/0005-lab-twin-2k-500-integration.md
"""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from models.schemas import LabChatRequest, LabTwin, LabTwinsResponse
from services.lab_service import list_twins, stream_chat


router = APIRouter(prefix="/api/lab", tags=["lab"])


# ── IP 단위 일일 rate limit (인메모리) ─────────────────────────────────────
DAILY_LIMIT = 30  # 메시지/IP/일
WINDOW_SEC = 24 * 3600

# {ip: [timestamp, ...]} — 24시간 이내 메시지 시점들
_request_log: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    """Cloud Run 등 프록시 환경 호환 — X-Forwarded-For 우선."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str) -> tuple[bool, int]:
    """True/False + 남은 쿨다운(초). 한도 초과 시 (False, seconds)."""
    now = time.time()
    cutoff = now - WINDOW_SEC
    log = _request_log[ip]
    # 24시간 이전 기록 제거
    log[:] = [t for t in log if t >= cutoff]
    if len(log) >= DAILY_LIMIT:
        oldest = log[0]
        return False, int(oldest + WINDOW_SEC - now)
    log.append(now)
    return True, 0


# ── 엔드포인트 ────────────────────────────────────────────────────────────


@router.get("/twins", response_model=LabTwinsResponse)
async def get_twins() -> LabTwinsResponse:
    """Lab 페이지에 표시할 Twin 페르소나 목록 (시범 50명)."""
    rows = await list_twins(limit=50)
    return LabTwinsResponse(twins=[LabTwin(**r) for r in rows])


@router.post("/chat")
async def post_chat(req: LabChatRequest, request: Request):
    """1:1 메신저 채팅 — SSE 스트리밍."""
    if not req.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="message는 비어 있을 수 없습니다",
        )

    ip = _client_ip(request)
    ok, remaining = _check_rate_limit(ip)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "reason": "rate_limit",
                "remaining_seconds": remaining,
                "limit_per_day": DAILY_LIMIT,
            },
        )

    history = [t.model_dump() for t in req.history]

    async def event_stream():
        async for chunk in stream_chat(req.twin_id, history, req.message):
            if await request.is_disconnected():
                break
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
