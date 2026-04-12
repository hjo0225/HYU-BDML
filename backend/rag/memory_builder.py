"""
memory_builder.py
row + codebook → 14개 카테고리 메모리 텍스트 + LLM importance 부여

함수:
    build_all_memory_texts(row, codebook) → List[Dict]
    attach_importance(memories) → List[Dict]
"""

from __future__ import annotations

import json
import math
import os
from typing import Any

import pandas as pd

# 기본 importance (API 실패 시 fallback)
DEFAULT_IMPORTANCE = 25
NO_IMPORTANCE_VALUE = 50


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------

def _safe_val(row: dict, col: str) -> Any:
    v = row.get(col)
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _decode(row: dict, col: str, codebook: dict) -> str | None:
    raw = _safe_val(row, col)
    if raw is None:
        return None
    var_key = col.replace("ps_", "") if col.startswith("ps_") else col
    entry = codebook.get(var_key)
    if entry is None:
        return None
    value_map = entry.get("value_map")
    if value_map is None:
        return str(raw) if str(raw).strip() else None
    try:
        code = int(float(raw))
    except (ValueError, TypeError):
        return None
    return value_map.get(code) or value_map.get(str(code))


def _parse_json_col(raw: Any) -> list:
    if raw is None:
        return []
    try:
        if isinstance(raw, float) and math.isnan(raw):
            return []
    except (TypeError, ValueError):
        pass
    try:
        return json.loads(raw) if isinstance(raw, str) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _active_cols(row: dict, codebook: dict, prefix: str, value_check=None) -> list[str]:
    """prefix로 시작하는 컬럼 중 value_check(raw_value)가 True인 항목의 decoded label 반환."""
    labels = []
    for col, v in row.items():
        if not col.startswith(f"ps_{prefix}"):
            continue
        raw = _safe_val(row, col)
        if raw is None:
            continue
        if value_check is not None and not value_check(raw):
            continue
        label = _decode(row, col, codebook)
        if label and label not in ("아니오", "비보유", "비이용", "없음"):
            labels.append(label)
    return labels


def _is_one(v) -> bool:
    try:
        return int(float(v)) == 1
    except (ValueError, TypeError):
        return False


def _fmt_ratio(v, name: str) -> str | None:
    try:
        r = float(v)
        return f"{name} {r * 100:.0f}%"
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 14개 메모리 빌더
# ---------------------------------------------------------------------------

def _build_appliances(row: dict, codebook: dict) -> dict | None:
    """가전 보유 현황"""
    # 대형/소형/주방/디지털 기기 - 보유(1)인 것만
    owned = []
    for col in row:
        if not col.startswith("ps_A"):
            continue
        raw = _safe_val(row, col)
        if raw is None:
            continue
        try:
            if int(float(raw)) != 1:
                continue
        except (ValueError, TypeError):
            continue
        label = _decode(row, col, codebook)
        if label and label not in ("보유", "이용"):
            owned.append(label)
        elif label in ("보유", "이용"):
            # description에서 가전명 추출
            var_key = col.replace("ps_", "")
            desc = codebook.get(var_key, {}).get("description", "")
            # description 예: "가전_대형가전_TV" → "TV"
            parts = desc.split("_")
            if len(parts) >= 3:
                owned.append(parts[-1])

    if not owned:
        return None

    text = f"집에 보유한 가전·기기: {', '.join(owned)}"
    return {"category": "appliances", "text": text}


def _build_food_lifestyle(row: dict, codebook: dict) -> dict | None:
    """식생활 습관"""
    parts = []

    # 식생활 행동 (binary)
    food_behaviors = []
    behavior_cols = {
        "ps_B0013": "배달앱으로 음식을 주문한다",
        "ps_B0014": "혼밥을 즐기는 편이다",
        "ps_B0015": "혼술을 즐기는 편이다",
        "ps_B0016": "커피전문점을 자주 이용한다",
        "ps_B0017": "베이커리를 자주 이용한다",
        "ps_B0018": "패스트푸드를 자주 이용한다",
        "ps_B0019": "샐러드/샌드위치 전문점을 이용한다",
        "ps_B0020": "피자/파스타 전문점을 이용한다",
        "ps_B0021": "치킨 전문점을 이용한다",
        "ps_B0022": "패밀리레스토랑을 이용한다",
        "ps_B0012": "도시락/간편식(HMR)을 구매한다",
    }
    for col, desc in behavior_cols.items():
        v = _safe_val(row, col)
        if v is not None and _is_one(v):
            food_behaviors.append(desc)

    if food_behaviors:
        parts.append("식생활 특징: " + ", ".join(food_behaviors))

    # 음식 유형 (B0023)
    food_type = _decode(row, "ps_B0023", codebook)
    if food_type:
        parts.append(f"음식 유형: {food_type}")

    if not parts:
        return None

    return {"category": "food_lifestyle", "text": ". ".join(parts)}


