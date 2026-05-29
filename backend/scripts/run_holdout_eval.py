"""run_holdout_eval.py — 홀드아웃 유사도 사전계산 (plan 0023, PoC).

agent.source_ref(pid) → agent_package 의 pid_xxx.txt 를 찾아 Q&A 페어 파싱,
80:20 split, 홀드아웃 질문을 agent 에게 chat_completion 으로 묻고, gpt-4.1-mini
judge 가 match/partial/no_match 판정. 결과를 backend/data/holdout_eval/{agent_id}.json
에 저장한다.

사용법:
  python -m scripts.run_holdout_eval                          # 데모 소스 6명 전체
  python -m scripts.run_holdout_eval --agent-ids <id>,<id>    # 특정 에이전트
  python -m scripts.run_holdout_eval --project-id <uuid>      # 특정 프로젝트 전체
  python -m scripts.run_holdout_eval --package-dir <path>     # pid_xxx.txt 경로 override
  python -m scripts.run_holdout_eval --limit 5                # 페어 수 제한 (디버그)
  python -m scripts.run_holdout_eval --mock                   # API 호출 없이 결정적 mock
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import Agent, AsyncSessionLocal, init_db
from eval_holdout.judge import JUDGE_MODEL, evaluate_pair, verdict_to_score
from eval_holdout.parser import parse_pid_txt
from eval_holdout.runner import (
    DEFAULT_HOLDOUT_RATIO,
    DEFAULT_SEED,
    collect_all_answers,
    split_holdout,
)

_DEFAULT_PACKAGE_DIR = Path(r"C:/Users/ABC/Desktop/agent_package (1)")
_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "holdout_eval"
_DEMO_SOURCE_PROJECT_ID = "61f78cf9-8329-4c24-912a-bd3eeac5bba8"
# 결과를 영구 저장하는 scratch 키. 라우터(get_agent_holdout)가 1차로 이 키를 읽는다.
# 배포(Cloud Run)는 파일시스템이 ephemeral 이라 DB(scratch) 저장이 SSOT.
_HOLDOUT_SCRATCH_KEY = "holdout_eval"


async def _persist_to_db(agent_id: str, result: dict) -> None:
    """결과를 agent.scratch['holdout_eval'] 에 저장 (배포 영속성).

    기존 scratch 키는 보존하고 holdout_eval 만 갱신. JSONB 변경 감지를 위해
    새 dict 로 재할당한다.
    """
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = res.scalar_one_or_none()
        if agent is None:
            return
        scratch = dict(agent.scratch) if isinstance(agent.scratch, dict) else {}
        scratch[_HOLDOUT_SCRATCH_KEY] = result
        agent.scratch = scratch
        await db.commit()


def _pid_txt_path(package_dir: Path, source_ref: str) -> Path:
    """source_ref(pid_001 등) → personas_readable/pid_001.txt."""
    return package_dir / "personas_readable" / f"{source_ref}.txt"


async def _resolve_agents(
    *,
    agent_ids: list[str] | None,
    project_id: str | None,
) -> list[Agent]:
    async with AsyncSessionLocal() as db:
        if agent_ids:
            res = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
        elif project_id:
            res = await db.execute(
                select(Agent).where(Agent.project_id == project_id).order_by(Agent.created_at.asc())
            )
        else:
            res = await db.execute(
                select(Agent)
                .where(Agent.project_id == _DEMO_SOURCE_PROJECT_ID)
                .order_by(Agent.created_at.asc())
            )
        return list(res.scalars().all())


async def _evaluate_agent(
    agent: Agent,
    package_dir: Path,
    *,
    ratio: float,
    seed: int,
    limit: int | None,
    mock: bool,
    per_lens_holdout: int | None,
    exclude_interview_q: set[int],
) -> dict:
    """단일 에이전트 처리. 결과 dict (저장 직전 형태) 반환."""
    if not agent.source_ref:
        raise RuntimeError(f"agent {agent.id[:8]} 에 source_ref 없음 — pid 매핑 불가")

    txt_path = _pid_txt_path(package_dir, agent.source_ref)
    if not txt_path.exists():
        raise FileNotFoundError(f"원본 파일 없음: {txt_path}")

    all_pairs = parse_pid_txt(txt_path, exclude_interview_q=exclude_interview_q)
    # 인터뷰는 전수 평가, 척도는 lens 별 stratified holdout.
    # per_lens_holdout 지정 시 lens 별 정확히 N개 (lens 페어<N 이면 전체) →
    # L6 등 표본 작은 lens 의 노이즈를 평탄화. ratio 모드는 fallback.
    interview_pairs = [p for p in all_pairs if p.section == "INT"]
    scale_pairs = [p for p in all_pairs if p.section != "INT"]
    _, scale_holdout = split_holdout(
        scale_pairs,
        ratio=ratio,
        seed=seed,
        per_lens_holdout=per_lens_holdout,
    )
    holdout = interview_pairs + scale_holdout
    if limit:
        holdout = holdout[:limit]

    print(
        f"  [{agent.display_name}] 전체 {len(all_pairs)} → "
        f"평가 {len(holdout)} (인터뷰 {len(interview_pairs)} 전수 + 척도 홀드아웃 {len(scale_holdout)})"
    )

    # 1) agent 응답 수집
    print("  · agent 응답 생성…")
    answers = await collect_all_answers(agent, holdout, concurrency=4, mock=mock)

    # 2) judge 평가 (concurrency 4)
    print("  · judge 평가…")
    sem = asyncio.Semaphore(4)

    async def _judge(pair, agent_answer):
        async with sem:
            v = await evaluate_pair(pair, agent_answer, mock=mock)
            return pair, agent_answer, v

    results = await asyncio.gather(*(_judge(p, a) for p, a in answers))

    # 3) 집계
    pairs_out: list[dict] = []
    score_sum = 0.0
    lens_agg: dict[str, dict[str, float]] = {}
    for pair, agent_answer, v in results:
        score = verdict_to_score(v["verdict"])
        score_sum += score
        bucket = lens_agg.setdefault(pair.lens, {"score_sum": 0.0, "n": 0.0})
        bucket["score_sum"] += score
        bucket["n"] += 1
        pairs_out.append({
            "question_id": pair.question_id,
            "lens": pair.lens,
            "section": pair.section,
            "section_label": pair.section_label,
            "domain": pair.domain,
            "qtype": pair.qtype,
            "question": pair.question,
            "human_answer": pair.answer,
            "agent_answer": agent_answer,
            "verdict": v["verdict"],
            "confidence": v["confidence"],
            "rationale": v["rationale"],
            "score": score,
        })

    by_lens = [
        {
            "lens": lens,
            "agreement": (b["score_sum"] / b["n"]) if b["n"] else 0.0,
            "n": int(b["n"]),
        }
        for lens, b in sorted(lens_agg.items())
    ]
    agreement = (score_sum / len(pairs_out)) if pairs_out else 0.0

    # 상위 표시용 top 페어 (10~15)
    matches = [p for p in pairs_out if p["verdict"] == "match"]
    mismatches = [p for p in pairs_out if p["verdict"] == "no_match"]
    matches.sort(key=lambda p: p["confidence"], reverse=True)
    mismatches.sort(key=lambda p: p["confidence"], reverse=True)

    return {
        "agent_id": agent.id,
        "agent_display_name": agent.display_name,
        "agent_source_ref": agent.source_ref,
        "agreement_score": round(agreement, 3),
        "n_total": len(pairs_out),
        "n_match": len(matches),
        "n_partial": sum(1 for p in pairs_out if p["verdict"] == "partial"),
        "n_no_match": len(mismatches),
        "by_lens": by_lens,
        "top_matches": matches[:12],
        "top_mismatches": mismatches[:12],
        "all_pairs": pairs_out,        # 전체 페어도 보존 (UI 에서 더보기 옵션)
        "judge_model": JUDGE_MODEL,
        "holdout_ratio": ratio if per_lens_holdout is None else None,
        "per_lens_holdout": per_lens_holdout,
        "exclude_interview_q": sorted(exclude_interview_q),
        "holdout_seed": seed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _run(args: argparse.Namespace) -> None:
    await init_db()
    package_dir = Path(args.package_dir)
    if not package_dir.exists():
        raise FileNotFoundError(f"--package-dir 없음: {package_dir}")

    agents = await _resolve_agents(
        agent_ids=args.agent_ids.split(",") if args.agent_ids else None,
        project_id=args.project_id,
    )
    if not agents:
        print("대상 에이전트 없음. --agent-ids 또는 --project-id 확인.")
        return

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # --exclude-interview-q "5,6" → {5,6}. 빈 문자열이면 빈 셋.
    exclude_iv_q: set[int] = set()
    if args.exclude_interview_q:
        for tok in args.exclude_interview_q.split(","):
            tok = tok.strip()
            if tok:
                exclude_iv_q.add(int(tok))

    per_lens = args.per_lens_holdout if args.per_lens_holdout and args.per_lens_holdout > 0 else None

    print(f"대상 {len(agents)}명, 캐시: {_CACHE_DIR}")
    print(f"judge={JUDGE_MODEL}, mock={args.mock}")
    if per_lens is not None:
        print(f"per_lens_holdout={per_lens} (ratio 무시), exclude_interview_q={sorted(exclude_iv_q)}")
    else:
        print(f"ratio={args.ratio}, exclude_interview_q={sorted(exclude_iv_q)}")

    for i, agent in enumerate(agents, start=1):
        print(f"\n[{i}/{len(agents)}] {agent.display_name} ({agent.id[:8]} · {agent.source_ref})")
        try:
            result = await _evaluate_agent(
                agent, package_dir,
                ratio=args.ratio, seed=args.seed,
                limit=args.limit, mock=args.mock,
                per_lens_holdout=per_lens,
                exclude_interview_q=exclude_iv_q,
            )
        except Exception as e:  # noqa: BLE001 — 1명 실패가 전체 중단 X
            print(f"  ❌ 실패: {e}")
            continue

        out_path = _CACHE_DIR / f"{agent.id}.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        # 파일(로컬 폴백) + DB scratch(배포 SSOT) 양쪽 저장
        await _persist_to_db(agent.id, result)
        print(
            f"  ✅ 일치율 {result['agreement_score']*100:.1f}% "
            f"(match {result['n_match']} / partial {result['n_partial']} / no_match {result['n_no_match']}) "
            f"→ {out_path.name} + DB scratch"
        )


def main() -> None:
    p = argparse.ArgumentParser(description="홀드아웃 유사도 사전계산 (plan 0023)")
    p.add_argument("--agent-ids", default=None, help="콤마 구분 agent.id 목록")
    p.add_argument("--project-id", default=None, help="프로젝트 단위 전체")
    p.add_argument("--package-dir", default=str(_DEFAULT_PACKAGE_DIR))
    p.add_argument("--ratio", type=float, default=DEFAULT_HOLDOUT_RATIO,
                   help="lens 별 holdout 비율 (per_lens_holdout 미지정 시)")
    p.add_argument("--per-lens-holdout", type=int, default=12,
                   help="lens 별 정확히 N개 holdout. 0 또는 음수면 ratio 모드.")
    p.add_argument("--exclude-interview-q", type=str, default="5,6",
                   help="인터뷰 블록에서 제외할 Q번호 (콤마구분). 기본 '5,6'.")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--limit", type=int, default=None, help="에이전트당 페어 수 상한(디버그)")
    p.add_argument("--mock", action="store_true", help="API 호출 없이 결정적 mock")
    args = p.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
