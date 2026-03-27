"""
FastAPI 엔드포인트 — Phase 3 Meeting API (WebSocket + REST)
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from module.meeting.session import (
    MeetingSession,
    _data_dir,
    _meeting_dir,
    _sanitize_name,
    load_persona_output,
)

router = APIRouter(prefix="/meeting", tags=["meeting"])

# 활성 세션 추적 (프로젝트당 1개)
_active_sessions: dict[str, MeetingSession] = {}


@router.websocket("/{project_name}/ws")
async def meeting_websocket(websocket: WebSocket, project_name: str):
    """WebSocket 회의 세션. 시작 ~ 종료 전부 이 연결에서 처리."""
    await websocket.accept()
    key = _sanitize_name(project_name)

    try:
        # Phase 2 결과 로드
        persona_output = load_persona_output(project_name)
    except FileNotFoundError as e:
        await websocket.send_json({"event": "error", "detail": str(e)})
        await websocket.close()
        return

    # start_meeting 이벤트 대기
    init_data = await websocket.receive_json()
    if init_data.get("event") != "start_meeting":
        await websocket.send_json({
            "event": "error",
            "detail": "첫 메시지는 {\"event\": \"start_meeting\"}이어야 합니다.",
        })
        await websocket.close()
        return

    max_rounds = init_data.get("max_rounds", 10)

    session = MeetingSession(
        project_name=project_name,
        persona_output=persona_output,
        websocket=websocket,
        max_rounds=max_rounds,
    )
    _active_sessions[key] = session

    try:
        await session.run()
    except WebSocketDisconnect:
        session.is_active = False
        session.end_reason = "connection_lost"
        session.save_session_log()
    finally:
        _active_sessions.pop(key, None)


@router.get("/{project_name}/status")
async def get_meeting_status(project_name: str):
    """현재 회의 상태 조회."""
    key = _sanitize_name(project_name)
    session = _active_sessions.get(key)
    if session is None:
        return {"active": False, "message": "진행 중인 회의가 없습니다."}
    return {
        "active": session.is_active,
        "current_round": session.current_round,
        "max_rounds": session.max_rounds,
        "total_entries": len(session.meeting_log),
    }


@router.get("/{project_name}/transcript")
async def get_transcript(project_name: str):
    """저장된 회의 기록 조회."""
    mdir = _meeting_dir(project_name)
    path = mdir / "session_log.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="회의 기록이 없습니다.")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/{project_name}/result")
async def get_meeting_result(project_name: str):
    """최종 보고서 조회."""
    ddir = _data_dir(project_name)
    path = ddir / "final_report.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="최종 보고서가 없습니다.")
    return json.loads(path.read_text(encoding="utf-8"))
