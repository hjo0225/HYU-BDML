"""import_agent_package.py — 외부 배포 패키지(agent_package)의 페르소나 JSON을
Ditto `agents` 테이블로 적재하는 어댑터 임포터 (PoC).

패키지는 Toubia(2025) Twin-2K-500 raw Q&A 평문 + Park(2024) Expert Reflection
6-Lens 분석을 담은 자급식 JSON 6개로 구성된다. `seed_agent` 와 달리 구조화
234문항 raw 가 없어 점수 산출(scoring/)을 건너뛰고, 6-Lens reflection 텍스트를
agent_memories 로 임베딩한다.

매핑 규칙은 docs/plans/active/0006-agent-package-poc-import.md 참조.

사용법:
  python -m scripts.import_agent_package \\
    --package-dir "C:/Users/ABC/Desktop/agent_package (1)" \\
    --user-email jeongoheo0225@gmail.com \\
    --project-title "agent_package PoC (6명)" \\
    [--pids pid_001,pid_002] [--synthetic] [--dry-run] [--reuse-project <id>]

보안: 패키지 JSON 은 실명·자유서술 PII 를 포함하므로 repo 로 복사·커밋하지 않는다.
이 스크립트는 --package-dir 경로를 읽기 전용으로만 참조한다.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import (
    Agent,
    AgentMemory,
    AsyncSessionLocal,
    ResearchProject,
    User,
    init_db,
)
from embedding.embedder import average_embedding, embed
from services.seed_service import recluster_project

# 패키지 6-Lens 섹션 헤더(### L1 …) → 우리 agent_memories 카테고리 매핑
_LENS_CATEGORY = {
    "L1": "l1_economic",
    "L2": "l2_decision",
    "L3": "l3_motivation",
    "L4": "l4_social",
    "L5": "l5_values",
    "L6": "l6_time",
}

# 기본 패키지 경로 (Desktop, repo 외부)
_DEFAULT_PACKAGE_DIR = r"C:/Users/ABC/Desktop/agent_package (1)"


# ── 패키지 파싱 ────────────────────────────────────────────────────────────

def load_manifest_pids(package_dir: Path) -> list[str]:
    """manifest.csv 에서 pid 목록을 읽는다. 없으면 agents/*.json 글롭."""
    manifest = package_dir / "manifest.csv"
    if manifest.exists():
        with open(manifest, encoding="utf-8-sig") as f:
            return [row["pid"] for row in csv.DictReader(f) if row.get("pid")]
    return sorted(p.stem for p in (package_dir / "agents").glob("pid_*.json"))


def parse_lens_reflections(persona_text: str) -> list[dict]:
    """persona_text 의 '## 6-Lens 전문가 분석' 섹션에서 L1~L6 블록을 추출.

    각 블록 → {category, text}. 섹션이 없으면 빈 리스트.
    """
    # 6-Lens 분석 섹션의 시작 위치 탐색
    m = re.search(r"^##\s*6-Lens\s*전문가\s*분석.*$", persona_text, re.MULTILINE)
    if not m:
        return []
    section = persona_text[m.end():]

    # 다음 최상위 '## ' 섹션 전까지로 한정
    nxt = re.search(r"^##\s", section, re.MULTILINE)
    if nxt:
        section = section[: nxt.start()]

    memories: list[dict] = []
    # ### L1 …  ~  다음 ### L? 또는 끝
    for block in re.finditer(
        r"^###\s*(L[1-6])\b([^\n]*)\n(.*?)(?=^###\s*L[1-6]\b|\Z)",
        section,
        re.MULTILINE | re.DOTALL,
    ):
        lens = block.group(1)
        heading = block.group(2).strip()
        body = block.group(3).strip()
        category = _LENS_CATEGORY.get(lens)
        if not category or not body:
            continue
        text = f"[{lens} {heading}]\n{body}" if heading else body
        memories.append({"category": category, "text": text})
    return memories


# 가명 풀 — 원본 실명 미사용. pid 순서로 결정적 배정(성별 인지). (plan 0010)
PSEUDONYMS_FEMALE = ["김서연", "이지우", "박하은", "최수아", "정예린", "강유진", "윤지민", "한소율"]
PSEUDONYMS_MALE = ["김도윤", "이준우", "박시우", "최지호", "정현우", "강민준", "윤태경", "한승재"]


def pick_pseudonym(gender: str, num: int) -> str:
    """성별·번호로 결정적 가명 배정. 성별 불명 시 여성 풀."""
    pool = PSEUDONYMS_MALE if "남" in gender else PSEUDONYMS_FEMALE
    return pool[(max(num, 1) - 1) % len(pool)]


def derive_display(meta: dict, pid: str) -> tuple[str, str, str]:
    """카드용 (display_name, emoji, intro_ko) — 가명 + age/gender 라벨."""
    resp = (meta or {}).get("respondent", {}) or {}
    age = (resp.get("age") or "").strip()
    gender = (resp.get("gender") or "").strip()
    num_str = pid.replace("pid_", "")
    num = int(num_str) if num_str.isdigit() else 1
    bits = [b for b in [age, gender] if b]
    label = " ".join(bits) if bits else "응답자"
    name = pick_pseudonym(gender, num)
    display_name = name  # 카드/대화에는 이름만 표시 — 인구통계는 intro_ko 로
    intro = f"{label} 인터뷰 기반 페르소나"
    return display_name, "👤", intro


# ── 적재 ──────────────────────────────────────────────────────────────────

async def resolve_user(email: str) -> User | None:
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.email == email.lower().strip()))
        return res.scalar_one_or_none()


async def ensure_user(email: str) -> User:
    """소유자 유저를 보장(없으면 생성). 데모 소스 적재 시 운영 DB 에 해당 계정이
    아직 로그인하지 않았을 수 있어, 패스워드 없는 소유자 행을 만들어 FK 를 충족한다."""
    email = email.lower().strip()
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is not None:
            return user
        user = User(
            id=str(uuid.uuid4()), email=email, hashed_pw=None,
            name=email.split("@")[0], role="researcher", is_active=True,
        )
        db.add(user)
        await db.commit()
        print(f"[IMPORT] 소유자 유저 생성: {email} (id={user.id[:8]}…)")
        return user


async def create_project(user_id: str, title: str, project_id: str | None = None) -> str:
    """프로젝트 생성. project_id 지정 시 그 ID 로 멱등 생성(이미 있으면 재사용).

    데모 소스(--as-demo-source)처럼 ID 가 고정돼야 운영 DB 에서도 데모가 찾을 수 있다.
    """
    project_id = project_id or str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(
            select(ResearchProject).where(ResearchProject.id == project_id)
        )).scalar_one_or_none()
        if existing is not None:
            print(f"[IMPORT] 프로젝트가 이미 존재 — 재사용: {project_id[:8]}…")
            return project_id
        db.add(ResearchProject(
            id=project_id,
            user_id=user_id,
            title=title,
            status="active",
            settings={"source": "agent_package", "import_kind": "poc"},
        ))
        await db.commit()
    return project_id


async def import_one(
    package_dir: Path,
    pid: str,
    project_id: str,
    *,
    synthetic: bool | None,
    dry_run: bool,
) -> dict:
    """단일 pid JSON 적재. 결과 요약 반환."""
    agent_json = json.loads((package_dir / "agents" / f"{pid}.json").read_text(encoding="utf-8"))

    system_message = agent_json.get("system_message", "")
    persona_header = agent_json.get("persona_header", "")
    persona_text = agent_json.get("persona_text", "")
    meta = agent_json.get("metadata", {}) or {}

    # persona_full_prompt: 패키지 의도대로 system + persona 를 결합해 그대로 보존
    persona_full_prompt = "\n\n".join(p for p in [system_message, persona_header + persona_text] if p)

    memories = parse_lens_reflections(persona_text)
    display_name, emoji, intro_ko = derive_display(meta, pid)

    if dry_run:
        return {
            "pid": pid, "status": "dry-run", "display_name": display_name,
            "memory_count": len(memories), "prompt_chars": len(persona_full_prompt),
        }

    # 6-Lens reflection 임베딩 → avg_embedding (V3 다양성·retrieval 대비)
    embeddings = [embed(m["text"], use_cache=False, synthetic=synthetic) for m in memories]
    avg_emb = average_embedding(embeddings) if embeddings else None

    resp = meta.get("respondent", {}) or {}
    scratch = {
        "age_range": resp.get("age"),
        "gender": resp.get("gender"),
        "original_id": meta.get("original_id"),
        "question_separator": agent_json.get("question_separator"),
        "format_instructions": agent_json.get("format_instructions"),
        "schema_version": agent_json.get("schema_version"),
        "has_interview": meta.get("has_interview"),
        "n_reflections": meta.get("n_reflections_lenses"),
        "package_method": meta.get("method"),
    }

    agent_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        db.add(Agent(
            id=agent_id,
            project_id=project_id,
            source_type="package",          # twin/survey 와 분리
            source_ref=pid,
            display_name=display_name,
            emoji=emoji,
            intro_ko=intro_ko,
            persona_params=None,            # 수치 미보유 (후속 복원 가능)
            persona_full_prompt=persona_full_prompt,
            scratch=scratch,
            responses=None,                 # 구조화 234문항 raw 미보유
            avg_embedding=avg_emb,
        ))
        await db.flush()
        for mem, emb in zip(memories, embeddings):
            db.add(AgentMemory(
                agent_id=agent_id,
                source="base",
                category=mem["category"],
                text=mem["text"],
                importance=70,
                embedding=emb,
            ))
        await db.commit()

    return {
        "pid": pid, "status": "ok", "agent_id": agent_id,
        "display_name": display_name, "memory_count": len(memories),
        "prompt_chars": len(persona_full_prompt),
    }


async def main_async(args) -> None:
    package_dir = Path(args.package_dir)
    if not (package_dir / "agents").is_dir():
        raise SystemExit(f"[ERR] agents/ 폴더를 찾을 수 없습니다: {package_dir}")

    await init_db()

    pids = args.pids.split(",") if args.pids else load_manifest_pids(package_dir)
    pids = [p.strip() for p in pids if p.strip()]
    print(f"[IMPORT] 대상 {len(pids)}명: {', '.join(pids)} (dry_run={args.dry_run})")

    # 사용자 확인 — 데모 소스 적재(--as-demo-source/--ensure-owner)는 없으면 생성
    if (args.as_demo_source or args.ensure_owner) and not args.dry_run:
        user = await ensure_user(args.user_email)
    else:
        user = await resolve_user(args.user_email)
        if not user:
            raise SystemExit(
                f"[ERR] 사용자 없음: {args.user_email} — 먼저 해당 계정으로 1회 로그인하거나 --ensure-owner 사용."
            )
    print(f"[IMPORT] 사용자: {user.email} (id={user.id[:8]}…)")

    # 프로젝트 결정
    fixed_id = args.project_id
    if args.as_demo_source:
        # 데모 소스로 적재 — demo_service.SOURCE_PROJECT_ID 와 동일 ID 로 고정해
        # 운영 DB 에서도 /api/demo/session 이 env 변경 없이 이 6명을 복제한다.
        from services import demo_service
        fixed_id = demo_service.SOURCE_PROJECT_ID
        print(f"[IMPORT] 데모 소스 모드 — 고정 project_id={fixed_id} 로 적재")

    if args.reuse_project:
        project_id = args.reuse_project
        print(f"[IMPORT] 기존 프로젝트 재사용: {project_id[:8]}…")
    elif args.dry_run:
        project_id = "00000000-0000-0000-0000-000000000000"
        print("[IMPORT] dry-run — 프로젝트 생성 생략")
    else:
        project_id = await create_project(user.id, args.project_title, project_id=fixed_id)
        print(f"[IMPORT] 프로젝트 확보: '{args.project_title}' (id={project_id})")

    ok = 0
    for pid in pids:
        try:
            r = await import_one(
                package_dir, pid, project_id,
                synthetic=args.synthetic, dry_run=args.dry_run,
            )
            ok += 1
            print(f"  [{r['status']}] {pid} → {r['display_name']} "
                  f"(메모리 {r['memory_count']}건, prompt {r['prompt_chars']:,}자)")
        except Exception as e:  # noqa: BLE001 — PoC: 1건 실패가 전체를 막지 않도록
            print(f"  [FAIL] {pid}: {e}")

    print(f"\n[IMPORT] 완료: {ok}/{len(pids)} 성공")

    if not args.dry_run and not args.reuse_project and ok >= 2:
        k = await recluster_project(project_id, k=min(5, ok))
        print(f"[KMEANS] {k or 0} 클러스터 재배정." if k else "[KMEANS] skip.")

    if not args.dry_run:
        print(f"[IMPORT] 프로젝트 ID: {project_id}  ← 되돌리려면 이 프로젝트 삭제")


def main():
    p = argparse.ArgumentParser(description="agent_package → Ditto agents 적재")
    p.add_argument("--package-dir", default=_DEFAULT_PACKAGE_DIR, help="패키지 루트 경로")
    p.add_argument("--user-email", default="jeongoheo0225@gmail.com", help="적재 대상 사용자")
    p.add_argument("--project-title", default="agent_package PoC (6명)", help="신규 프로젝트 제목")
    p.add_argument("--pids", default=None, help="쉼표구분 pid (기본: manifest 전체)")
    p.add_argument("--reuse-project", default=None, help="기존 프로젝트 UUID 에 추가 적재")
    p.add_argument("--project-id", default=None, help="이 UUID 로 프로젝트를 멱등 생성(이미 있으면 재사용)")
    p.add_argument("--as-demo-source", action="store_true",
                   help="데모 소스로 적재 — demo_service.SOURCE_PROJECT_ID 고정 ID 사용 (운영 데모용)")
    p.add_argument("--ensure-owner", action="store_true",
                   help="소유자 유저가 없으면 생성(운영 DB 에 해당 계정 미로그인 시)")
    p.add_argument("--synthetic", action="store_true", help="임베딩 강제 합성 (OPENAI 키 없이)")
    p.add_argument("--dry-run", action="store_true", help="DB INSERT 없이 검증만")
    args = p.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