def _build_transportation(row: dict, codebook: dict) -> dict | None:
    """교통 이용 패턴"""
    parts = []

    # 통근 여부
    commute = _safe_val(row, "ps_C0001")
    if commute is not None and _is_one(commute):
        commute_time = _decode(row, "ps_C0002", codebook)
        if commute_time:
            parts.append(f"통근: 편도 {commute_time}")
        else:
            parts.append("통근을 한다")

    # 운전 여부
    drive = _safe_val(row, "ps_C0012")
    if drive is not None:
        try:
            parts.append("운전을 한다" if _is_one(drive) else "운전을 하지 않는다")
        except Exception:
            pass

    # 1주일 이내 이용 교통수단
    weekly_transport = {
        "ps_C0029": "자동차",
        "ps_C0030": "오토바이/스쿠터",
        "ps_C0031": "자전거/전기자전거",
        "ps_C0032": "개인 전기 이동기기",
        "ps_C0033": "마을버스",
        "ps_C0034": "시내버스/광역버스",
        "ps_C0035": "지하철",
        "ps_C0036": "택시",
    }
    used = [label for col, label in weekly_transport.items()
            if _safe_val(row, col) is not None and _is_one(_safe_val(row, col))]
    if used:
        parts.append(f"주로 이용하는 교통수단: {', '.join(used)}")

    # 1년 이내 장거리 교통
    long_distance = {
        "ps_C0013": "렌터카",
        "ps_C0014": "철도",
        "ps_C0015": "여객선",
        "ps_C0016": "국내선 항공",
        "ps_C0017": "미주 항공",
        "ps_C0018": "유럽 항공",
        "ps_C0019": "아시아 항공",
        "ps_C0020": "기타 해외 항공",
    }
    used_long = [label for col, label in long_distance.items()
                 if _safe_val(row, col) is not None and _is_one(_safe_val(row, col))]
    if used_long:
        parts.append(f"1년 내 장거리 이동: {', '.join(used_long)}")

    if not parts:
        return None

    return {"category": "transportation", "text": ". ".join(parts)}


def _build_health(row: dict, codebook: dict) -> dict | None:
    """건강 관리 패턴"""
    parts = []

    # 흡연
    smoke = _safe_val(row, "ps_D0035")
    if smoke is not None:
        parts.append("흡연자" if _is_one(smoke) else "비흡연자")

    # 건강기능식품
    supplements_cols = {
        "ps_D0015": "글루코사민", "ps_D0016": "단백질/프로틴", "ps_D0017": "비타민",
        "ps_D0018": "오메가3", "ps_D0019": "유산균", "ps_D0020": "체지방/체중감소제",
        "ps_D0021": "칼슘/철분/엽산", "ps_D0022": "콜라겐/히알루론산",
        "ps_D0024": "프로폴리스", "ps_D0025": "홍삼/인삼", "ps_D0026": "루테인",
        "ps_D0062": "밀크시슬",
    }
    taken = [label for col, label in supplements_cols.items()
             if _safe_val(row, col) is not None and _is_one(_safe_val(row, col))]
    if taken:
        parts.append(f"복용 중인 건강기능식품: {', '.join(taken)}")

    # 건강관리 활동
    health_activities = {
        "ps_D0063": "규칙적인 운동", "ps_D0064": "마사지",
        "ps_D0065": "소식/단식", "ps_D0066": "식단관리", "ps_D0067": "건강기능식품 섭취",
    }
    activities = [label for col, label in health_activities.items()
                  if _safe_val(row, col) is not None and _is_one(_safe_val(row, col))]
    if activities:
        parts.append(f"건강관리 활동: {', '.join(activities)}")

    # 건강 관심 영역 (D0042-D0061)
    health_concerns_cols = {
        "ps_D0042": "뇌건강", "ps_D0043": "정신건강", "ps_D0044": "모발건강",
        "ps_D0045": "눈건강", "ps_D0046": "치아건강", "ps_D0051": "피부질환",
        "ps_D0052": "피부미용", "ps_D0053": "비만/과체중", "ps_D0054": "뼈건강",
        "ps_D0055": "근육건강", "ps_D0056": "호흡기질환", "ps_D0057": "혈관계질환",
        "ps_D0058": "당뇨", "ps_D0059": "장건강", "ps_D0060": "위건강",
    }
    concerns = [label for col, label in health_concerns_cols.items()
                if _safe_val(row, col) is not None and _is_one(_safe_val(row, col))]
    if concerns:
        parts.append(f"건강 관심 영역: {', '.join(concerns)}")

    if not parts:
        return None

    return {"category": "health", "text": ". ".join(parts)}


