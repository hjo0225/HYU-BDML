"""회의 시뮬레이션 라우터"""
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from models.schemas import MeetingRequest
from services.meeting_service import run_meeting

router = APIRouter(prefix="/api")


@router.post("/meeting")
async def meeting_endpoint(req: MeetingRequest):
    """Phase 4: 회의 시뮬레이션 (SSE)"""

    async def event_stream():
        async for msg in run_meeting(req.agents, req.topic, req.research_context):
            yield f"data: {msg.model_dump_json()}\n\n"
        yield f'data: {json.dumps({"type": "done"})}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
