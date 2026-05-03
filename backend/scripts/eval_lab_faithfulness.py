"""Lab Faithfulness — 트윈 일괄 평가 스크립트.

흐름:
  1) 각 트윈의 `Panel.scratch.probe_questions[category]`(seed_lab_probe_questions로
     사전 생성)를 순회.
  2) 같은 lab_service.stream_chat을 호출해 답변을 수집 (실제 사용자가 보는 응답).
  3) lab_judge_service.judge_response()로 채점.
  4) 카테고리별 점수 집계 → `Panel.scratch.faithfulness`에 저장.

점수 매핑 (verdict → score):
  consistent = 1.0
  partial    = 0.5
  contradicts= 0.0
  evasive    = (제외) — 평균에 포함하지 않음

실행:
  cd backend
  python -m scripts.seed_lab_probe_questions  # 선행 (한 번)
  python -m scripts.eval_lab_faithfulness --twin-id twin_1001
  python -m scripts.eval_lab_faithfulness --all
  python -m scripts.eval_lab_faithfulness --all --limit 5  # 시범 5명
  python -m scripts.eval_lab_faithfulness --all --max-per-twin 8  # 카테고리 8개만 표본
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass

from sqlalchemy import select

from database import AsyncSessionLocal, Panel
from services.lab_judge_service import judge_response
from services.lab_service import stream_chat


_SCORE_MAP = {
    "consistent": 1.0,
    "partial": 0.5,
    "contradicts": 0.0,
}


async def _collect_answer(twin_id: str, question: str) -> str:
    """stream_chat 제너레이터를 소진하고 end content만 추출."""
    full_content = ""
    async for sse_line in stream_chat(twin_id, history=[], message=question):
        line = sse_line.strip()
        if not line.startswith("data:"):
            continue
        try:
            data = json.loads(line[len("data:"):].strip())
        except Exception:  # noqa: BLE001
            continue
        if data.get("type") == "end":
            full_content = data.get("content") or ""
        elif data.get("type") == "error":
            return ""
    return full_content


async def _eval_twin(panel_id: str, max_per_twin: int | None) -> dict | None:
    async with AsyncSessionLocal() as session:
        panel = (await session.execute(
            select(Panel).where(
                Panel.panel_id == panel_id,
                Panel.source == "twin2k500",
            )
        )).scalar_one_or_none()
        if not panel:
            print(f"  ! {panel_id}: 패널 없음")
            return None
        scratch = panel.scratch
        if isinstance(scratch, str):
            scratch = json.loads(scratch)
        scratch = scratch or {}
        probes: dict = scratch.get("probe_questions") or {}

    if not isinstance(probes, dict) or not probes:
        print(f"  ! {panel_id}: probe_questions 없음 — seed_lab_probe_questions 먼저 실행")
        return None

    items = list(probes.items())
    if max_per_twin and len(items) > max_per_twin:
        random.shuffle(items)
        items = items[:max_per_twin]

    scores_by_cat: dict[str, list[float]] = {}
    n_eval = 0
    n_evasive = 0

    for i, (category, question) in enumerate(items, 1):
        question = (question or "").strip()
        if not question:
            continue
        print(f"    [{i}/{len(items)}] {category} — Q: {question[:40]}")
        answer = await _collect_answer(panel_id, question)
        if not answer:
            print("      → 답변 비어있음 (skip)")
            continue
        verdict = await judge_response(panel_id, question, answer)
        v = verdict.verdict
        if v == "evasive":
            n_evasive += 1
            print(f"      → evasive: {verdict.reason[:60]}")
            continue
        score = _SCORE_MAP.get(v, 0.0)
        scores_by_cat.setdefault(category, []).append(score)
        n_eval += 1
        print(f"      → {v} ({score})")

    by_category = {
        cat: round(sum(s) / len(s), 4) for cat, s in scores_by_cat.items() if s
    }
    overall = (
        round(sum(by_category.values()) / len(by_category), 4) if by_category else 0.0
    )

    summary = {
        "overall": overall,
        "by_category": by_category,
        "n_eval": n_eval,
        "n_evasive": n_evasive,
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    # 저장
    async with AsyncSessionLocal() as session:
        panel = (await session.execute(
            select(Panel).where(
                Panel.panel_id == panel_id,
                Panel.source == "twin2k500",
            )
        )).scalar_one_or_none()
        if panel:
            scratch_now = panel.scratch
            if isinstance(scratch_now, str):
                scratch_now = json.loads(scratch_now)
            scratch_now = scratch_now or {}
            scratch_now["faithfulness"] = summary
            panel.scratch = scratch_now
            await session.commit()

    print(
        f"  ✓ {panel_id}: overall={overall:.3f}, n={n_eval} (evasive {n_evasive}), "
        f"categories={len(by_category)}"
    )
    return summary


async def _main(args: argparse.Namespace) -> None:
    if args.twin_id:
        ids = [args.twin_id]
    else:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Panel.panel_id).where(Panel.source == "twin2k500")
            )
            ids = [r[0] for r in result.all()]
        if args.limit:
            ids = ids[: args.limit]

    print(f"[eval] Twin {len(ids)}명 평가 시작 (max_per_twin={args.max_per_twin})")
    for i, pid in enumerate(ids, 1):
        print(f"[{i}/{len(ids)}] {pid}")
        await _eval_twin(pid, args.max_per_twin)
    print("[eval] 완료")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--twin-id", type=str, default=None, help="단일 트윈 평가")
    parser.add_argument("--all", action="store_true", help="모든 트윈 평가")
    parser.add_argument("--limit", type=int, default=None, help="--all과 함께, 앞에서 N명만")
    parser.add_argument(
        "--max-per-twin",
        type=int,
        default=None,
        help="트윈당 최대 평가 카테고리 수 (랜덤 샘플)",
    )
    args = parser.parse_args()
    if not args.twin_id and not args.all:
        parser.error("--twin-id 또는 --all 중 하나는 필수입니다.")
    asyncio.run(_main(args))