def _build_shopping_preferences(row: dict, codebook: dict) -> dict | None:
    """쇼핑 채널 이용 빈도"""
    channel_cols = {
        "ps_E0009": "백화점",
        "ps_E0010": "대형마트/창고형할인점",
        "ps_E0011": "슈퍼마켓",
        "ps_E0012": "편의점",
        "ps_E0013": "재래시장",
        "ps_E0014": "온라인쇼핑",
        "ps_E0015": "복합쇼핑센터",
    }
    # 값: 1=주1회이상, 2=월2~3회, 3=월1회, 4=분기1~2회, 5=반기1~2회, 6=연1회이하
    frequent = []  # 1~3 (월 1회 이상)
    for col, label in channel_cols.items():
        decoded = _decode(row, col, codebook)
        if decoded:
            raw = _safe_val(row, col)
            try:
                if int(float(raw)) <= 3:
                    frequent.append(label)
            except (ValueError, TypeError):
                pass

    if not frequent:
        return None

    text = f"자주 이용하는 쇼핑 채널 (월 1회 이상): {', '.join(frequent)}"
    return {"category": "shopping_preferences", "text": text}


def _build_recent_purchases(row: dict, codebook: dict) -> dict | None:
    """최근 3개월 구매 카테고리"""
    purchase_cols = {
        "ps_E0001": "의류",
        "ps_E0002": "신발",
        "ps_E0003": "패션잡화",
        "ps_E0004": "미용/화장품",
        "ps_E0005": "인테리어/홈데코",
        "ps_E0006": "레저/취미/스포츠용품",
        "ps_E0007": "출산/유아/아동",
        "ps_E0008": "반려동물",
    }
    bought = [label for col, label in purchase_cols.items()
              if _safe_val(row, col) is not None and _is_one(_safe_val(row, col))]

    if not bought:
        return None

    text = f"최근 3개월 내 구매한 품목: {', '.join(bought)}"
    return {"category": "recent_purchases", "text": text}


def _build_shopping_channel(row: dict, codebook: dict) -> dict | None:
    """소비 스타일 및 쇼핑 유형"""
    parts = []

    fashion = _decode(row, "ps_E0040", codebook)
    if fashion:
        parts.append(f"패션 스타일: {fashion}")

    interior = _decode(row, "ps_E0041", codebook)
    if interior:
        parts.append(f"인테리어 스타일: {interior}")

    # 반려동물 보유 여부
    pets = {
        "ps_E0042": "개", "ps_E0043": "고양이", "ps_E0044": "물고기",
        "ps_E0045": "새", "ps_E0046": "파충류/양서류",
    }
    has_pets = [label for col, label in pets.items()
                if _safe_val(row, col) is not None and _is_one(_safe_val(row, col))]
    if has_pets:
        parts.append(f"반려동물: {', '.join(has_pets)}")
    else:
        # E0042~E0047이 모두 0이면 반려동물 없음
        any_pet_col = [c for c in pets if _safe_val(row, c) is not None]
        if any_pet_col:
            parts.append("반려동물: 없음")

    if not parts:
        return None

    return {"category": "shopping_channel", "text": ". ".join(parts)}


