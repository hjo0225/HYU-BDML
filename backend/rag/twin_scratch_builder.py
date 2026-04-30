"""Twin-2K-500 (Toubia et al. 2025) `persona_summary` → scratch dict 변환.

Hugging Face `LLM-Digital-Twin/Twin-2K-500` (config="full_persona") 로드 시
각 행은 `pid`, `persona_text`, `persona_summary`, `persona_json`을 가진다.
이 모듈은 영어 정형 텍스트인 `persona_summary`를 파싱해 scratch dict를 만든다.

Twin은 영어 원본을 임베딩에 그대로 사용한다(`docs/adr/0005-...`). 발화 시
`prompts/twin_utterance.py`에서 LLM이 한국어로 변환한다.
"""
from __future__ import annotations

import re


# persona_summary 첫 블록의 인구통계 헤더 (응답 순서 고정)
_DEMO_KEYS = (
    "Geographic region",
    "Gender",
    "Age",
    "Education level",
    "Race",
    "Citizen of the US",
    "Marital status",
    "Religion",
    "Religious attendance",
    "Political affiliation",
    "Income",
    "Political views",
    "Household size",
    "Employment status",
)

# Big 5 + need for cognition (가장 중요한 스코어 6개) — 트레잇 라벨 변환용
_BIG5_KEYS = ("extraversion", "agreeableness", "conscientiousness", "openness", "neuroticism")

_SCORE_RE = re.compile(
    r"score_(\w+)\s*=\s*([\-\d.]+)\s*\((\d+)(?:st|nd|rd|th)\s+percentile\)"
)
# wave1_/wave2_ 접두 점수도 잡는다 (e.g. wave1_score_conscientiousness)
_WAVE_SCORE_RE = re.compile(
    r"wave\d_score_(\w+)\s*=\s*([\-\d.]+)\s*\((\d+)(?:st|nd|rd|th)\s+percentile\)"
)


def _parse_demographics(summary: str) -> dict[str, str]:
    """첫 블록의 'Header: value' 라인을 모아 dict로 반환."""
    out: dict[str, str] = {}
    for key in _DEMO_KEYS:
        m = re.search(rf"^{re.escape(key)}:\s*(.+)$", summary, re.MULTILINE)
        if m:
            out[key] = m.group(1).strip()
    return out


def _parse_scores(summary: str) -> dict[str, dict]:
    """`score_<name> = <value> (<percentile>th percentile)` 모두 추출."""
    out: dict[str, dict] = {}
    for name, raw_value, raw_pct in _SCORE_RE.findall(summary):
        try:
            out[name] = {"value": float(raw_value), "percentile": int(raw_pct)}
        except ValueError:
            continue
    # wave 접두도 'wave1_' 같은 prefix를 키에 포함해 둠
    for name, raw_value, raw_pct in _WAVE_SCORE_RE.findall(summary):
        key = f"wave_{name}"
        if key not in out:
            try:
                out[key] = {"value": float(raw_value), "percentile": int(raw_pct)}
            except ValueError:
                continue
    return out


_QUAL_PATTERNS = {
    "aspire": re.compile(
        r'type of person you\s+aspire to be.*?They answered:\s*"([^"]+)"',
        re.DOTALL,
    ),
    "ought": re.compile(
        r'type of person you\s+ought to be.*?They answered:\s*"([^"]+)"',
        re.DOTALL,
    ),
    "actual": re.compile(
        r'type of person you\s+actually are.*?They answered:\s*"([^"]+)"',
        re.DOTALL,
    ),
}


