"""Mock Twin-2K-500 응답 생성기 — 실데이터 도착 전 흐름 검증용.

LENS_DEFINITIONS 의 234문항 키 구조를 따르되, 6 archetype × N명 배분으로
다양성을 보장한다. seed 고정 시 결정적이라 회귀 테스트에도 사용 가능.

사용법:
  python -m scripts.generate_mock_twin --count 30 --seed 42 --out tests/_fixtures/mock_twin_30.json

archetype:
  - frugal_planner       : 위험·손실 회피 高, 절약·성실성 高, 미니멀리즘 中
  - trend_adopter        : 위험 회피 低, 극대화 高, 독특성·자기감시 高
  - social_collectivist  : 공감·집단주의 高, 친환경·관계 中, agency 中
  - minimalist_idealist  : 미니멀·친환경 高, 인지욕구 高, 가치소비 高
  - rational_analytic    : 인지욕구·CRT·금융 高, 공감 中, 충동성 低
  - value_traditional    : 보수·집단주의 高, 인지욕구 中, 친환경 低
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ARCHETYPES = [
    "frugal_planner",
    "trend_adopter",
    "social_collectivist",
    "minimalist_idealist",
    "rational_analytic",
    "value_traditional",
]


# ── 인구통계 풀 ───────────────────────────────────────────────────────────

REGIONS = ["서울특별시", "경기도", "인천광역시", "부산광역시", "대전광역시", "대구광역시", "광주광역시", "강원특별자치도"]
GENDERS = ["여성", "남성"]
AGE_RANGES = ["20-29", "30-39", "40-49", "50-59", "60-69"]
EDUCATION = ["고등학교 졸업", "전문대학 졸업", "대학교 졸업", "대학원 석사", "대학원 박사"]
EMPLOYMENT = ["정규직 임금근로자", "비정규직 임금근로자", "자영업자", "프리랜서", "주부", "학생", "구직 중"]
INCOMES = ["100~200만원", "200~300만원", "300~500만원", "500~700만원", "700~1000만원", "1000만원 이상"]
MARITAL = ["미혼", "기혼(법적)", "이혼", "사별"]
HOUSEHOLD_SIZES = ["1명", "2명", "3명", "4명", "5명 이상"]
RELIGION = ["무교(없음)", "개신교", "천주교", "불교", "기타"]
POLITICAL_PARTY = ["무당층(지지 정당 없음)", "더불어민주당", "국민의힘", "정의당", "기타"]
NATIONALITY = ["한국인"]
VISA = ["해당없음(한국인)"]


# ── 정성 응답 텍스트 풀 ───────────────────────────────────────────────────

QUALITATIVE_BANK: dict[str, dict[str, list[str]]] = {
    "frugal_planner": {
        "aspire": [
            "저축으로 안정된 은퇴를 준비하고, 가족이 갑작스러운 일에도 흔들리지 않도록 든든한 버팀목이 되고 싶습니다. 불필요한 소비를 줄이고 핵심에만 지출하는 삶이 이상적입니다.",
            "비상금을 늘리고, 빚 없이 사는 것을 가장 원합니다. 자녀 교육비를 충분히 준비해서 본인이 원하는 길을 가게 하는 것이 목표입니다.",
        ],
        "ought": [
            "버는 만큼 분수에 맞게 써야 한다고 생각합니다. 가족의 미래를 위해 현재의 욕구를 절제하는 것은 당연한 책임입니다.",
            "충동구매를 피하고 가계부를 꾸준히 쓰는 것이 옳다고 봅니다. 사회 구성원으로서 안정적으로 살아가는 것이 의무라고 느낍니다.",
        ],
        "actual": [
            "저는 가격을 비교한 뒤에 사고, 할인 시즌을 기다려서 구매하는 편입니다. 새것보다 오래 쓸 수 있는 물건을 고릅니다.",
            "예산을 정해두고 그 안에서만 지출합니다. 외식보다 직접 요리를 선호하고, 정리정돈을 자주 합니다.",
        ],
        # ── V1 hold-out (페르소나 프롬프트에 미포함) ─────────────────────────
        "recent_purchase": [
            "가장 최근에 큰 지출은 김치냉장고를 산 것입니다. 1년 넘게 가격 비교를 했고, 할인 행사 때 영수증을 챙겨서 카드 할부 무이자로 결제했습니다. 새 모델보다 직전 연식이 30만 원 싸길래 그쪽을 골랐습니다.",
            "최근 큰 소비는 자녀 교복비였습니다. 학교 지정 매장이라 선택지가 좁았지만, 형제 물려주기를 전제로 한 치수 위를 골라 길게 입힐 수 있게 했습니다. 외투는 인터넷 최저가 매장을 따로 찾아 따로 샀습니다.",
        ],
        "info_source": [
            "물건을 살 때 가장 신뢰하는 것은 검색해서 모은 실제 사용자 후기들입니다. 너무 좋다는 후기보다 단점을 적은 후기들을 더 꼼꼼히 봅니다. 광고성 블로그는 거르고 커뮤니티의 1년 사용기를 우선합니다.",
            "할인 정보는 가계부 어플의 알림과 마트 전단지를 봅니다. 새 카드도 연회비 무료에 적립이 큰지 비교 사이트에서 확인하고 만듭니다. 친구가 추천해도 일단 본인이 직접 따져 봅니다.",
        ],
        "lifestyle": [
            "본인을 한 단어로 표현한다면 '계획형'입니다. 매월 첫 주에 가계부를 결산하고 다음 달 예산을 잡습니다. 즉흥적인 지출은 거의 없고, 미래 비용이 보이지 않는 결정을 가장 싫어합니다.",
            "'준비형' 소비자입니다. 1년 안에 들어올 큰 지출(보험·교육·차량 수리)을 미리 적어 두고, 매달 그 항목으로 자동이체를 빼둡니다. 비상금이 두 달 치 생활비 밑으로 내려가면 외식부터 줄입니다.",
        ],
    },
    "trend_adopter": {
        "aspire": [
            "새로운 경험과 트렌드를 빠르게 누리고 싶습니다. 남들이 모르는 것을 먼저 발견하는 데서 즐거움을 느끼고, 그것을 주변과 공유하고 싶습니다.",
            "취미와 일이 균형 잡힌 라이프스타일을 추구합니다. 늘 무언가를 시도하고 도전하면서 정체되지 않는 삶을 원합니다.",
        ],
        "ought": [
            "시대 변화를 따라가지 못하면 도태된다고 생각합니다. 새 기술과 문화를 익히는 것은 사회인의 책임입니다.",
            "스스로의 욕망을 너무 억누르지 않고, 즐기는 만큼 일도 열심히 해야 한다고 봅니다.",
        ],
        "actual": [
            "SNS에서 화제가 된 상품은 일단 사보는 편입니다. 친구들이 좋다고 한 곳은 가능한 한 빨리 방문합니다.",
            "신상품·신규 서비스의 얼리어답터입니다. 약간 비싸도 새로운 경험이라면 지갑을 열어요.",
        ],
        "recent_purchase": [
            "최근에 새로 나온 무선 이어폰의 사전예약 1차 물량을 잡아 결제했습니다. 기존 거 잘 쓰고 있었지만 신기능 데모 영상을 보고 바로 결심했어요. 받자마자 SNS에 개봉 영상을 올렸습니다.",
            "한정판 운동화 응모에 당첨돼서 시세보다 두 배 가까운 가격에 거래로 추가 결제했습니다. 매장 픽업 후 친구들과 인증샷을 찍으러 카페를 갔어요.",
        ],
        "info_source": [
            "트렌드는 인스타그램과 유튜브 쇼츠에서 가장 먼저 캐치합니다. 화제가 된 가게는 위치 저장해 두고 주말에 바로 갑니다. 따라가는 사람보다 먼저 가서 후기를 남기는 쪽을 선호합니다.",
            "얼리어답터 커뮤니티의 사전 후기와 해외 IT 채널을 봅니다. 한국 정식 출시 전에 직구로 먼저 받아보는 경우도 많습니다.",
        ],
        "lifestyle": [
            "'얼리어답터'가 가장 잘 맞는 한 단어입니다. 새 기능·새 서비스를 가장 먼저 써보고 그 경험을 남에게 추천하는 데서 만족감을 얻습니다. 검증된 것만 쓰는 삶은 답답해요.",
            "'경험 수집가'입니다. 똑같은 카페보다 새로 생긴 곳, 안 가본 도시·전시를 늘 우선합니다. 한 분야에 오래 머무는 것보다 다양한 자극이 더 가치 있다고 봅니다.",
        ],
    },
    "social_collectivist": {
        "aspire": [
            "가족·친구·동료와 따뜻한 관계를 유지하면서, 어려운 사람들에게 작은 도움이라도 주고 싶습니다. 공동체에 보탬이 되는 삶이 이상입니다.",
            "팀이 잘 되도록 돕고, 사람들이 저를 신뢰할 수 있는 사람으로 기억해 주길 바랍니다.",
        ],
        "ought": [
            "주변 사람들의 부탁은 가급적 들어주려고 합니다. 함께 사는 사회니까 서로 양보하고 배려해야 한다고 생각합니다.",
            "가족의 행사와 친구의 경조사는 빠지지 않습니다. 인간관계는 신뢰에서 시작된다고 믿습니다.",
        ],
        "actual": [
            "주말마다 가족과 시간을 보내고, 친구 모임에 자주 나갑니다. 동료가 어려울 때 먼저 손을 내미는 편입니다.",
            "그룹 채팅에 답이 빠른 편이고, 모임을 주도하는 일이 많습니다. 혼자보다 함께 하는 활동이 즐겁습니다.",
        ],
        "recent_purchase": [
            "최근에 친구 부부의 집들이 선물로 식기 세트를 샀습니다. 두 사람 취향을 모두 살피느라 몇 시간 고민했고, 함께 자주 모이는 친구 두 명과 비용을 모아 좋은 걸로 골랐습니다.",
            "동호회 모임 회식 비용을 모아 단체로 결제했습니다. 본인이 총무라 미리 사람 수를 받아 코스 가격을 조율하고, 못 오는 사람 몫까지 조금씩 깎아 정산했습니다.",
        ],
        "info_source": [
            "결정 전에는 신뢰하는 친구·선배에게 묻습니다. 같은 경험을 한 사람이 있다면 그 말이 어떤 후기보다 정확하다고 봐요. 가족이 써보고 좋다 한 브랜드는 거의 따라갑니다.",
            "커뮤니티의 단톡방, 동료가 추천한 블로그가 1순위 정보원입니다. 모르는 사람의 별점보다 아는 사람의 진짜 후기를 더 신뢰합니다.",
        ],
        "lifestyle": [
            "한 단어로 '연결형'입니다. 좋은 식당·여행지·물건을 찾으면 가족과 친구에게 먼저 공유합니다. 혼자만 좋은 것을 아는 건 별로 의미가 없다고 느껴요.",
            "'동행형'입니다. 큰 결정도 가족과 의논해서 함께 가는 길을 고릅니다. 혼자 잘되는 것보다 같이 잘되는 게 더 안정감 있어요.",
        ],
    },
    "minimalist_idealist": {
        "aspire": [
            "꼭 필요한 것만 가지고 단순하게 살고 싶습니다. 환경에 부담을 적게 주고, 소유보다 경험에 가치를 두는 삶이 이상입니다.",
            "물건의 양보다 시간의 질을 우선하는 삶을 원합니다. 작은 공간이라도 잘 정돈된 곳에서 의미 있는 일을 하고 싶습니다.",
        ],
        "ought": [
            "기후 위기에 작게라도 책임을 져야 한다고 생각합니다. 일회용품을 줄이고, 가능한 한 재사용하는 것이 옳습니다.",
            "필요 없는 물건을 사지 않는 것이 가장 친환경적이라고 봅니다. 적게 가지고 깊게 쓰는 것이 윤리적 소비라고 생각합니다.",
        ],
        "actual": [
            "1년 이상 쓰지 않은 물건은 정리합니다. 새 옷보다 기존 옷을 오래 입고, 텀블러·장바구니를 늘 챙깁니다.",
            "비건 식단을 자주 시도하고, 친환경 인증 제품을 선호합니다. 비싸도 의미 있는 소비라면 합니다.",
        ],
        "recent_purchase": [
            "최근에 산 큰 물건은 무세제 세탁이 가능한 친환경 세탁기입니다. 기존 게 고장 났을 때 그냥 바꾸지 않고, 한 달간 알아본 뒤 RE100 공급망과 수리 가능성이 좋은 브랜드로 결정했습니다.",
            "원목 책상을 중고로 들였습니다. 새 가구를 사는 대신 멀쩡한 걸 받아 직접 사포질하고 마감재만 친환경 오일로 발랐어요. 새 가구를 만드는 데 들어가는 자원이 줄어든 게 가장 만족스럽습니다.",
        ],
        "info_source": [
            "구매 전에 제조사의 ESG 리포트·인증 마크를 확인합니다. 환경 단체·소비자 리포트의 비교 자료가 가장 신뢰됩니다. 가격은 그다음입니다.",
            "지속가능 소비 뉴스레터와 공익 매체의 리뷰를 봅니다. 화려한 광고보다 단점을 솔직하게 쓰는 매체가 더 믿을 만해요.",
        ],
        "lifestyle": [
            "'미니멀리스트'입니다. 1년 안 쓴 물건은 정기적으로 정리하고, 같은 용도의 물건은 한 개만 둡니다. 비우는 데서 오는 자유가 크다고 느껴요.",
            "'가치소비자'입니다. 싸다고 사지 않고, 비싸도 만든 방식이 윤리적이면 삽니다. 한 번 사면 오래 쓰는 게 핵심입니다.",
        ],
    },
    "rational_analytic": {
        "aspire": [
            "충분한 정보를 바탕으로 합리적인 결정을 내리고 싶습니다. 감정에 휘둘리지 않고 데이터와 근거로 판단하는 사람이 되고 싶습니다.",
            "복잡한 문제를 분석하고 해결하는 일을 즐깁니다. 자기 전문 분야에서 깊이 있는 통찰을 갖춘 사람이 이상입니다.",
        ],
        "ought": [
            "근거 없이 주장하지 말아야 한다고 생각합니다. 결정 전에 비용·편익을 계산하는 것이 합리적 시민의 자세입니다.",
            "감정적 충동에 의한 의사결정은 피해야 합니다. 시간이 걸리더라도 정확한 판단이 결국 이득입니다.",
        ],
        "actual": [
            "큰 지출 전에는 여러 후기와 데이터를 비교합니다. 가계부·투자내역을 엑셀로 관리합니다.",
            "회의에서 데이터를 들고 가는 편입니다. 직관보다 모델·통계를 더 신뢰합니다.",
        ],
        "recent_purchase": [
            "최근에 노트북을 바꿨습니다. 사용 시간 대비 단가를 계산해서 5년 ROI 가 나오는 모델을 골랐고, 메모리·SSD 만 따로 업그레이드해 가격을 20% 줄였습니다. 비교표 엑셀까지 만들어 결제 전에 두 번 검토했어요.",
            "투자 계좌를 IRP 로 옮긴 게 가장 큰 결정이었습니다. 수익률·세제 혜택·환매 조건을 표로 비교한 뒤, 절세 효과가 가장 큰 옵션으로 6개 ETF 비중을 정했습니다.",
        ],
        "info_source": [
            "1차 자료를 우선합니다. 제조사 사양표, 학술 논문, 공식 통계가 가장 신뢰할 만합니다. 인플루언서의 추천은 거의 보지 않아요.",
            "데이터·차트가 풍부한 리뷰 매체를 신뢰합니다. 같은 제품을 측정 방식이 다른 두 사이트에서 교차 검증한 다음에야 결제를 합니다.",
        ],
        "lifestyle": [
            "'분석가'입니다. 모든 결정 전에 표를 만들어 항목별로 비용·편익·리스크를 계산합니다. 직관에 따른 결정이 가장 후회가 크다고 느껴요.",
            "'계산형'입니다. 시간당 가치, 자원 단가를 머릿속에 두고 결정합니다. 정량화할 수 있는 것은 반드시 정량화하고 시작합니다.",
        ],
    },
    "value_traditional": {
        "aspire": [
            "가족과 전통을 중요하게 여기며, 안정적이고 예측 가능한 삶을 원합니다. 부모님께 효도하고 자녀를 잘 키우는 것이 가장 중요한 목표입니다.",
            "검증된 방식으로 살아가며, 큰 모험 없이도 충분히 의미 있는 인생이라 믿습니다.",
        ],
        "ought": [
            "부모를 공경하고 가정을 지키는 것이 사회의 기본이라고 생각합니다. 약속·의리·체면을 지키는 것은 어른의 도리입니다.",
            "시류에 휩쓸리지 않고 우리 사회의 미풍양속을 지키는 것이 옳다고 봅니다.",
        ],
        "actual": [
            "명절·제사·가족 모임은 빠지지 않습니다. 새로운 것보다는 익숙한 브랜드와 매장을 신뢰합니다.",
            "친환경·트렌드보다는 검증된 품질을 우선합니다. 모험적인 소비는 거의 하지 않습니다.",
        ],
        "recent_purchase": [
            "부모님 보일러를 새로 들였습니다. 30년 된 동네 보일러 가게에서 같은 브랜드로 교체했고, 시공비도 거기서 그대로 받았습니다. 인터넷 최저가는 보지 않았어요.",
            "큰아이 백일 잔치 한복을 맞췄습니다. 주변에 추천받은 오랜 한복집에서 직접 가서 천을 골랐고, 어머니께서 함께 가셔서 디자인 의견을 주셨습니다.",
        ],
        "info_source": [
            "오래 거래한 동네 가게 사장님과 친지의 말이 가장 믿을 만합니다. 한 번 거래해서 좋았던 곳은 다음에도 그곳에서 삽니다.",
            "어른들이 추천하는 브랜드, 부모님 세대부터 써온 회사 제품을 신뢰합니다. 새로 생긴 브랜드는 일단 의심부터 합니다.",
        ],
        "lifestyle": [
            "한 단어로 '안정형'입니다. 검증된 것에 머물고 작은 변화도 충분히 의미 있다고 봅니다. 굳이 모험을 들여 위험을 키울 이유가 없어요.",
            "'전통형'입니다. 명절·기념일·가족 의례를 빠지지 않고 챙기고, 그 시간을 통해 삶의 중심이 잡힌다고 느낍니다.",
        ],
    },
}


# V1 hold-out 자극의 한국어 질문 (페르소나 프롬프트에 들어가지 않음)
HOLDOUT_QUESTIONS: dict[str, str] = {
    "recent_purchase": "최근 6개월 안에 본인이 한 가장 큰 소비 한 건을 떠올려서, 무엇을 샀고 왜 그렇게 결정했는지 4~6문장으로 설명해 주세요.",
    "info_source": "물건이나 서비스를 결정할 때 가장 신뢰하는 정보 출처는 무엇인가요? 그렇게 신뢰하게 된 이유까지 4~6문장으로 답해 주세요.",
    "lifestyle": "본인의 라이프스타일을 한 단어로 표현한다면 무엇이고, 그 단어가 왜 본인을 잘 설명하는지 4~6문장으로 풀어주세요.",
}


def _pick(rng: random.Random, items: list):
    return rng.choice(items)


def _likert(rng: random.Random, mean: float, scale_max: int, sd: float = 0.9) -> int:
    """평균 mean, 범위 [1, scale_max] 의 정수 응답. mean 으로부터 정규 노이즈."""
    val = rng.gauss(mean, sd)
    return max(1, min(scale_max, round(val)))


def _binary_prob(rng: random.Random, p_true: float) -> str:
    return "TRUE" if rng.random() < p_true else "FALSE"


# ── 아키타입별 파라미터 ───────────────────────────────────────────────────

ARCHETYPE_PROFILES: dict[str, dict] = {
    "frugal_planner": {
        # MPL CE — 위험 회피 高: CE 가 EV 대비 낮음
        "l1_1_ce_factor": (0.50, 0.70),     # CE = EV * factor
        "l1_2_mpl_x": (2500, 4500),         # L1-2.Q1 (EV=6000)
        "l1_2_q4_x": (8000, 14000),         # 손실회피 mixed gain
        "l1_3_match_p": 0.85,               # 정답에 대한 일치율
        "l1_4_mean": 3.5,                   # 1~5 미니, 절약 高 → 낮은 점수
        "l2_max_mean": 2.5,                 # 극대화 낮음 — 만족형
        "l2_nfc_mean": 3.2,                 # 인지욕구 중
        "l2_nfclo_mean": 4.0,               # 종결 욕구 높음
        "l2_crt_correct_p": 0.55,
        "l3_reg_focus_mean": 6.0,           # 예방 초점 높음
        "l3_agency_mean": 5.5,
        "l3_communion_mean": 6.5,
        "l3_uniq_mean": 2.5,                # 독특성 낮음
        "l4_sm_mean": 2.5,                  # 자기 감시 낮음
        "l4_indiv_h": 3.5, "l4_indiv_v": 2.5, "l4_coll_h": 5.0, "l4_coll_v": 4.5,
        "l4_empathy_mean": 3.2,
        "l4_dictator": [1000, 2000],
        "l4_fc_p1_mean": 2.8, "l4_fc_p2_mean": 35,
        "l5_min_mean": 3.5,
        "l5_green_mean": 3.5,
        "l6_dr_q1_x": (4500, 5500), "l6_pb_q1_x": (5500, 6500),
        "l6_consc_high_p": 0.75,
        "fin_correct_p": 0.65, "num_correct_p": 0.55,
    },
    "trend_adopter": {
        "l1_1_ce_factor": (0.85, 1.05),
        "l1_2_mpl_x": (4500, 5800),
        "l1_2_q4_x": (12000, 20000),
        "l1_3_match_p": 0.40,
        "l1_4_mean": 1.8,
        "l2_max_mean": 4.3,
        "l2_nfc_mean": 3.0,
        "l2_nfclo_mean": 2.5,
        "l2_crt_correct_p": 0.35,
        "l3_reg_focus_mean": 4.5,
        "l3_agency_mean": 7.5, "l3_communion_mean": 5.5,
        "l3_uniq_mean": 4.2,
        "l4_sm_mean": 4.2,
        "l4_indiv_h": 4.5, "l4_indiv_v": 4.0, "l4_coll_h": 3.0, "l4_coll_v": 2.5,
        "l4_empathy_mean": 3.3,
        "l4_dictator": [0, 1000, 2000],
        "l4_fc_p1_mean": 3.5, "l4_fc_p2_mean": 60,
        "l5_min_mean": 2.0,
        "l5_green_mean": 3.0,
        "l6_dr_q1_x": (5400, 5950), "l6_pb_q1_x": (6800, 7800),
        "l6_consc_high_p": 0.35,
        "fin_correct_p": 0.45, "num_correct_p": 0.50,
    },
    "social_collectivist": {
        "l1_1_ce_factor": (0.60, 0.80),
        "l1_2_mpl_x": (3000, 4500),
        "l1_2_q4_x": (10000, 14000),
        "l1_3_match_p": 0.65,
        "l1_4_mean": 3.0,
        "l2_max_mean": 3.3,
        "l2_nfc_mean": 3.3,
        "l2_nfclo_mean": 3.5,
        "l2_crt_correct_p": 0.40,
        "l3_reg_focus_mean": 5.0,
        "l3_agency_mean": 5.0, "l3_communion_mean": 8.0,
        "l3_uniq_mean": 2.5,
        "l4_sm_mean": 3.5,
        "l4_indiv_h": 3.0, "l4_indiv_v": 2.5, "l4_coll_h": 6.0, "l4_coll_v": 5.5,
        "l4_empathy_mean": 4.3,
        "l4_dictator": [2000, 4000],
        "l4_fc_p1_mean": 3.0, "l4_fc_p2_mean": 50,
        "l5_min_mean": 3.0, "l5_green_mean": 4.0,
        "l6_dr_q1_x": (4800, 5500), "l6_pb_q1_x": (5800, 6800),
        "l6_consc_high_p": 0.60,
        "fin_correct_p": 0.50, "num_correct_p": 0.45,
    },
    "minimalist_idealist": {
        "l1_1_ce_factor": (0.65, 0.85),
        "l1_2_mpl_x": (3500, 5000),
        "l1_2_q4_x": (10000, 16000),
        "l1_3_match_p": 0.60,
        "l1_4_mean": 4.2,
        "l2_max_mean": 2.8,
        "l2_nfc_mean": 4.3,
        "l2_nfclo_mean": 2.8,
        "l2_crt_correct_p": 0.60,
        "l3_reg_focus_mean": 5.5,
        "l3_agency_mean": 6.0, "l3_communion_mean": 6.5,
        "l3_uniq_mean": 3.8,
        "l4_sm_mean": 3.0,
        "l4_indiv_h": 4.5, "l4_indiv_v": 3.0, "l4_coll_h": 4.5, "l4_coll_v": 3.5,
        "l4_empathy_mean": 4.0,
        "l4_dictator": [2000, 4000, 5000],
        "l4_fc_p1_mean": 3.5, "l4_fc_p2_mean": 45,
        "l5_min_mean": 4.5, "l5_green_mean": 4.5,
        "l6_dr_q1_x": (4800, 5500), "l6_pb_q1_x": (5500, 6500),
        "l6_consc_high_p": 0.65,
        "fin_correct_p": 0.60, "num_correct_p": 0.55,
    },
    "rational_analytic": {
        "l1_1_ce_factor": (0.75, 0.95),
        "l1_2_mpl_x": (4500, 5600),
        "l1_2_q4_x": (8000, 12000),
        "l1_3_match_p": 0.90,
        "l1_4_mean": 3.0,
        "l2_max_mean": 3.5,
        "l2_nfc_mean": 4.6,
        "l2_nfclo_mean": 3.0,
        "l2_crt_correct_p": 0.85,
        "l3_reg_focus_mean": 5.2,
        "l3_agency_mean": 7.0, "l3_communion_mean": 5.0,
        "l3_uniq_mean": 3.2,
        "l4_sm_mean": 3.2,
        "l4_indiv_h": 4.0, "l4_indiv_v": 3.5, "l4_coll_h": 3.0, "l4_coll_v": 3.0,
        "l4_empathy_mean": 3.0,
        "l4_dictator": [0, 1000, 2000],
        "l4_fc_p1_mean": 3.0, "l4_fc_p2_mean": 50,
        "l5_min_mean": 3.5, "l5_green_mean": 3.2,
        "l6_dr_q1_x": (5000, 5700), "l6_pb_q1_x": (5500, 6500),
        "l6_consc_high_p": 0.70,
        "fin_correct_p": 0.85, "num_correct_p": 0.85,
    },
    "value_traditional": {
        "l1_1_ce_factor": (0.55, 0.75),
        "l1_2_mpl_x": (2800, 4500),
        "l1_2_q4_x": (9000, 13000),
        "l1_3_match_p": 0.70,
        "l1_4_mean": 3.8,
        "l2_max_mean": 2.7,
        "l2_nfc_mean": 2.8,
        "l2_nfclo_mean": 4.3,
        "l2_crt_correct_p": 0.30,
        "l3_reg_focus_mean": 5.8,
        "l3_agency_mean": 5.5, "l3_communion_mean": 6.0,
        "l3_uniq_mean": 2.2,
        "l4_sm_mean": 2.8,
        "l4_indiv_h": 2.5, "l4_indiv_v": 3.0, "l4_coll_h": 5.5, "l4_coll_v": 6.0,
        "l4_empathy_mean": 3.5,
        "l4_dictator": [1000, 2000],
        "l4_fc_p1_mean": 2.5, "l4_fc_p2_mean": 30,
        "l5_min_mean": 3.2, "l5_green_mean": 2.5,
        "l6_dr_q1_x": (4500, 5500), "l6_pb_q1_x": (5500, 6800),
        "l6_consc_high_p": 0.65,
        "fin_correct_p": 0.45, "num_correct_p": 0.40,
    },
}


# ── 정답 (parser/scoring 호환용) ──────────────────────────────────────────

CRT_ANSWERS = ["수아", 0, 2, 8]
FIN_ANSWERS = ["TRUE", 3, 2, "TRUE", 2, 2, "TRUE", "영원히"]
NUM_ANSWERS = [500, 10, 20, 0.1, 100, 5, 500, 47]


def _categorical_pick(rng: random.Random, correct, prob: float, alt_pool: list):
    if rng.random() < prob:
        return correct
    return _pick(rng, alt_pool)


def generate_record(rng: random.Random, idx: int, archetype: str) -> dict:
    """단일 mock 레코드 생성."""
    P = ARCHETYPE_PROFILES[archetype]

    # ── L1-1 위험 회피 MPL CE (EV: 3000/5000/5000) ─────────────────────────
    f_lo, f_hi = P["l1_1_ce_factor"]
    l1_1 = {
        "L1-1.Q1.row_first_certain": int(3000 * rng.uniform(f_lo, f_hi)),
        "L1-1.Q2.row_first_certain": int(5000 * rng.uniform(f_lo, f_hi)),
        "L1-1.Q3.row_first_certain": int(5000 * rng.uniform(f_lo, f_hi)),
    }

    # ── L1-2 손실 회피 ────────────────────────────────────────────────────
    mpl_lo, mpl_hi = P["l1_2_mpl_x"]
    q4_lo, q4_hi = P["l1_2_q4_x"]
    l1_2 = {
        "L1-2.Q1.row_first_certain": rng.randint(mpl_lo, mpl_hi),
        "L1-2.Q2.row_first_certain": rng.randint(mpl_lo + 1500, mpl_hi + 1500),
        "L1-2.Q3.row_first_certain": rng.randint(mpl_lo + 2500, mpl_hi + 2500),
        "L1-2.Q4.row_first_positive": rng.randint(q4_lo, q4_hi),
    }

    # ── L1-3 심적 회계 (정답 A/A/B/B 패턴 일치율) ─────────────────────────
    expected = ["A", "A", "B", "B"]
    l1_3 = {
        f"L1-3.Q{i+1}": (expected[i] if rng.random() < P["l1_3_match_p"] else ("B" if expected[i] == "A" else "A"))
        for i in range(4)
    }

    # ── L1-4 구두쇠-낭비벽 ────────────────────────────────────────────────
    l1_4 = {
        "L1-4.Q1": _likert(rng, P["l1_4_mean"], 11, sd=1.8),
        "L1-4.Q2a": _likert(rng, P["l1_4_mean"] * 0.8, 5, sd=0.8),
        "L1-4.Q2b": _likert(rng, 5 - P["l1_4_mean"] * 0.8, 5, sd=0.8),
        "L1-4.Q3": _likert(rng, 5 - P["l1_4_mean"] * 0.5, 5, sd=0.8),
    }

    # ── L1-5 프레이밍 + L1-6 절약 ─────────────────────────────────────────
    l1_5 = {
        "L1-5.Q1.condition": _pick(rng, ["gain", "loss"]),
        "L1-5.Q1.response": rng.randint(1, 2),
    }
    l1_6 = {
        "L1-6.Q1.condition": _pick(rng, ["calculator", "jacket"]),
        "L1-6.Q1.response": _pick(rng, ["yes", "no"]),
    }

    # ── L2-1 ~ L2-4 ────────────────────────────────────────────────────────
    l2_1 = {f"L2-1.Q{i}": _likert(rng, P["l2_max_mean"], 7) for i in range(1, 7)}
    l2_2 = {f"L2-2.Q{i}": _likert(rng, P["l2_nfclo_mean"], 6) for i in range(1, 16)}
    l2_3 = {f"L2-3.Q{i}": _likert(rng, P["l2_nfc_mean"], 5) for i in range(1, 19)}
    crt_p = P["l2_crt_correct_p"]
    crt_distractors = [["라일라", "선우"], [5, 10, 100], [4, 8, 24], [16, 20, 12]]
    l2_4 = {
        "L2-4.Q1": _categorical_pick(rng, CRT_ANSWERS[0], crt_p, crt_distractors[0]),
        "L2-4.Q2": _categorical_pick(rng, CRT_ANSWERS[1], crt_p, crt_distractors[1]),
        "L2-4.Q3": _categorical_pick(rng, CRT_ANSWERS[2], crt_p, crt_distractors[2]),
        "L2-4.Q4": _categorical_pick(rng, CRT_ANSWERS[3], crt_p, crt_distractors[3]),
    }

    # ── L3-1 ~ L3-3 ────────────────────────────────────────────────────────
    l3_1 = {f"L3-1.Q{i}": _likert(rng, P["l3_reg_focus_mean"], 7) for i in range(1, 11)}
    # L3-2 V1-24: Agency 짝수번호 일부 / Communion 나머지(매핑은 scoring 쪽)
    agency_v = {1, 2, 4, 6, 8, 10, 13, 15, 18, 20, 22, 24}
    l3_2 = {}
    for v in range(1, 25):
        mean = P["l3_agency_mean"] if v in agency_v else P["l3_communion_mean"]
        l3_2[f"L3-2.V{v}"] = _likert(rng, mean, 9)
    l3_3 = {f"L3-3.Q{i}": _likert(rng, P["l3_uniq_mean"], 5) for i in range(1, 13)}

    # ── L3-4 자기차이 (qualitative) ────────────────────────────────────────
    bank = QUALITATIVE_BANK[archetype]
    qa = {
        "aspire": _pick(rng, bank["aspire"]),
        "ought": _pick(rng, bank["ought"]),
        "actual": _pick(rng, bank["actual"]),
        # V1 hold-out — 페르소나 프롬프트에 들어가지 않는 정성 답변 3종
        "recent_purchase": _pick(rng, bank["recent_purchase"]),
        "info_source": _pick(rng, bank["info_source"]),
        "lifestyle": _pick(rng, bank["lifestyle"]),
    }
    l3_4 = {
        "L3-4.Q1": qa["aspire"],
        "L3-4.Q2": qa["ought"],
        "L3-4.Q3": qa["actual"],
    }

    # ── L4-1 ~ L4-6 ────────────────────────────────────────────────────────
    l4_1 = {f"L4-1.Q{i}": _likert(rng, P["l4_sm_mean"], 6) for i in range(1, 14)}
    # L4-2 16문항 = 4 그룹(수평/수직 × 개인/집단주의) × 4문항
    l4_2 = {}
    group_means = [P["l4_indiv_h"], P["l4_indiv_v"], P["l4_coll_h"], P["l4_coll_v"]]
    for i in range(1, 17):
        mean = group_means[(i - 1) // 4]
        l4_2[f"L4-2.Q{i}"] = _likert(rng, mean, 7)
    # L4-3 사회적 바람직성 — 사회적 응답을 따라가는 확률
    # 정답 패턴: TRUE on Q5,7,9,10,13 + FALSE on Q1,2,3,4,6,8,11,12
    sd_true_idx = {5, 7, 9, 10, 13}
    sd_p = 0.55
    l4_3 = {
        f"L4-3.Q{i}": _binary_prob(rng, sd_p if i in sd_true_idx else 1 - sd_p)
        for i in range(1, 14)
    }
    l4_4 = {f"L4-4.Q{i}": _likert(rng, P["l4_empathy_mean"], 5) for i in range(1, 21)}
    l4_5 = {f"L4-5.P1.Q{i}": _likert(rng, P["l4_fc_p1_mean"], 5) for i in range(1, 11)}
    l4_5.update({f"L4-5.P2.Q{i}": max(0, min(100, round(rng.gauss(P["l4_fc_p2_mean"], 15)))) for i in range(1, 11)})
    l4_6 = {"L4-6.Q1": _pick(rng, P["l4_dictator"])}

    # ── L5 ~ L6 ────────────────────────────────────────────────────────────
    l5_1 = {f"L5-1.Q{i}": _likert(rng, P["l5_min_mean"], 5) for i in range(1, 13)}
    l5_2 = {f"L5-2.Q{i}": _likert(rng, P["l5_green_mean"], 5) for i in range(1, 7)}
    dr_lo, dr_hi = P["l6_dr_q1_x"]
    pb_lo, pb_hi = P["l6_pb_q1_x"]
    l6_1 = {
        "L6-1.Q1.row_first_certain": rng.randint(dr_lo, dr_hi),
        "L6-1.Q2.row_first_certain": rng.randint(dr_lo + 1500, dr_hi + 1500),
        "L6-1.Q3.row_first_certain": rng.randint(dr_lo + 2500, dr_hi + 2500),
    }
    l6_2 = {
        "L6-2.Q1.row_first_certain": rng.randint(pb_lo, pb_hi),
        "L6-2.Q2.row_first_certain": rng.randint(pb_lo + 1500, pb_hi + 1500),
        "L6-2.Q3.row_first_certain": rng.randint(pb_lo + 2500, pb_hi + 2500),
    }
    # L6-3 성실성: 1~4 응답>5, 5~8(역채점) 응답<5
    high_p = P["l6_consc_high_p"]
    l6_3 = {}
    for i in range(1, 5):
        l6_3[f"L6-3.Q{i}"] = rng.randint(6, 9) if rng.random() < high_p else rng.randint(1, 5)
    for i in range(5, 9):
        l6_3[f"L6-3.Q{i}"] = rng.randint(1, 4) if rng.random() < high_p else rng.randint(5, 9)

    # ── C-2 금융, C-3 수리 ─────────────────────────────────────────────────
    fin_dist = [
        ["FALSE"], [1, 2, 4], [1, 3, 4], ["FALSE"],
        [1, 3, 4], [1, 3, 4], ["FALSE"], ["1년", "10년", "100년"],
    ]
    c_2 = {
        f"C-2.Q{i+1}": _categorical_pick(rng, FIN_ANSWERS[i], P["fin_correct_p"], fin_dist[i])
        for i in range(8)
    }
    num_dist = [
        [100, 1000], [5, 50], [10, 50], [0.01, 1],
        [50, 200], [1, 10], [100, 1000], [50, 100],
    ]
    c_3 = {
        f"C-3.Q{i+1}": _categorical_pick(rng, NUM_ANSWERS[i], P["num_correct_p"], num_dist[i])
        for i in range(8)
    }

    # ── 인구통계 ───────────────────────────────────────────────────────────
    demographics = {
        "region": _pick(rng, REGIONS),
        "gender": _pick(rng, GENDERS),
        "age_range": _pick(rng, AGE_RANGES),
        "education": _pick(rng, EDUCATION),
        "nationality": _pick(rng, NATIONALITY),
        "visa_status": _pick(rng, VISA),
        "marital_status": _pick(rng, MARITAL),
        "religion": _pick(rng, RELIGION),
        "religion_frequency": _pick(rng, ["전혀 안 함", "년 1~2회", "월 1~2회", "주 1회 이상"]),
        "political_party": _pick(rng, POLITICAL_PARTY),
        "household_income": _pick(rng, INCOMES),
        "political_views": rng.randint(1, 7),
        "household_size": _pick(rng, HOUSEHOLD_SIZES),
        "employment": _pick(rng, EMPLOYMENT),
    }

    # ── 합치기 ─────────────────────────────────────────────────────────────
    responses = {}
    for d in (l1_1, l1_2, l1_3, l1_4, l1_5, l1_6,
              l2_1, l2_2, l2_3, l2_4,
              l3_1, l3_2, l3_3, l3_4,
              l4_1, l4_2, l4_3, l4_4, l4_5, l4_6,
              l5_1, l5_2,
              l6_1, l6_2, l6_3,
              c_2, c_3):
        responses.update(d)

    return {
        "respondent_id": f"mock_{archetype}_{idx:03d}",
        "collected_at": "2026-05-16T10:00:00+09:00",
        "archetype": archetype,
        "demographics": demographics,
        "responses": responses,
        "qualitative": {
            "self_aspire": qa["aspire"],
            "self_ought": qa["ought"],
            "self_actual": qa["actual"],
            "dictator_reasoning": _pick(rng, [
                "필요한 만큼만 나누는 것이 합리적이라 봤습니다.",
                "상대도 사람인데 나만 챙기는 건 어색해서 절반 정도 나눴습니다.",
                "처음 보는 사람이라 기본만 주는 게 맞다고 생각했습니다.",
                "내 몫을 줄이더라도 상대가 더 가져가는 편이 마음 편합니다.",
            ]),
            # V1 hold-out 정성 답변 — 페르소나 프롬프트에 들어가지 않으므로
            # "안 보고 답하는" 평가로 사용 가능. stimuli.py 와 scratch_key 동기.
            "holdout_recent_purchase": qa["recent_purchase"],
            "holdout_info_source": qa["info_source"],
            "holdout_lifestyle": qa["lifestyle"],
        },
    }


def generate_records(count: int, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    out = []
    per_archetype = max(1, count // len(ARCHETYPES))
    plan: list[tuple[int, str]] = []
    for ai, arch in enumerate(ARCHETYPES):
        for j in range(per_archetype):
            plan.append((ai * per_archetype + j, arch))
    # 잔여(count 가 6 의 배수가 아닐 때)
    remainder = count - len(plan)
    for k in range(remainder):
        plan.append((len(plan), ARCHETYPES[k % len(ARCHETYPES)]))
    # 셔플 — 적재 순서가 archetype 순이 아니도록
    rng.shuffle(plan)
    for idx, arch in plan:
        out.append(generate_record(rng, idx, arch))
    return out


def main():
    parser = argparse.ArgumentParser(description="Mock Twin-2K-500 응답 생성기")
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="tests/_fixtures/mock_twin_30.json")
    args = parser.parse_args()

    records = generate_records(args.count, seed=args.seed)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[MOCK] {len(records)}건 생성 → {out_path}")


if __name__ == "__main__":
    main()
