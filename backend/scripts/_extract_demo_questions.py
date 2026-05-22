"""_extract_demo_questions.py — agent_package persona_text 에서 데모용 질문 풀 추출.

범용(MindLens) + 포토이즘 도메인 설문의 **질문만** 뽑아 렌즈별로 구조화한 JSON 을
stdout 으로 출력한다. 응답자 답변(Answer:)·MPL 매트릭스 행은 제외(PII 회피 + 데모 간결화).

전략: 모든 문항은 'Question Type:' 줄을 가진다. 그 줄을 앵커로 삼아 바로 위 텍스트
블록을 질문 프롬프트로 잡으면 번호형·Q#.·[정책N]·자유 시나리오를 모두 포착하고,
매트릭스 행/답변은 자연히 배제된다.

이 스크립트는 일회성 데이터 생성 보조 도구다(커밋 대상 아님).

사용: python -m scripts._extract_demo_questions [pid_001] > _demo_q.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

PKG = Path(r"C:/Users/ABC/Desktop/agent_package (1)/agents")

LENS_OF = {"1": "L1", "2": "L2", "3": "L3", "4": "L4", "5": "L5", "6": "L6", "C": "C"}
LENS_LABEL = {
    "L1": "경제적 합리성", "L2": "의사결정 스타일", "L3": "동기 구조",
    "L4": "사회적 영향", "L5": "가치 사슬", "L6": "시간 지향", "C": "통제·인구통계",
}

_SEC = re.compile(r"^###\s*Section\s+([0-9C]+)-(\S+):\s*(.+?)\s*$")
_OPT_NUM = re.compile(r"^\d+\s*[=\-]")
_LEADING_NUM = re.compile(r"^(Q?\d+)\.\s*")


def _scale_label(opts: list[str], qtype: str) -> str:
    joined = " ".join(opts)
    nums = [o for o in opts if _OPT_NUM.match(o)]
    if "동의" in joined and nums:
        return f"{len(nums)}점 동의"
    if "찬성" in joined and nums:
        return f"{len(nums)}점 찬반"
    if "추첨" in joined or re.search(r"\bL\s*=", joined):
        return "선택(MPL)"
    if nums:
        return f"{len(nums)}점 척도"
    if "Single" in qtype:
        return "단일 선택"
    if "Text" in qtype or "주관식" in qtype:
        return "주관식"
    return "선택"


def _clean_prompt(buf: list[str]) -> str:
    """버퍼 줄들 → 질문 프롬프트. 부제'(...)'·지시사항·Part 안내는 제거."""
    keep: list[str] = []
    for s in buf:
        s = s.strip()
        if not s:
            continue
        if re.match(r"^\(.*\)$", s):          # 부제
            continue
        if s.startswith(("지시사항", "Part 1", "Part 2", "형식.", "채점")):
            continue
        keep.append(s)
    q = " ".join(keep)
    q = _LEADING_NUM.sub("", q).strip()        # 선두 'N.'/'Q#.' 제거
    q = re.sub(r"\s+", " ", q)
    return q[:300]


def parse_block(text: str) -> list[dict]:
    lines = text.splitlines()
    out: list[dict] = []
    lens = scale_name = None
    buf: list[str] = []
    cur: dict | None = None        # 직전 Question Type 으로 만든 item (옵션 수집 대상)
    in_opts = False
    for ln in lines:
        s = ln.strip()
        m = _SEC.match(ln)
        if m:
            lens = LENS_OF.get(m.group(1), m.group(1))
            scale_name = re.sub(r"\s*—\s*도메인\s*$", "", m.group(3)).strip()
            buf, cur, in_opts = [], None, False
            continue
        if s.startswith("Question Type:"):
            q = _clean_prompt(buf)
            buf = []
            in_opts = False
            qtype = s.split(":", 1)[1].strip()
            if q and lens:
                cur = {"lens": lens, "scaleName": scale_name, "_qtype": qtype, "_opts": [], "q": q}
                out.append(cur)
            else:
                cur = None
            continue
        if s.startswith("Options:"):
            in_opts = True
            continue
        if s.startswith("Answer:"):
            in_opts = False
            buf = []
            continue
        if in_opts:
            if cur is not None and _OPT_NUM.match(s):
                cur["_opts"].append(s)
            continue
        buf.append(s)
    # 스케일 라벨 후처리 + 임시키 제거
    for it in out:
        it["scale"] = _scale_label(it.pop("_opts"), it.pop("_qtype"))
    return out


def main() -> None:
    pid = sys.argv[1] if len(sys.argv) > 1 else "pid_001"
    t = json.loads((PKG / f"{pid}.json").read_text(encoding="utf-8"))["persona_text"]
    g0 = t.find("## 범용 소비자 특성 설문")
    g1 = t.find("## 포토이즘 도메인 특화 설문")
    g2 = t.find("## 심층 인터뷰")
    result = {"mindlens": parse_block(t[g0:g1]), "domain": parse_block(t[g1:g2])}
    for k, v in result.items():
        print(f"[{k}] 총 {len(v)}문항 — {dict(Counter(x['lens'] for x in v))}", file=sys.stderr)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