def _parse_qualitative(summary: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for label, pat in _QUAL_PATTERNS.items():
        m = pat.search(summary)
        if m:
            out[label] = m.group(1).strip()
    return out


def _age_midpoint(age_range: str) -> int | None:
    """'18-29' → 23, '65+' → 70, '50-64' → 57. 숫자 추출 실패 시 None."""
    if not age_range:
        return None
    nums = [int(n) for n in re.findall(r"\d+", age_range)]
    if not nums:
        return None
    if len(nums) == 1:
        return nums[0] + 5  # "65+" → 70
    return (nums[0] + nums[1]) // 2


def _normalize_gender(value: str) -> str:
    s = (value or "").strip().lower()
    if s.startswith("m"):
        return "male"
    if s.startswith("f"):
        return "female"
    return s or "unspecified"


def _short_region(region: str) -> str:
    """'South (TX, OK, AR, ...)' → 'South' (괄호 앞 단어만)."""
    if not region:
        return ""
    return region.split("(")[0].strip()


def _trait_labels(scores: dict[str, dict]) -> list[str]:
    """Big 5 점수 → 트레잇 라벨 (특징적인 것만)."""
    labels: list[str] = []
    for key in _BIG5_KEYS:
        s = scores.get(key)
        if not s:
            continue
        pct = s["percentile"]
        if pct >= 75:
            labels.append(f"high {key}")
        elif pct <= 25:
            labels.append(f"low {key}")
    if "needforcognition" in scores and scores["needforcognition"]["percentile"] >= 70:
        labels.append("high need for cognition")
    if "minimalism" in scores and scores["minimalism"]["percentile"] >= 70:
        labels.append("minimalist")
    if "GREEN" in scores and scores["GREEN"]["percentile"] >= 70:
        labels.append("environmentalist")
    return labels[:6]


def _build_intro_ko(demo: dict[str, str], scratch_age: int | None, traits: list[str]) -> str:
    """카드 하단에 노출되는 1~2문장 한국어 소개."""
    region = _short_region(demo.get("Geographic region", ""))
    gender_kr = {"male": "남성", "female": "여성"}.get(_normalize_gender(demo.get("Gender", "")), "")
    age_part = f"{scratch_age}세" if scratch_age else (demo.get("Age") or "나이 미상")
    employment = demo.get("Employment status", "직업 미상")
    political = demo.get("Political views") or demo.get("Political affiliation") or ""

    head = f"{age_part} {gender_kr} ({demo.get('Race', '')}, {region} 거주)"
    head = re.sub(r"\s+", " ", head).replace(" ,", ",").strip()
    tail_parts = [employment]
    if political:
        tail_parts.append(political)
    if traits:
        tail_parts.append(", ".join(traits[:3]))
    tail = " · ".join(p for p in tail_parts if p)
    return f"{head}. {tail}." if tail else f"{head}."


_GENDER_EMOJI = {"male": "👨", "female": "👩"}


def build_display_name(pid: str) -> str:
    """카드용 표시 이름. 익명 보장 — pid 그대로."""
    return f"Twin {pid}"


def build_emoji(demo: dict[str, str]) -> str:
    return _GENDER_EMOJI.get(_normalize_gender(demo.get("Gender", "")), "🧑")


def build_scratch(pid: str, persona_summary: str) -> dict:
    """Twin-2K-500 응답자 한 명의 persona_summary → scratch dict.

    출력은 `services/lab_service.py`의 `_format_profile` 및
    `routers/lab.py`의 LabTwin 응답에 사용된다.
    """
    demo = _parse_demographics(persona_summary)
    scores = _parse_scores(persona_summary)
    qual = _parse_qualitative(persona_summary)

    age = _age_midpoint(demo.get("Age", ""))
    gender = _normalize_gender(demo.get("Gender", ""))
    region = _short_region(demo.get("Geographic region", ""))
    occupation = demo.get("Employment status", "")
    traits = _trait_labels(scores)

    scratch = {
        # 핵심 인구통계
        "twin_pid": pid,
        "age": age,
        "age_range": demo.get("Age") or "",
        "gender": gender,
        "region": region,
        "occupation": occupation,
        # 추가 인구통계 (메모리·프롬프트 컨텍스트용)
        "education": demo.get("Education level", ""),
        "race": demo.get("Race", ""),
        "marital_status": demo.get("Marital status", ""),
        "religion": demo.get("Religion", ""),
        "political_affiliation": demo.get("Political affiliation", ""),
        "political_views": demo.get("Political views", ""),
        "income": demo.get("Income", ""),
        "household_size": demo.get("Household size", ""),
        # 페르소나 특성
        "traits": traits,
        "big5": {k: scores[k] for k in _BIG5_KEYS if k in scores},
        # 자기개념 정성응답 (1인칭 영어 원문)
        "aspire": qual.get("aspire", ""),
        "ought": qual.get("ought", ""),
        "actual": qual.get("actual", ""),
        # 카드 디스플레이
        "display_name": build_display_name(pid),
        "emoji": build_emoji(demo),
    }
    scratch["intro_ko"] = _build_intro_ko(demo, age, traits)
    return scratch
