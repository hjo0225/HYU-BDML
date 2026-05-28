"""pid_xxx.txt → 홀드아웃 후보 Q&A 페어 추출 (plan 0023, P3 자동+수동제외).

블록 구조: `Q\\d+\\.` 또는 `\\d+\\.` 헤더 → `Question Type:` → (`Options:`) → `Answer:`.
calibration grid(여러 sub-row 가 각자 Answer 가지는 Matrix) 는 multi-answer 라
1블록=1Answer 규칙으로 자동 제외된다. demographics 섹션(C-*)과 6-Lens reflection
헤더(`### L1~L6`)도 lens 가 없어 자연스레 제외.

추가로 `## 심층 인터뷰 응답 (raw)` 섹션(Q5~Q29) 도 별도 핸들러로 추출한다.
파일에는 답변만 있고 질문 텍스트가 비어 있어, `interview_questions.json` 에서
번호 → 질문/lens/domain 매핑을 가져와 join 한다.

수동 제외 리스트(질문 id 기준)는 `exclude.yaml` 로 지원 가능 — PoC 에선 미사용.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_SECTION_RE = re.compile(r"^###\s+Section\s+([A-Z0-9]+)-(\d+):\s*(.+)$")
_REFLECTION_HEADER_RE = re.compile(r"^###\s+L\d\s")  # ### L1 경제적 합리성 …
_Q_RE = re.compile(r"^Q(\d+)\.\s*(.+)$")
_LIKERT_RE = re.compile(r"^(\d+)\.\s+(.+)$")  # Matrix 내 Likert sub-item
_QTYPE_RE = re.compile(r"^Question Type:\s*(.+)$")
_ANSWER_RE = re.compile(r"^Answer:\s*(.+)$")

_INTERVIEW_HEADER_RE = re.compile(r"^##\s+심층\s+인터뷰\s+응답")
_INTERVIEW_Q_RE = re.compile(r"^Q(\d+)\.\s*$")  # 인터뷰 블록은 질문 텍스트가 비어있음
_INTERVIEW_ANSWER_RE = re.compile(r"^→\s*(.+)$")

_SECTION_LENS = {"1": "L1", "2": "L2", "3": "L3", "4": "L4", "5": "L5", "6": "L6"}

_INTERVIEW_QMAP_PATH = Path(__file__).resolve().parent / "interview_questions.json"
_interview_qmap_cache: dict | None = None


def _load_interview_qmap() -> dict:
    """interview_questions.json (모듈 인접 파일) 로 부터 인터뷰 질문 메타 로드.

    파일이 없으면 빈 dict — 인터뷰 블록을 통째로 건너뜀.
    """
    global _interview_qmap_cache
    if _interview_qmap_cache is None:
        if _INTERVIEW_QMAP_PATH.exists():
            data = json.loads(_INTERVIEW_QMAP_PATH.read_text(encoding="utf-8"))
            _interview_qmap_cache = {k: v for k, v in data.items() if not k.startswith("_")}
        else:
            _interview_qmap_cache = {}
    return _interview_qmap_cache


@dataclass
class QAPair:
    """홀드아웃 후보 1건."""
    question_id: str       # "S3-1_D_q5" 같은 결정적 id
    section: str           # "3-1"
    lens: str              # "L1"~"L6"
    domain: bool           # 포토이즘 도메인 반복 섹션 여부
    question: str          # 문항 평문
    qtype: str             # "Single Choice" | "Text Entry" | "Matrix"(=Likert) | "Slider" 등
    answer: str            # 원본 인간 응답
    section_label: str     # "Regulatory Focus Scale (조절초점 척도)"

    def to_dict(self) -> dict:
        return {
            "question_id": self.question_id,
            "section": self.section,
            "lens": self.lens,
            "domain": self.domain,
            "question": self.question,
            "qtype": self.qtype,
            "answer": self.answer,
            "section_label": self.section_label,
        }


def _slug(text: str, max_len: int = 30) -> str:
    """문항 평문 → id 슬러그 (공백 → 언더스코어, 특수문자 제거)."""
    s = re.sub(r"[^\w가-힣]+", "_", text).strip("_")
    return s[:max_len]


def parse_pid_txt(
    path: Path | str,
    *,
    exclude_interview_q: set[int] | None = None,
) -> list[QAPair]:
    """pid_xxx.txt 한 파일에서 홀드아웃 후보 Q&A 페어를 추출.

    Args:
        path: pid 파일 경로.
        exclude_interview_q: 인터뷰 블록에서 제외할 Q번호 집합 (예: {5, 6}).

    Returns:
        QAPair 리스트 (블록당 1개, multi-Answer 블록 자동 제외).
    """
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()

    items: list[QAPair] = []
    section: str | None = None
    lens: str | None = None
    section_label: str = ""
    domain: bool = False
    seen_q_in_section: int = 0  # section 내 Q 카운터 (id 결정적 생성)

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].rstrip()

        # ### L1~L6 reflection 섹션 → 거기서 끝
        if _REFLECTION_HEADER_RE.match(line):
            break

        m_sec = _SECTION_RE.match(line)
        if m_sec:
            prefix, num, label = m_sec.group(1), m_sec.group(2), m_sec.group(3)
            section_label = label
            domain = "도메인" in label
            if prefix.isdigit() and prefix in _SECTION_LENS:
                section = f"{prefix}-{num}"
                lens = _SECTION_LENS[prefix]
            else:
                # Section C-* (인구통계·금융·수리) 는 평가 대상에서 제외
                section = None
                lens = None
            seen_q_in_section = 0
            i += 1
            continue

        # 문항 헤더 — Q1.  또는  1.
        m_q = _Q_RE.match(line)
        is_q = m_q is not None
        if not is_q:
            m_q2 = _LIKERT_RE.match(line)
            # Likert sub-item 은 lens 있는 섹션 안에서만 인정
            if m_q2 is not None and lens is not None:
                m_q = m_q2
                is_q = True

        if is_q and lens is not None:
            q_text = m_q.group(2).strip()
            seen_q_in_section += 1

            # 블록 수집: 다음 문항 헤더 / 섹션 헤더 / 반사 헤더 직전까지
            block_lines: list[str] = []
            j = i + 1
            while j < n:
                nl = lines[j].rstrip()
                if _SECTION_RE.match(nl) or _REFLECTION_HEADER_RE.match(nl):
                    break
                if _Q_RE.match(nl):
                    break
                # 빈줄 다음 N. 새 문항(같은 섹션 내) 일 때도 종료
                if _LIKERT_RE.match(nl) and j > 0 and lines[j - 1].strip() == "":
                    break
                block_lines.append(nl)
                j += 1

            qtype: str | None = None
            answers: list[str] = []
            for bl in block_lines:
                m_t = _QTYPE_RE.match(bl)
                if m_t:
                    qtype = m_t.group(1).strip()
                m_a = _ANSWER_RE.match(bl)
                if m_a:
                    answers.append(m_a.group(1).strip())

            if qtype and len(answers) == 1:
                qid = f"S{section}{'_D' if domain else ''}_{seen_q_in_section:03d}_{_slug(q_text)}"
                items.append(QAPair(
                    question_id=qid,
                    section=section or "",
                    lens=lens,
                    domain=domain,
                    question=q_text,
                    qtype=qtype,
                    answer=answers[0],
                    section_label=section_label,
                ))
            i = j
            continue

        i += 1

    # ── 인터뷰 블록 (## 심층 인터뷰 응답) — 별도 핸들러로 추가 ───────────
    items.extend(parse_interview_block(lines, exclude_q_numbers=exclude_interview_q))

    return items


def parse_interview_block(
    lines: list[str],
    *,
    exclude_q_numbers: set[int] | None = None,
) -> list[QAPair]:
    """`## 심층 인터뷰 응답 (raw)` 섹션에서 Q&A 추출.

    파일에는 답변만 있고 질문 텍스트가 비어 있어, interview_questions.json 의
    번호별 매핑(question/lens/domain) 을 join 한다. 매핑에 없는 번호는 skip.

    한 Q 의 답변이 여러 줄일 수도 있어 `→ ` 줄을 누적한다.

    Args:
        lines: pid 파일 전체 라인.
        exclude_q_numbers: 제외할 Q번호 집합 (예: {5, 6}). yes/no·장문 등
            judge 평가에 부적합한 질문 제거용.
    """
    qmap = _load_interview_qmap()
    if not qmap:
        return []
    excluded = exclude_q_numbers or set()

    items: list[QAPair] = []
    in_block = False
    pending_q: int | None = None
    pending_answer_lines: list[str] = []

    def _flush():
        nonlocal pending_q, pending_answer_lines
        if pending_q is None:
            pending_answer_lines = []
            return
        if pending_q in excluded:
            pending_q = None
            pending_answer_lines = []
            return
        meta = qmap.get(str(pending_q))
        answer = " ".join(pending_answer_lines).strip()
        if meta and answer:
            q_text = meta["question"]
            items.append(QAPair(
                question_id=f"INT_Q{pending_q:02d}_{_slug(q_text)}",
                section="INT",
                lens=meta["lens"],
                domain=bool(meta.get("domain", False)),
                question=q_text,
                qtype="Interview",
                answer=answer,
                section_label="심층 인터뷰",
            ))
        pending_q = None
        pending_answer_lines = []

    for raw in lines:
        line = raw.rstrip()

        if _INTERVIEW_HEADER_RE.match(line):
            in_block = True
            continue
        if not in_block:
            continue

        # 다른 ## 섹션 시작 시 인터뷰 블록 종료
        if line.startswith("## ") and not _INTERVIEW_HEADER_RE.match(line):
            _flush()
            break

        m_q = _INTERVIEW_Q_RE.match(line)
        if m_q:
            _flush()
            pending_q = int(m_q.group(1))
            continue

        m_a = _INTERVIEW_ANSWER_RE.match(line)
        if m_a:
            pending_answer_lines.append(m_a.group(1).strip())
            continue

        # `→` 가 없는 후속 줄(드물지만 멀티라인 답변 후속)
        if pending_q is not None and line.strip() and not line.startswith("##"):
            pending_answer_lines.append(line.strip())

    _flush()
    return items


def summarize(items: list[QAPair]) -> dict:
    """파서 결과 진단용 요약."""
    by_lens: dict[str, int] = {}
    by_type: dict[str, int] = {}
    n_domain = 0
    for it in items:
        by_lens[it.lens] = by_lens.get(it.lens, 0) + 1
        by_type[it.qtype] = by_type.get(it.qtype, 0) + 1
        if it.domain:
            n_domain += 1
    return {
        "total": len(items),
        "by_lens": by_lens,
        "by_type": by_type,
        "domain_count": n_domain,
    }


if __name__ == "__main__":
    import json
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        r"C:/Users/ABC/Desktop/agent_package (1)/personas_readable/pid_001.txt"
    )
    pairs = parse_pid_txt(target)
    print(json.dumps(summarize(pairs), ensure_ascii=False, indent=2))
    print("\n=== 샘플 5건 ===")
    for p in pairs[:5]:
        print(f"\n[{p.lens} · {p.section} · {p.qtype}] {p.question_id}")
        print(f"Q: {p.question[:80]}")
        print(f"A: {p.answer[:80]}")
