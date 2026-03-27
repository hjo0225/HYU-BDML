"""Phase 3 Pydantic 데이터 모델."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class MeetingEntry(BaseModel):
    """회의록 1건."""

    round: int
    speaker_id: str
    speaker_role: str
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    type: str = "utterance"  # "utterance" | "facilitation" | "user_input" | "summary"


class OrchestratorDecision(BaseModel):
    """오케스트레이터 판단 결과."""

    next_speaker_id: str
    facilitation: str
    consensus_reached: bool = False
    consensus_summary: Optional[str] = None
    meeting_status: str = "continue"  # "continue" | "consensus_reached" | "needs_more_discussion"


class MeetingStats(BaseModel):
    """회의 통계."""

    total_rounds: int = 0
    end_reason: str = ""
    participants: list[str] = Field(default_factory=list)
    user_interventions: int = 0


class ConsensusInfo(BaseModel):
    """합의 정보."""

    reached: bool = False
    summary: Optional[str] = None


class FinalReport(BaseModel):
    """회의 최종 보고서."""

    project_name: str
    topic: str
    purpose: str
    meeting_stats: MeetingStats = Field(default_factory=MeetingStats)
    consensus: ConsensusInfo = Field(default_factory=ConsensusInfo)
    key_insights: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    full_transcript: list[MeetingEntry] = Field(default_factory=list)
    summary_report: str = ""
