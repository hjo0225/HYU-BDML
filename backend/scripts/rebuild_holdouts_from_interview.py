"""V1 진짜 hold-out 백필 — 패키지 JSON 의 인터뷰 답변을 ground truth 로 추출하고
페르소나 프롬프트에서 인터뷰 섹션·근거 발언 라인을 제거한다.

배경:
- 현재 import_agent_package.py 는 패키지 persona_text(인터뷰 raw + 6-Lens 분석
  포함, ~87k 문자)를 그대로 persona_full_prompt 에 넣음 → 인터뷰 답변이
  페르소나에 노출되므로 hold-out 무효.
- 이 스크립트는 in-place 로:
  1) 인터뷰 답변(Q6/Q7/Q8/Q11/Q12/Q13) → scratch.holdout_iv_a1~b3
  2) persona_full_prompt 재구성: 인터뷰 섹션 통째로 제거 + 6-Lens 분석의
     "근거 발언" 라인만 제거 (관찰 본문은 유지 — 추상 해석이라 페르소나 유용)

사용:
    python -m scripts.rebuild_holdouts_from_interview \\
        --project-id 0de00000-0000-4000-8000-000000000002

    # dry-run (DB 변경 없이 진단만)
    python -m scripts.rebuild_holdouts_from_interview --project-id ... --dry-run

멱등: 이미 처리된 페르소나(인터뷰 섹션 없음) 는 prompt 갱신 skip 하고
holdout 값만 동기화. --force 로 holdout 강제 재추출.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from database import Agent, AsyncSessionLocal
from evaluation.stimuli import HOLDOUT_INTERVIEW_MAPPING, HOLDOUT_OBJECTIVE_MAPPING

# 기본 패키지 경로 (import_agent_package.py 와 동일)
_DEFAULT_PACKAGE_DIR = r"C:/Users/ABC/Desktop/agent_package (1)"

# persona_text 안 인터뷰 섹션 헤더 (그 다음 ## 헤더 전까지가 인터뷰 본문)
_INTERVIEW_SECTION_RE = re.compile(
    r"\n?##\s*심층\s*인터뷰\s*응답.*?(?=\n##\s|\Z)",
    re.DOTALL,
)

# 6-Lens 분석 안 "근거 발언:" 으로 시작하는 라인(들). 동일 라인이 ' "..." ' 따옴표로
# 끝나므로 라인 단위 매칭.
_EVIDENCE_LINE_RE = re.compile(r"^\s*근거\s*발언:\s*.*$\n?", re.MULTILINE)

# 객관식 척도 섹션 안 'Answer: ...' 라인 - mask 대상.
_ANSWER_LINE_RE = re.compile(r"^(\s*)Answer:\s*(.+?)\s*$", re.MULTILINE)

# Conscientiousness 9점 척도 라벨 보간 — anchor 1·5·9 만 명세돼 있어
# 중간 점수 답 ("7" 등) 은 가까운 anchor 의 라벨로 보강. 다른 lens 자극은
# 모두 "<점수> - <라벨>" 형식이라 형평성을 위해 L6 도 같은 형식으로 통일.
_CON_LABEL_BY_RANGE = [
    (1, 1, "매우 부정확함"),
    (2, 4, "부정확함"),
    (5, 5, "정확하지도 부정확하지도 않음"),
    (6, 8, "정확함"),
    (9, 9, "매우 정확함"),
]

def normalize_objective_answer(raw: str) -> str:
    """ground truth 가 숫자만 ("9") 인 경우 라벨을 보강.

    이미 "9 - 매우 정확함" 같이 라벨이 있으면 그대로. 형식 통일 목적이라
    채점 편의 제공이 아니라 자극 간 동일 매칭 조건 보장.
    """
    a = (raw or "").strip()
    if "-" in a or not a.isdigit():
        return a  # 이미 라벨 있음 또는 비숫자
    n = int(a)
    for lo, hi, lab in _CON_LABEL_BY_RANGE:
        if lo <= n <= hi:
            return f"{a} - {lab}"
    return a


def find_objective_answer(
    persona_text: str, section_re: str, statement_keyword: str
) -> tuple[str | None, tuple[int, int] | None]:
    """섹션 헤더 안에서 진술문 키워드를 포함한 Q 블록의 Answer 추출.

    Returns:
        (answer_text, (start, end) of the Answer line in persona_text)
        매칭 실패 시 (None, None).
    """
    sec_m = re.search(section_re, persona_text)
    if not sec_m:
        return None, None
    # 섹션 본문 = 헤더 시작부터 다음 ### 직전까지
    section_start = sec_m.start()
    next_sec = re.search(r"^### ", persona_text[sec_m.end():], re.MULTILINE)
    section_end = sec_m.end() + next_sec.start() if next_sec else len(persona_text)
    section = persona_text[section_start:section_end]

    # 진술문 키워드를 포함한 라인 찾기
    kw_m = re.search(re.escape(statement_keyword), section)
    if not kw_m:
        return None, None
    # 그 위치 이후 첫 'Answer:' 라인
    ans_m = _ANSWER_LINE_RE.search(section, pos=kw_m.end())
    if not ans_m:
        return None, None
    answer = ans_m.group(2).strip()
    # persona_text 전체 기준 절대 좌표
    abs_start = section_start + ans_m.start()
    abs_end = section_start + ans_m.end()
    return answer, (abs_start, abs_end)


def mask_objective_answers(
    persona_text: str, mapping: dict[str, tuple[str, str]]
) -> tuple[str, dict[str, str]]:
    """매핑된 객관식 Answer 라인을 'Answer: [평가용으로 가림]' 으로 치환.

    Returns:
        (수정된 persona_text, {scratch_key: 원본_answer})
    """
    extracted: dict[str, str] = {}
    # 여러 치환을 동시에 수행하기 위해 위치를 모은 뒤 뒤에서부터 치환
    replacements: list[tuple[int, int, str]] = []
    for scratch_key, (section_re, kw) in mapping.items():
        answer, span = find_objective_answer(persona_text, section_re, kw)
        if answer is None or span is None:
            continue
        # 형평성 — 다른 자극과 동일한 "<점수> - <라벨>" 형식으로 통일
        extracted[scratch_key] = normalize_objective_answer(answer)
        # 들여쓰기 보존을 위해 원본 라인의 leading whitespace 유지
        orig_line = persona_text[span[0]:span[1]]
        m = re.match(r"^(\s*)Answer:", orig_line)
        indent = m.group(1) if m else ""
        replacements.append((span[0], span[1], f"{indent}Answer: [평가용으로 가림]"))

    # 뒤에서부터 치환 (인덱스 유지)
    new_text = persona_text
    for start, end, repl in sorted(replacements, key=lambda x: -x[0]):
        new_text = new_text[:start] + repl + new_text[end:]
    return new_text, extracted


def parse_interview_qa(persona_text: str) -> dict[str, str]:
    """persona_text 의 인터뷰 섹션에서 {Q번호: 답변} 추출.

    포맷:
        ## 심층 인터뷰 응답 (raw)
        Q5.
        → 사용함

        Q6.
        → 키보드 ...

    답변 = '→ ' 다음부터 다음 'Q<n>.' 또는 다음 '##' 직전까지의 텍스트.
    """
    m = _INTERVIEW_SECTION_RE.search(persona_text)
    if not m:
        return {}
    section = m.group(0)

    qa: dict[str, str] = {}
    # 각 Q 블록: Q<n>. (옵션 헤더) → 답변 본문 (다음 Q<n>. 직전까지)
    # 비탐욕 매칭으로 다음 Q<n>. 또는 섹션 끝
    for blk in re.finditer(
        r"^Q(\d+)\.[^\n]*\n→\s*(.*?)(?=^Q\d+\.|\Z)",
        section,
        re.MULTILINE | re.DOTALL,
    ):
        qnum = blk.group(1)
        answer = blk.group(2).strip()
        if answer:
            qa[qnum] = answer
    return qa


def strip_interview_and_evidence(persona_text: str) -> str:
    """persona_text 에서 인터뷰 섹션 + 6-Lens 분석 근거 발언 라인 제거.

    - 인터뷰 섹션 (## 심층 인터뷰 응답 ~ 다음 ## 헤더 직전) : 통째 삭제
    - 6-Lens 분석의 '근거 발언: "..."' 라인 : 라인만 삭제 (관찰 본문 유지)
    """
    cleaned = _INTERVIEW_SECTION_RE.sub("", persona_text)
    cleaned = _EVIDENCE_LINE_RE.sub("", cleaned)
    return cleaned


def rebuild_full_prompt(
    *,
    system_message: str,
    persona_header: str,
    cleaned_persona_text: str,
) -> str:
    """import_agent_package.py 와 동일한 결합 규칙으로 prompt 재구성."""
    parts = [p for p in [system_message, (persona_header or "") + cleaned_persona_text] if p]
    return "\n\n".join(parts)


def load_package_json(package_dir: Path, pid: str) -> dict | None:
    p = package_dir / "agents" / f"{pid}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


async def process_one(
    db: AsyncSession,
    agent: Agent,
    *,
    package_dir: Path,
    force: bool,
    dry_run: bool,
) -> str:
    """반환: 'seeded' / 'updated_prompt' / 'noop' / 'skipped:<reason>'"""
    if agent.source_type != "package" or not agent.source_ref:
        return "skipped:not-package"
    pkg = load_package_json(package_dir, agent.source_ref)
    if pkg is None:
        return f"skipped:no-json({agent.source_ref})"

    system_message = pkg.get("system_message", "")
    persona_header = pkg.get("persona_header", "")
    persona_text = pkg.get("persona_text", "")
    if not persona_text:
        return "skipped:empty-persona-text"

    # ① 인터뷰 Q&A 추출
    qa = parse_interview_qa(persona_text)
    if not qa:
        return "skipped:no-interview-section"

    scratch = dict(agent.scratch or {})
    iv_updates = 0
    for scratch_key, qnum in HOLDOUT_INTERVIEW_MAPPING.items():
        ans = qa.get(qnum)
        if not ans:
            continue
        if scratch.get(scratch_key) and not force:
            continue
        scratch[scratch_key] = ans
        iv_updates += 1

    # ② persona_text 정제 — 인터뷰 섹션 + 근거 발언 라인 제거
    cleaned = strip_interview_and_evidence(persona_text)

    # ③ 객관식 hold-out — 진술문 Answer 라인을 마스킹하고 ground truth 저장
    cleaned, obj_extracted = mask_objective_answers(cleaned, HOLDOUT_OBJECTIVE_MAPPING)
    obj_updates = 0
    for scratch_key, ans in obj_extracted.items():
        if scratch.get(scratch_key) and not force:
            continue
        scratch[scratch_key] = ans
        obj_updates += 1

    # ④ persona_full_prompt 재구성
    new_prompt = rebuild_full_prompt(
        system_message=system_message,
        persona_header=persona_header,
        cleaned_persona_text=cleaned,
    )
    prompt_changed = (agent.persona_full_prompt or "") != new_prompt

    if dry_run:
        tag = []
        if iv_updates:
            tag.append(f"iv+{iv_updates}")
        if obj_updates:
            tag.append(f"obj+{obj_updates}")
        if prompt_changed:
            tag.append(f"prompt:{len(agent.persona_full_prompt or '')}→{len(new_prompt)}")
        return "dry:" + (",".join(tag) if tag else "noop")

    changed = False
    if iv_updates or obj_updates:
        agent.scratch = scratch
        flag_modified(agent, "scratch")
        changed = True
    if prompt_changed:
        agent.persona_full_prompt = new_prompt
        changed = True

    if not changed:
        return "noop"
    return f"updated(iv+{iv_updates},obj+{obj_updates},prompt_chars={len(new_prompt)})"


async def run(*, project_id: str, package_dir: Path, force: bool, dry_run: bool) -> None:
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(Agent).where(Agent.project_id == project_id).order_by(Agent.created_at)
        )
        agents = list(res.scalars().all())

        if not agents:
            print(f"no agents (project_id={project_id})")
            return

        print(f"package_dir = {package_dir}")
        print(f"project_id  = {project_id}")
        print(f"agents      = {len(agents)} (force={force}, dry_run={dry_run})\n")

        results: list[str] = []
        for a in agents:
            status = await process_one(
                db, a, package_dir=package_dir, force=force, dry_run=dry_run
            )
            results.append(status)
            tag = "✓" if status.startswith(("updated", "dry:holdout")) else (
                "·" if status in ("noop",) else "!"
            )
            print(f"  {tag} {a.id[:8]} {a.source_ref or '-':<8} {a.display_name or '(no name)':<10} {status}")

        if not dry_run:
            await db.commit()

        print(f"\nprocessed {len(agents)} agents")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--project-id", required=True, help="처리 대상 프로젝트")
    ap.add_argument("--package-dir", default=_DEFAULT_PACKAGE_DIR, help="원본 패키지 루트")
    ap.add_argument("--force", action="store_true", help="이미 채워진 holdout 도 재추출")
    ap.add_argument("--dry-run", action="store_true", help="DB 변경 없이 진단만")
    args = ap.parse_args()

    asyncio.run(run(
        project_id=args.project_id,
        package_dir=Path(args.package_dir),
        force=args.force,
        dry_run=args.dry_run,
    ))


if __name__ == "__main__":
    main()
