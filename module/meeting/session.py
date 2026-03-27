"""
회의 세션 — 전체 상태 관리 + 메인 루프.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from fastapi import WebSocket
from openai import AsyncOpenAI

from module.persona.models import PersonaCard, PersonaOutput

from .models import (
    ConsensusInfo,
    FinalReport,
    MeetingEntry,
    MeetingStats,
    OrchestratorDecision,
)
from .orchestrator import decide_next_speaker
from .prompts import LOG_COMPRESS_SYSTEM, SUMMARY_SYSTEM
from .speaker import speak_with_streaming

# ── 설정 ────────────────────────────────────────────────────
LLM_MODEL = "gpt-4o"
RAW_BASE = Path("raw")
DATA_BASE = Path("data")
DEFAULT_MAX_ROUNDS = 10
LOG_COMPRESS_THRESHOLD = 5  # 이 라운드 수 이전 발언은 압축


def _sanitize_name(name: str) -> str:
    return re.sub(r"[^\w가-힣-]", "_", name).strip("_")


def _meeting_dir(project_name: str) -> Path:
    return RAW_BASE / _sanitize_name(project_name) / "meeting"


def _data_dir(project_name: str) -> Path:
    return DATA_BASE / _sanitize_name(project_name)


def _init_openai() -> AsyncOpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.startswith("sk-your"):
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")
    return AsyncOpenAI(api_key=key)


def load_persona_output(project_name: str) -> PersonaOutput:
    """Phase 2 결과 로드."""
    path = RAW_BASE / _sanitize_name(project_name) / "personas" / "persona_cards.json"
    if not path.exists():
        raise FileNotFoundError(f"Phase 2 결과가 없습니다: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return PersonaOutput(**data)


class MeetingSession:
    """회의 세션: 상태 관리 + 메인 루프."""

    def __init__(
        self,
        project_name: str,
        persona_output: PersonaOutput,
        websocket: WebSocket,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
    ):
        self.project_name = project_name
        self.topic = persona_output.topic
        self.purpose = persona_output.purpose
        self.meeting_agenda = persona_output.meeting_agenda
        self.personas = persona_output.personas
        self.discussion_seeds = persona_output.discussion_seeds
        self.websocket = websocket
        self.openai = _init_openai()

        self.meeting_log: list[MeetingEntry] = []
        self.compressed_log: str | None = None  # 압축된 이전 회의록
        self.current_round: int = 0
        self.max_rounds: int = max_rounds
        self.interrupt_flag: bool = False
        self.is_active: bool = False
        self.end_reason: str = ""
        self.consensus_summary: str | None = None

        # 디렉토리 준비
        self._meeting_dir = _meeting_dir(project_name)
        self._rounds_dir = self._meeting_dir / "rounds"
        self._meeting_dir.mkdir(parents=True, exist_ok=True)
        self._rounds_dir.mkdir(parents=True, exist_ok=True)

    # ── 헬퍼 ────────────────────────────────────────────────

    def get_persona(self, speaker_id: str) -> PersonaCard | None:
        for p in self.personas:
            if p.id == speaker_id:
                return p
        return None

    def add_entry(
        self, speaker_id: str, speaker_role: str, content: str, entry_type: str
    ) -> MeetingEntry:
        entry = MeetingEntry(
            round=self.current_round,
            speaker_id=speaker_id,
            speaker_role=speaker_role,
            content=content,
            type=entry_type,
        )
        self.meeting_log.append(entry)
        return entry

    def _get_effective_log(self) -> list[MeetingEntry]:
        """LLM에 전달할 회의록. 오래된 발언은 압축된 요약으로 대체."""
        if self.compressed_log and self.current_round > LOG_COMPRESS_THRESHOLD:
            cutoff = self.current_round - LOG_COMPRESS_THRESHOLD
            recent = [e for e in self.meeting_log if e.round >= cutoff]
            summary_entry = MeetingEntry(
                round=0,
                speaker_id="system",
                speaker_role="시스템",
                content=f"[이전 회의 요약]\n{self.compressed_log}",
                type="summary",
            )
            return [summary_entry] + recent
        return self.meeting_log

    async def _compress_old_log(self) -> None:
        """오래된 회의록을 LLM으로 요약 압축."""
        if self.current_round <= LOG_COMPRESS_THRESHOLD:
            return

        cutoff = self.current_round - LOG_COMPRESS_THRESHOLD
        old_entries = [e for e in self.meeting_log if e.round < cutoff]
        if not old_entries:
            return

        old_text = "\n".join(
            f"[Round {e.round}] {e.speaker_role}: {e.content}" for e in old_entries
        )

        response = await self.openai.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": LOG_COMPRESS_SYSTEM},
                {"role": "user", "content": f"아래 회의록을 핵심만 남겨 압축해주세요.\n\n{old_text}"},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        self.compressed_log = result.get("compressed_log", old_text)

    # ── 저장 ────────────────────────────────────────────────

    def save_round(self) -> None:
        """현재 라운드를 개별 파일로 저장."""
        entries = [e for e in self.meeting_log if e.round == self.current_round]
        path = self._rounds_dir / f"round_{self.current_round:03d}.json"
        path.write_text(
            json.dumps([e.model_dump() for e in entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save_session_log(self) -> None:
        """전체 회의 기록 저장."""
        path = self._meeting_dir / "session_log.json"
        path.write_text(
            json.dumps(
                [e.model_dump() for e in self.meeting_log],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # ── 메인 루프 ───────────────────────────────────────────

    async def run(self) -> None:
        """회의 메인 루프."""
        self.is_active = True

        # 회의 시작 알림
        await self.websocket.send_json({
            "event": "meeting_started",
            "agenda": self.meeting_agenda,
            "personas": [{"id": p.id, "role": p.role} for p in self.personas],
        })

        # 오프닝 발언
        seed = self.discussion_seeds[0] if self.discussion_seeds else ""
        opening = f"오늘 회의 안건은 '{self.topic}'입니다. {seed}"
        self.current_round = 1
        self.add_entry("orchestrator", "진행자", opening, "facilitation")
        await self.websocket.send_json({
            "event": "round_update",
            "round": self.current_round,
            "latest_entry": self.meeting_log[-1].model_dump(),
        })

        # 수신 태스크: 클라이언트 이벤트를 비동기로 처리
        receive_task = asyncio.create_task(self._receive_loop())

        try:
            while self.is_active:
                # 다음 발언자 결정
                if self.interrupt_flag:
                    self.interrupt_flag = False
                    await self._handle_user_turn()
                else:
                    await self._handle_agent_turn()

                # 라운드 저장
                self.save_round()
                self.save_session_log()

                await self.websocket.send_json({
                    "event": "round_update",
                    "round": self.current_round,
                    "latest_entry": self.meeting_log[-1].model_dump(),
                })

                if not self.is_active:
                    break

                # 최대 라운드 확인
                if self.current_round >= self.max_rounds:
                    self.end_reason = "max_rounds_reached"
                    break

                # 회의록 압축 (필요 시)
                await self._compress_old_log()

                self.current_round += 1
        finally:
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass

        # 종료 처리
        self.is_active = False
        if not self.end_reason:
            self.end_reason = "user_ended"

        final_report = await self._summarize_meeting()
        self._save_final_report(final_report)
        self.save_session_log()

        await self.websocket.send_json({
            "event": "meeting_ended",
            "reason": self.end_reason,
            "summary": final_report.model_dump(),
        })

    async def _receive_loop(self) -> None:
        """클라이언트 이벤트 수신 루프 (interrupt, end_meeting)."""
        try:
            while self.is_active:
                data = await self.websocket.receive_json()
                event = data.get("event", "")

                if event == "interrupt":
                    self.interrupt_flag = True
                    await self.websocket.send_json({"event": "interrupt_acknowledged"})

                elif event == "end_meeting":
                    self.is_active = False
                    self.end_reason = "user_ended"

                elif event == "user_message":
                    # user_message는 _handle_user_turn에서 직접 수신하므로
                    # 여기서는 큐에 넣거나 무시
                    pass
        except Exception:
            # WebSocket 종료 시
            self.is_active = False
            self.end_reason = "connection_lost"

    async def _handle_agent_turn(self) -> None:
        """에이전트 발언 턴."""
        effective_log = self._get_effective_log()

        decision = await decide_next_speaker(
            self.openai, self.meeting_agenda, self.personas, effective_log
        )

        # 합의 확인
        if decision.consensus_reached:
            self.end_reason = "consensus_reached"
            self.consensus_summary = decision.consensus_summary
            self.is_active = False
            return

        persona = self.get_persona(decision.next_speaker_id)
        if persona is None:
            # 폴백: 첫 번째 페르소나
            persona = self.personas[0]

        await self.websocket.send_json({
            "event": "next_speaker",
            "id": persona.id,
            "role": persona.role,
            "facilitation": decision.facilitation,
        })

        full_text = await speak_with_streaming(
            self.openai,
            persona,
            self.meeting_agenda,
            effective_log,
            decision.facilitation,
            self.websocket,
        )

        self.add_entry(persona.id, persona.role, full_text, "utterance")

    async def _handle_user_turn(self) -> None:
        """사용자 발언 턴."""
        await self.websocket.send_json({"event": "your_turn"})

        # 사용자 메시지 대기
        while True:
            data = await self.websocket.receive_json()
            event = data.get("event", "")
            if event == "user_message":
                text = data.get("text", "")
                self.add_entry("user", "사용자", text, "user_input")
                break
            elif event == "end_meeting":
                self.is_active = False
                self.end_reason = "user_ended"
                break

    async def _summarize_meeting(self) -> FinalReport:
        """회의 종료 후 최종 보고서 생성."""
        log_text = "\n".join(
            f"[Round {e.round}] {e.speaker_role}({e.speaker_id}): {e.content}"
            for e in self.meeting_log
        )

        user_msg = (
            f"## 회의 정보\n"
            f"주제: {self.topic}\n목적: {self.purpose}\n안건: {self.meeting_agenda}\n\n"
            f"## 종료 사유: {self.end_reason}\n\n"
            f"## 전체 회의록\n{log_text}"
        )

        response = await self.openai.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)

        # 통계 계산
        speaker_roles = set()
        user_count = 0
        for e in self.meeting_log:
            if e.speaker_id == "user":
                user_count += 1
            elif e.speaker_id not in ("orchestrator", "system"):
                speaker_roles.add(e.speaker_role)

        return FinalReport(
            project_name=_sanitize_name(self.project_name),
            topic=self.topic,
            purpose=self.purpose,
            meeting_stats=MeetingStats(
                total_rounds=self.current_round,
                end_reason=self.end_reason,
                participants=sorted(speaker_roles),
                user_interventions=user_count,
            ),
            consensus=ConsensusInfo(
                reached=self.end_reason == "consensus_reached",
                summary=self.consensus_summary,
            ),
            key_insights=result.get("key_insights", []),
            action_items=result.get("action_items", []),
            unresolved_issues=result.get("unresolved_issues", []),
            full_transcript=self.meeting_log,
            summary_report=result.get("summary_report", ""),
        )

    def _save_final_report(self, report: FinalReport) -> None:
        """최종 보고서를 data/{project_name}/에 저장."""
        ddir = _data_dir(self.project_name)
        ddir.mkdir(parents=True, exist_ok=True)
        (ddir / "final_report.json").write_text(
            json.dumps(report.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