def _build_leisure(row: dict, codebook: dict) -> dict | None:
    """여가 활동"""
    parts = []

    # 여가 장소 방문
    venue_cols = {
        "ps_F0029": "카지노",
        "ps_F0030": "경마/경륜장",
        "ps_F0031": "놀이동산/테마파크",
        "ps_F0032": "워터파크",
        "ps_F0033": "동물원/식물원/수목원",
        "ps_F0034": "박물관/전시관/미술관",
        "ps_F0035": "아쿠아리움",
        "ps_F0036": "지역축제",
        "ps_F0037": "템플스테이",
        "ps_F0038": "피부관리실/마사지샵",
        "ps_F0040": "네일샵",
    }
    visited = [label for col, label in venue_cols.items()
               if _safe_val(row, col) is not None and _is_one(_safe_val(row, col))]
    if visited:
        parts.append(f"1년 내 방문한 여가 장소: {', '.join(visited)}")

    # 여가 활동 (1년)
    activity_cols = {
        "ps_F0047": "강좌/학원 수강", "ps_F0048": "골프", "ps_F0049": "공연 관람",
        "ps_F0050": "구기 스포츠", "ps_F0051": "국내여행", "ps_F0052": "영화 관람",
        "ps_F0053": "낚시", "ps_F0054": "등산", "ps_F0055": "미술/공예",
        "ps_F0056": "봉사활동", "ps_F0057": "사진/영상촬영", "ps_F0058": "수영/다이빙",
        "ps_F0059": "스크린스포츠", "ps_F0060": "스포츠 관람", "ps_F0061": "악기연주/밴드",
        "ps_F0062": "요리/제빵", "ps_F0063": "원예/식물", "ps_F0064": "웹툰/웹소설/이북",
        "ps_F0065": "유명맛집/카페 탐방", "ps_F0066": "종교활동", "ps_F0067": "독서",
        "ps_F0068": "캠핑/글램핑", "ps_F0069": "콘솔게임", "ps_F0070": "해외여행",
        "ps_F0071": "헬스/요가/필라테스",
    }
    activities = [label for col, label in activity_cols.items()
                  if _safe_val(row, col) is not None and _is_one(_safe_val(row, col))]
    if activities:
        parts.append(f"1년 내 여가 활동: {', '.join(activities)}")

    if not parts:
        return None

    return {"category": "leisure", "text": ". ".join(parts)}


def _build_media(row: dict, codebook: dict) -> dict | None:
    """미디어 소비 패턴"""
    parts = []

    # 방송 서비스
    broadcast_cols = {
        "ps_G0053": "공중파/케이블TV 실시간 방송",
        "ps_G0054": "TV VOD",
        "ps_G0055": "OTT(넷플릭스·웨이브·티빙 등)",
        "ps_G0056": "라디오 방송",
    }
    broadcast = [label for col, label in broadcast_cols.items()
                 if _safe_val(row, col) is not None and _is_one(_safe_val(row, col))]
    if broadcast:
        parts.append(f"이용 중인 방송 서비스: {', '.join(broadcast)}")

    # 인터넷 서비스
    internet_cols = {
        "ps_G0010": "OTT 서비스",
        "ps_G0011": "SNS",
        "ps_G0012": "블로그/카페",
        "ps_G0013": "포털 검색",
        "ps_G0014": "모바일 메신저",
        "ps_G0015": "음악 듣기",
        "ps_G0016": "금융 서비스",
    }
    internet = [label for col, label in internet_cols.items()
                if _safe_val(row, col) is not None and _is_one(_safe_val(row, col))]
    if internet:
        parts.append(f"이용 중인 인터넷 서비스: {', '.join(internet)}")

    # SNS 참여 방식
    sns_style = _decode(row, "ps_G0051", codebook)
    if sns_style:
        parts.append(f"SNS 이용 방식: {sns_style}")

    # 관심 동영상 콘텐츠 유형
    content_cols = {
        "ps_G0029": "드라마/영화", "ps_G0030": "음악/댄스",
        "ps_G0031": "푸드/먹방/레시피", "ps_G0032": "뉴스/시사/정치",
        "ps_G0033": "게임", "ps_G0034": "스포츠",
        "ps_G0035": "예능/코미디", "ps_G0036": "연예계 소식",
        "ps_G0037": "여행", "ps_G0038": "뷰티/패션",
        "ps_G0039": "애완동물/동물", "ps_G0040": "운동/헬스",
        "ps_G0041": "학습/강의", "ps_G0042": "일상/Vlog",
        "ps_G0044": "경제/재테크", "ps_G0045": "인테리어",
        "ps_G0046": "자동차/교통수단",
    }
    contents = [label for col, label in content_cols.items()
                if _safe_val(row, col) is not None and _is_one(_safe_val(row, col))]
    if contents:
        parts.append(f"즐겨보는 동영상 콘텐츠: {', '.join(contents)}")

    if not parts:
        return None

    return {"category": "media", "text": ". ".join(parts)}


