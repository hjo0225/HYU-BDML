"""fgi_spike.py — Plan 0004 §Slice 0b 의 FGI 오케스트레이션 선검증 스크립트.

검증 항목:
  1. 2 라운드 transcript 가 일반론·반복에 그치지 않고 페르소나별 관점
     차이가 드러나는가
  2. 라운드별 engagement score 가 round-robin 과 다른 발화자 순서를
     선정하는가
  3. follow-up cascade (1차 token → 2차 LLM rubric) 가 발화 품질을
     실질적으로 높이는가
  4. 세션당 비용(토큰 사용량 × 가격) 추정

사용법:
  # .env 로 OPENAI_API_KEY 설정 후
  python -m backend.spike.fgi_spike --rounds 2 --output backend/spike/transcripts/run1.json
  # 다른 가중치 시도
  python -m backend.spike.fgi_spike --weights "relevance=0.6,recency=0.2,extraversion=0.2"

결과 transcript JSON 의 구조:
  {
    "meta": { "topic", "weights", "model", "started_at", "ended_at", "cost_estimate" },
    "personas": [...],
    "turns": [
      { "round", "role", "speaker_id", "speaker_name", "content",
        "engagement_breakdown", "cascade": { ... } },
      ...
    ],
    "round_summaries": [...]
  }
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# 프로젝트 루트를 import path 에 추가 (python -m backend.spike.fgi_spike 실행 가정)
# .env 자동 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from backend.spike.cascade import CascadeResult, token_filter
from backend.spike.engagement import DEFAULT_WEIGHTS, select_next_speaker
from backend.spike.personas import PERSONAS, TOPIC, SpikePersona
from backend.spike.prompts import (
    AGENT_TURN,
    CASCADE_RUBRIC,
    MODERATOR_FOLLOWUP,
    MODERATOR_OPENING,
)

# ─────────────────────────────────────────────────────────────────────────────
# 모델 & 가격 (2026-05 기준 USD per 1M token)
# ─────────────────────────────────────────────────────────────────────────────
CHAT_MODEL = "gpt-4o"
EMBED_MODEL = "text-embedding-3-small"
PRICE = {
    "gpt-4o": {"in": 2.5, "out": 10.0},
    "text-embedding-3-small": {"in": 0.02, "out": 0.0},
}


# ─────────────────────────────────────────────────────────────────────────────
# 비용 추적
# ─────────────────────────────────────────────────────────────────────────────
class UsageMeter:
    def __init__(self):
        self.records: list[dict] = []

    def add(self, model: str, in_tokens: int, out_tokens: int, label: str):
        cost = (in_tokens * PRICE[model]["in"] + out_tokens * PRICE[model]["out"]) / 1_000_000
        self.records.append({
            "model": model,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "cost_usd": cost,
            "label": label,
        })

    @property
    def total_cost(self) -> float:
        return sum(r["cost_usd"] for r in self.records)

    @property
    def total_in(self) -> int:
        return sum(r["in_tokens"] for r in self.records)

    @property
    def total_out(self) -> int:
        return sum(r["out_tokens"] for r in self.records)


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI 호출 래퍼 — usage 자동 누적
# ─────────────────────────────────────────────────────────────────────────────
async def chat(
    client: AsyncOpenAI,
    messages: list[ChatCompletionMessageParam],
    label: str,
    meter: UsageMeter,
    *,
    temperature: float = 0.8,
    max_tokens: int = 400,
) -> str:
    resp = await client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if resp.usage:
        meter.add(CHAT_MODEL, resp.usage.prompt_tokens, resp.usage.completion_tokens, label)
    return (resp.choices[0].message.content or "").strip()


async def embed(client: AsyncOpenAI, text: str, label: str, meter: UsageMeter) -> list[float]:
    resp = await client.embeddings.create(model=EMBED_MODEL, input=text)
    if resp.usage:
        meter.add(EMBED_MODEL, resp.usage.prompt_tokens, 0, label)
    return resp.data[0].embedding


# ─────────────────────────────────────────────────────────────────────────────
# 메인 루프
# ─────────────────────────────────────────────────────────────────────────────
async def run_spike(
    rounds: int,
    weights: dict[str, float],
    output_path: Path,
    topic: str = TOPIC,
) -> dict:
    client = AsyncOpenAI()  # OPENAI_API_KEY 환경변수 사용
    meter = UsageMeter()

    # 1) 페르소나 요약 임베딩 사전 계산 (relevance 항용)
    print(f"▶ 페르소나 임베딩 계산 ({len(PERSONAS)}건)…", flush=True)
    persona_emb: dict[str, list[float]] = {}
    for p in PERSONAS:
        persona_emb[p.agent_id] = await embed(client, p.summary_text, f"persona_emb/{p.agent_id}", meter)

    candidates = [
        {
            "agent_id": p.agent_id,
            "summary_emb": persona_emb[p.agent_id],
            "extraversion": p.extraversion,
        }
        for p in PERSONAS
    ]
    persona_by_id: dict[str, SpikePersona] = {p.agent_id: p for p in PERSONAS}

    transcript: list[dict] = []
    round_summaries: list[str] = []
    started_at = datetime.now(timezone.utc).isoformat()

    # 2) 라운드 루프
    for round_idx in range(1, rounds + 1):
        print(f"\n──── Round {round_idx}/{rounds} ────", flush=True)

        # 모더레이터 발언
        if round_idx == 1:
            mod_prompt = MODERATOR_OPENING.format(topic=topic)
        else:
            mod_prompt = MODERATOR_FOLLOWUP.format(round_summary=round_summaries[-1])

        mod_msg = await chat(
            client,
            [{"role": "system", "content": "당신은 시장조사 FGI 모더레이터입니다."},
             {"role": "user", "content": mod_prompt}],
            label=f"moderator/r{round_idx}",
            meter=meter,
            temperature=0.6,
            max_tokens=200,
        )
        transcript.append({
            "round": round_idx,
            "role": "moderator",
            "speaker_id": "__moderator__",
            "speaker_name": "모더레이터",
            "content": mod_msg,
            "engagement_breakdown": None,
            "cascade": None,
        })
        print(f"🎤 모더레이터: {mod_msg}", flush=True)

        # 라운드 내 발화 (engagement score 로 발화자 순서 결정, 한 라운드에 모두 1회씩)
        mod_emb = await embed(client, mod_msg, f"moderator_emb/r{round_idx}", meter)
        spoken_this_round: set[str] = set()

        for turn_idx in range(len(PERSONAS)):
            remaining = [c for c in candidates if c["agent_id"] not in spoken_this_round]
            sel = select_next_speaker(remaining, mod_emb, transcript, weights)
            spoken_this_round.add(sel.agent_id)
            persona = persona_by_id[sel.agent_id]

            # 다른 참여자 발언 요약 (최근 3개)
            others_recent = [
                t for t in transcript[-6:]
                if t["role"] == "agent" and t["speaker_id"] != sel.agent_id
            ]
            others_summary = "\n".join(
                f"- {t['speaker_name']}: {t['content']}" for t in others_recent
            ) or "(아직 다른 참여자 발언 없음)"

            agent_prompt = AGENT_TURN.format(
                moderator_message=mod_msg,
                others_summary=others_summary,
            )
            utterance = await chat(
                client,
                [{"role": "system", "content": persona.system_prompt},
                 {"role": "user", "content": agent_prompt}],
                label=f"agent/{persona.agent_id}/r{round_idx}",
                meter=meter,
                temperature=0.85,
                max_tokens=200,
            )

            # follow-up cascade
            cascade_1 = token_filter(utterance)
            if cascade_1 is None:
                # 2차 LLM rubric
                rubric_resp = await chat(
                    client,
                    [{"role": "system", "content": "당신은 발언 품질을 평가하는 평가자입니다."},
                     {"role": "user", "content": CASCADE_RUBRIC.format(
                         persona_summary=persona.summary_text, utterance=utterance,
                     )}],
                    label=f"cascade/{persona.agent_id}/r{round_idx}",
                    meter=meter,
                    temperature=0.0,
                    max_tokens=80,
                )
                try:
                    rubric = json.loads(rubric_resp)
                    cascade_result = CascadeResult(
                        need_followup=int(rubric.get("score", 5)) <= 3,
                        stage="llm_rubric",
                        score=int(rubric.get("score", 5)),
                        reason=str(rubric.get("reason", "")),
                    )
                except (json.JSONDecodeError, ValueError, TypeError):
                    cascade_result = CascadeResult(
                        need_followup=False,
                        stage="llm_rubric",
                        score=None,
                        reason=f"rubric 파싱 실패: {rubric_resp[:60]!r}",
                    )
            else:
                cascade_result = cascade_1

            transcript.append({
                "round": round_idx,
                "role": "agent",
                "speaker_id": persona.agent_id,
                "speaker_name": persona.name,
                "content": utterance,
                "engagement_breakdown": sel.breakdown,
                "cascade": {
                    "need_followup": cascade_result.need_followup,
                    "stage": cascade_result.stage,
                    "score": cascade_result.score,
                    "reason": cascade_result.reason,
                },
            })
            print(
                f"💬 {persona.name} "
                f"[eng={sel.breakdown['total']:.2f} "
                f"R={sel.breakdown['relevance']:.2f} t={sel.breakdown['recency']:.2f} "
                f"x={sel.breakdown['extraversion']:.2f}] "
                f"cascade={cascade_result.stage}/{'⚠' if cascade_result.need_followup else '✓'}",
                flush=True,
            )
            print(f"   {utterance}", flush=True)

        # 라운드 요약 생성 (다음 라운드 follow-up 입력용)
        round_agent_turns = [t for t in transcript if t["round"] == round_idx and t["role"] == "agent"]
        round_summary = "\n".join(f"- {t['speaker_name']}: {t['content']}" for t in round_agent_turns)
        round_summaries.append(round_summary)

    ended_at = datetime.now(timezone.utc).isoformat()

    # 3) 결과 직렬화
    result = {
        "meta": {
            "topic": topic,
            "weights": weights,
            "chat_model": CHAT_MODEL,
            "embed_model": EMBED_MODEL,
            "started_at": started_at,
            "ended_at": ended_at,
            "usage": {
                "total_in_tokens": meter.total_in,
                "total_out_tokens": meter.total_out,
                "total_cost_usd": round(meter.total_cost, 4),
                "records": meter.records,
            },
        },
        "personas": [
            {"agent_id": p.agent_id, "name": p.name, "extraversion": p.extraversion}
            for p in PERSONAS
        ],
        "turns": transcript,
        "round_summaries": round_summaries,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 저장: {output_path}", flush=True)
    print(
        f"💰 비용: ${meter.total_cost:.4f} "
        f"(in {meter.total_in:,} / out {meter.total_out:,} tokens)",
        flush=True,
    )

    # 발화자 순서 vs round-robin 비교
    speaker_order = [t["speaker_id"] for t in transcript if t["role"] == "agent"]
    print(f"📋 발화자 순서: {' → '.join(speaker_order)}", flush=True)

    return result


def parse_weights(s: str) -> dict[str, float]:
    """'relevance=0.5,recency=0.3,extraversion=0.2' → dict"""
    if not s:
        return DEFAULT_WEIGHTS
    out: dict[str, float] = {}
    for pair in s.split(","):
        k, v = pair.split("=")
        out[k.strip()] = float(v.strip())
    total = sum(out.values())
    if abs(total - 1.0) > 0.01:
        raise ValueError(f"weights 합이 1.0 이 아닙니다: {total}")
    return out


def main():
    parser = argparse.ArgumentParser(description="FGI 스파이크 실행")
    parser.add_argument("--rounds", type=int, default=2, help="회의 라운드 수 (기본 2)")
    parser.add_argument(
        "--weights",
        type=str,
        default="",
        help="engagement 가중치 'relevance=0.5,recency=0.3,extraversion=0.2'",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=f"backend/spike/transcripts/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        help="transcript JSON 저장 경로",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=TOPIC,
        help="FGI 주제 (기본: 신규 구독형 단백질 보충제)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="LLM 호출 없이 비용 추정만 출력 후 종료",
    )
    args = parser.parse_args()

    weights = parse_weights(args.weights)
    output_path = Path(args.output)

    if args.dry_run:
        # 매우 거친 예측
        estimated_chat_calls = args.rounds * (1 + len(PERSONAS) * 2)  # mod + (agent + rubric) × N
        estimated_embed_calls = len(PERSONAS) + args.rounds
        print(f"⚠ dry-run: 예상 chat 호출 {estimated_chat_calls}, embed 호출 {estimated_embed_calls}")
        print(f"   예상 비용 ≈ ${0.05 * args.rounds:.3f}~${0.10 * args.rounds:.3f}")
        return

    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다. backend/.env 에 추가하거나 export 하세요.")
        sys.exit(1)

    asyncio.run(run_spike(args.rounds, weights, output_path, args.topic))


if __name__ == "__main__":
    main()
