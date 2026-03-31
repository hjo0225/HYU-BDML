"""회의 시뮬레이션 라우터"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from models.schemas import MeetingRequest
from services.meeting_service import run_meeting_stream

router = APIRouter(prefix="/api")


@router.post("/meeting")
async def meeting_endpoint(req: MeetingRequest):
    """Phase 4: 회의 시뮬레이션 (SSE 토큰 스트리밍)"""

    async def event_stream():
        async for chunk in run_meeting_stream(req.agents, req.topic, req.research_context, req.max_rounds):
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