def _build_finance(row: dict, codebook: dict) -> dict | None:
    """금융 상품 및 투자 성향"""
    parts = []

    product_cols = {
        "ps_H0005": "주식 직접투자",
        "ps_H0006": "주식 간접투자(펀드/ETF)",
        "ps_H0007": "채권",
        "ps_H0008": "외화",
        "ps_H0009": "가상화폐",
        "ps_H0010": "부동산",
        "ps_H0014": "금",
    }
    products = [label for col, label in product_cols.items()
                if _safe_val(row, col) is not None and _is_one(_safe_val(row, col))]
    if products:
        parts.append(f"투자 중인 금융 상품: {', '.join(products)}")
    else:
        # 모두 0이면 "투자 없음"
        any_col = [c for c in product_cols if _safe_val(row, c) is not None]
        if any_col:
            parts.append("별도 투자 상품 없음")

    invest_style = _decode(row, "ps_H0015", codebook)
    if invest_style:
        parts.append(f"투자 성향: {invest_style}")

    if not parts:
        return None

    return {"category": "finance", "text": ". ".join(parts)}


def _build_pay_pattern(row: dict, codebook: dict) -> dict | None:
    """결제 행동 패턴 (정량 데이터)"""
    parts = []

    monthly = _safe_val(row, "pay_monthly_avg_spend")
    if monthly is not None:
        try:
            parts.append(f"월평균 결제금액: 약 {int(float(monthly)):,}원")
        except (ValueError, TypeError):
            pass

    for col, name in [
        ("pay_online_ratio", "온라인 결제 비율"),
        ("pay_conv_ratio", "편의점 결제 비율"),
        ("pay_dining_ratio", "외식 결제 비율"),
        ("pay_alcohol_ratio", "주류 결제 비율"),
        ("pay_late_night_ratio", "심야 결제 비율"),
        ("pay_weekend_ratio", "주말 결제 비율"),
    ]:
        v = _safe_val(row, col)
        if v is not None:
            fmt = _fmt_ratio(v, name)
            if fmt:
                parts.append(fmt)

    if not parts:
        return None

    return {"category": "pay_pattern", "text": ". ".join(parts)}


def _build_pay_favorites(row: dict, codebook: dict) -> dict | None:
    """자주 결제하는 카테고리 및 단골 매장"""
    parts = []

    top_cats = _parse_json_col(_safe_val(row, "pay_top_categories"))
    if top_cats:
        cat_str = ", ".join(f"{name}({cnt}건)" for name, cnt in top_cats[:5])
        parts.append(f"자주 결제하는 카테고리: {cat_str}")

    top_stores = _parse_json_col(_safe_val(row, "pay_top_stores"))
    if top_stores:
        store_str = ", ".join(name for name, _ in top_stores[:5])
        parts.append(f"단골 매장: {store_str}")

    if not parts:
        return None

    return {"category": "pay_favorites", "text": ". ".join(parts)}


def _build_lbs_pattern(row: dict, codebook: dict) -> dict | None:
    """위치 이동 및 방문 패턴"""
    parts = []

    spatial = _safe_val(row, "lbs_spatial_range_km")
    if spatial is not None:
        try:
            parts.append(f"활동 반경: 약 {float(spatial):.0f}km")
        except (ValueError, TypeError):
            pass

    unique = _safe_val(row, "lbs_unique_places")
    if unique is not None:
        try:
            parts.append(f"방문 고유 장소 수: {int(float(unique))}곳")
        except (ValueError, TypeError):
            pass

    for col, name in [
        ("lbs_restaurant", "식당/음식점"),
        ("lbs_cafe", "카페"),
        ("lbs_conv_store", "편의점"),
        ("lbs_gym_fitness", "헬스장/피트니스"),
        ("lbs_mart", "마트"),
        ("lbs_entertainment", "오락시설"),
        ("lbs_bar_club", "술집/바"),
        ("lbs_pc_bang", "PC방"),
    ]:
        v = _safe_val(row, col)
        if v is not None:
            try:
                cnt = int(float(v))
                if cnt > 0:
                    parts.append(f"{name} 방문 {cnt}회")
            except (ValueError, TypeError):
                pass

    top_cats = _parse_json_col(_safe_val(row, "lbs_top_categories"))
    if top_cats:
        cat_str = ", ".join(name for name, _ in top_cats[:5])
        parts.append(f"주요 방문 장소 유형: {cat_str}")

    if not parts:
        return None

    return {"category": "lbs_pattern", "text": ". ".join(parts)}


