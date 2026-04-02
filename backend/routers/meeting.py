"""회의 시뮬레이션 SSE 엔드포인트."""
import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from models.schemas import MeetingRequest
from services.meeting_service import run_meeting_stream

router = APIRouter(prefix="/api")


@router.post("/meeting")
async def meeting_endpoint(req: MeetingRequest, request: Request):
    """회의 시뮬레이션을 SSE로 스트리밍한다."""

    async def event_stream():
        try:
            async for chunk in run_meeting_stream(
                req.agents,
                req.topic,
                req.research_context,
                req.max_rounds,
            ):
                # 브라우저 연결이 끊긴 뒤에도 생성기를 계속 돌리면 불필요한 토큰 비용이 생긴다.
                if await request.is_disconnected():
                    break
                yield chunk
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
