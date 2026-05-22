"""_gen_demo_surveys.py — _demo_q.json → demoScenario.ts 의 DEMO_SURVEYS 블록 재생성.

전체 문항(범용 267 + 도메인 82)을 렌즈별 메타와 함께 TS 배열로 주입한다.
정적 부분(BRIEF/INTERVIEW/STEPS 등)은 건드리지 않고 DEMO_SURVEYS 상수만 교체.
일회성 보조 도구(커밋 대상 아님).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TS = ROOT / "frontend" / "src" / "lib" / "demoScenario.ts"
DATA = Path(__file__).resolve().parent.parent / "_demo_q.json"

LENS_LABEL = {
    "L1": "경제적 합리성", "L2": "의사결정 스타일", "L3": "동기 구조",
    "L4": "사회적 영향", "L5": "가치 사슬", "L6": "시간 지향", "C": "통제·인구통계",
}


def js(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def items_ts(items: list[dict], indent: str) -> str:
    out = []
    for it in items:
        out.append(
            f"{indent}{{ lens: {js(it['lens'])}, scaleName: {js(it.get('scaleName') or '')}, "
            f"scale: {js(it.get('scale') or '')}, q: {js(it['q'])} }},"
        )
    return "\n".join(out)


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    mind, domain = data["mindlens"], data["domain"]

    labels = ",\n".join(f"  {k}: {js(v)}" for k, v in LENS_LABEL.items())

    block = f"""/** 설문 렌즈(L1~L6+통제) 한국어 라벨 — 질문 관리 화면의 접기 섹션 제목. */
export const SURVEY_LENS_LABELS: Record<string, string> = {{
{labels},
}};

/**
 * 2단계 — 설문 2종 + 인터뷰 1종 (실제 적용 문항 전체).
 * 설문 1: Twin-2K-500 한국화(Toubia 2025) — 범용 6-Lens 심리·행동 배터리({len(mind)}문항).
 * 설문 2: 위 척도를 포토이즘(셀프 사진관) 맥락으로 변형한 도메인 특화 설문({len(domain)}문항).
 * 문항은 실제 응답자에게 제시된 원본이며, 화면에서는 렌즈별로 접어서 본다.
 */
export const DEMO_SURVEYS = [
  {{
    key: 'mindlens',
    title: '기본 소비자 특성 설문',
    desc: '소비 성향·의사결정·가치관을 폭넓게 측정하는 표준 문항 (검증된 심리척도 기반)',
    note: '주제와 무관하게 적용되는 공통 문항으로, AI 소비자의 성향 점수의 토대가 됩니다. 렌즈(L1~L6·통제)별로 접어서 볼 수 있어요.',
    items: [
{items_ts(mind, '      ')}
    ],
  }},
  {{
    key: 'domain',
    title: '포토이즘 도메인 특화 설문',
    desc: '동일한 성향 척도를 셀프 사진관 맥락(매장·콘셉트·재방문)으로 변형',
    note: '범용 척도를 포토이즘 상황에 투영해 도메인 행동을 측정합니다.',
    items: [
{items_ts(domain, '      ')}
    ],
  }},
] as const;"""

    src = TS.read_text(encoding="utf-8")
    # 기존 DEMO_SURVEYS 주석 + 상수 블록 교체:
    #   '/**\n * 2단계' 주석부터 'export const DEMO_SURVEYS = [' ... '\n] as const;' 까지.
    pat = re.compile(
        r"/\*\*\s*\n \* 2단계.*?export const DEMO_SURVEYS = \[.*?\n\] as const;",
        re.DOTALL,
    )
    new_src, n = pat.subn(block, src)
    if n != 1:
        raise SystemExit(f"[ERR] DEMO_SURVEYS 블록 교체 실패 (matches={n})")
    TS.write_text(new_src, encoding="utf-8")
    print(f"[OK] DEMO_SURVEYS 재생성 — mindlens {len(mind)} · domain {len(domain)} 문항")


if __name__ == "__main__":
    main()