def _build_app_pattern(row: dict, codebook: dict) -> dict | None:
    """앱 사용 패턴"""
    parts = []

    total_hr = _safe_val(row, "app_total_duration_hr")
    if total_hr is not None:
        try:
            parts.append(f"총 앱 사용시간: 약 {float(total_hr):,.0f}시간")
        except (ValueError, TypeError):
            pass

    for col, name in [
        ("app_social_hr", "소셜/커뮤니케이션"),
        ("app_gaming_hr", "게임"),
        ("app_shopping_hr", "쇼핑"),
        ("app_entertainment_hr", "엔터테인먼트"),
    ]:
        v = _safe_val(row, col)
        if v is not None:
            try:
                h = float(v)
                if h > 0:
                    parts.append(f"{name} 앱 {h:,.0f}시간")
            except (ValueError, TypeError):
                pass

    top_cats = _parse_json_col(_safe_val(row, "app_top_categories"))
    if top_cats:
        # 값이 나노초(ns) 단위일 경우 시간 변환
        try:
            cat_str = ", ".join(name for name, _ in top_cats[:5])
            parts.append(f"주요 앱 카테고리: {cat_str}")
        except Exception:
            pass

    top_apps = _parse_json_col(_safe_val(row, "app_top_apps"))
    if top_apps:
        try:
            app_str = ", ".join(name for name, _ in top_apps[:5])
            parts.append(f"자주 쓰는 앱: {app_str}")
        except Exception:
            pass

    if not parts:
        return None

    return {"category": "app_pattern", "text": ". ".join(parts)}


# ---------------------------------------------------------------------------
# 전체 조합
# ---------------------------------------------------------------------------

_BUILDERS = [
    _build_appliances,
    _build_food_lifestyle,
    _build_transportation,
    _build_health,
    _build_shopping_preferences,
    _build_recent_purchases,
    _build_shopping_channel,
    _build_leisure,
    _build_media,
    _build_finance,
    _build_pay_pattern,
    _build_pay_favorites,
    _build_lbs_pattern,
    _build_app_pattern,
]


def build_all_memory_texts(row: dict, codebook: dict) -> list[dict]:
    """
    row와 codebook으로 최대 14개 카테고리 메모리 텍스트 생성.
    각 항목: {"category": str, "text": str}
    한 빌더가 실패해도 나머지는 계속 실행됨.
    """
    results = []
    for builder in _BUILDERS:
        try:
            result = builder(row, codebook)
            if result is not None:
                results.append(result)
        except Exception:
            pass
    return results


# ---------------------------------------------------------------------------
# LLM Importance 부여
# ---------------------------------------------------------------------------

IMPORTANCE_PROMPT_TEMPLATE = """\
On the scale of 1 to 10, where 1 is purely mundane \
(e.g., brushing teeth, making bed) and 10 is extremely poignant \
(e.g., a break up, college acceptance), rate the likely poignancy \
of the following pieces of memory.
Rate the response on a scale from 1 to 10. Respond only in JSON.

Memory:
{memory_items}

JSON response format:
{{"Item 1": <fill in>, "Item 2": <fill in>, ...}}
"""


def attach_importance(memories: list[dict], no_importance: bool = False) -> list[dict]:
    """
    memories 리스트에 importance(0~100) 부여.
    no_importance=True이면 모두 50 반환.
    API 실패 시 fallback: 모두 25.
    """
    if not memories:
        return memories

    if no_importance:
        return [{**m, "importance": NO_IMPORTANCE_VALUE} for m in memories]

    memory_items = "\n".join(
        f"Item {i + 1}: {m['text']}" for i, m in enumerate(memories)
    )
    prompt = IMPORTANCE_PROMPT_TEMPLATE.format(memory_items=memory_items)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.0,
        )
        content = response.choices[0].message.content.strip()

        # JSON 파싱
        # 코드블록 제거
        if content.startswith("```"):
            content = "\n".join(content.split("\n")[1:-1])

        scores: dict = json.loads(content)

        result = []
        for i, m in enumerate(memories):
            key = f"Item {i + 1}"
            score_raw = scores.get(key, DEFAULT_IMPORTANCE)
            try:
                score_1_10 = float(score_raw)
                importance = max(0, min(100, int(round(score_1_10 * 10))))
            except (ValueError, TypeError):
                importance = DEFAULT_IMPORTANCE
            result.append({**m, "importance": importance})
        return result

    except Exception as e:
        print(f"[경고] Importance 점수 부여 실패 ({e}). 모두 {DEFAULT_IMPORTANCE}점으로 설정.")
        return [{**m, "importance": DEFAULT_IMPORTANCE} for m in memories]
