"""restyle_holdout_display.py — 홀드아웃 표시용 말투 통일본 사전계산 (plan 0023 연장).

backend/data/holdout_eval/{agent_id}.json 의 자유서술 인터뷰(section='INT') 페어에 대해
사람·AI 답변을 같은 구어체 존댓말 톤으로 통일(eval_holdout.restyle.unify_tone)하고
human_answer_display / agent_answer_display 필드로 저장한다.
**원본(human_answer·agent_answer)과 유사도 점수는 건드리지 않는다 — 표시 전용.**

사용법:
  python -m scripts.restyle_holdout_display              # 캐시의 모든 {id}.json
  python -m scripts.restyle_holdout_display --mock       # API 호출 없이 (display=원본)
  python -m scripts.restyle_holdout_display --force      # 이미 채워진 페어도 재생성
  python -m scripts.restyle_holdout_display --agent-ids <id>,<id>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval_holdout.restyle import unify_tone

_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "holdout_eval"

# 말투 통일 대상 — 자유서술 인터뷰만(객관식·Likert 는 '말투'가 없어 제외).
_RESTYLE_SECTION = "INT"


def _needs_restyle(pair: dict, force: bool) -> bool:
    if pair.get("section") != _RESTYLE_SECTION:
        return False
    if force:
        return True
    return not (pair.get("human_answer_display") and pair.get("agent_answer_display"))


async def _restyle_file(path: Path, *, mock: bool, force: bool, concurrency: int) -> int:
    result = json.loads(path.read_text(encoding="utf-8"))
    all_pairs: list[dict] = result.get("all_pairs") or []

    # 통일 대상 question_id 별로 1회만 호출 (all_pairs 가 SSOT — top_* 는 여기서 patch).
    targets: dict[str, dict] = {}
    for p in all_pairs:
        if _needs_restyle(p, force) and p["question_id"] not in targets:
            targets[p["question_id"]] = p
    if not targets:
        return 0

    sem = asyncio.Semaphore(concurrency)

    async def _one(qid: str, p: dict) -> tuple[str, dict[str, str]]:
        async with sem:
            styled = await unify_tone(
                p.get("question", ""), p.get("human_answer", ""), p.get("agent_answer", ""), mock=mock
            )
            return qid, styled

    styled_map = dict(await asyncio.gather(*(_one(q, p) for q, p in targets.items())))

    # all_pairs · top_matches · top_mismatches 전부 같은 question_id 로 patch.
    patched = 0
    for key in ("all_pairs", "top_matches", "top_mismatches"):
        for p in result.get(key) or []:
            styled = styled_map.get(p.get("question_id"))
            if styled and p.get("section") == _RESTYLE_SECTION:
                p["human_answer_display"] = styled["human"]
                p["agent_answer_display"] = styled["agent"]
                if key == "all_pairs":
                    patched += 1

    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return patched


async def _run(args: argparse.Namespace) -> None:
    if not _CACHE_DIR.exists():
        print(f"캐시 디렉터리 없음: {_CACHE_DIR}. 먼저 run_holdout_eval 실행 필요.")
        return

    files = sorted(_CACHE_DIR.glob("*.json"))
    if args.agent_ids:
        wanted = {a.strip() for a in args.agent_ids.split(",") if a.strip()}
        files = [f for f in files if f.stem in wanted]
    if not files:
        print("대상 JSON 없음.")
        return

    print(f"대상 {len(files)}개 파일, mock={args.mock}, force={args.force}")
    for f in files:
        n = await _restyle_file(f, mock=args.mock, force=args.force, concurrency=args.concurrency)
        print(f"  ✅ {f.name}: INT 페어 {n}건 말투 통일" if n else f"  · {f.name}: 통일 대상 없음(이미 처리됨)")


def main() -> None:
    p = argparse.ArgumentParser(description="홀드아웃 표시용 말투 통일 사전계산")
    p.add_argument("--agent-ids", default=None, help="콤마 구분 agent.id (파일명) 필터")
    p.add_argument("--mock", action="store_true", help="API 호출 없이 (display=원본 폴백)")
    p.add_argument("--force", action="store_true", help="이미 채워진 페어도 재생성")
    p.add_argument("--concurrency", type=int, default=4)
    args = p.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
