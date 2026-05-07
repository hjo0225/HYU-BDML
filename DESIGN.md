# 🏛️ DESIGN.md — Ditto

> 디자인 토큰 + 컴포넌트 규칙의 Single Source of Truth. UI 코드 작성 전 반드시 이 문서를 먼저 읽고, 정의된 토큰만 사용한다. 새 토큰이 필요하면 코드보다 이 문서를 먼저 수정한다.

## 1. 🎨 핵심 디자인 토큰 (Design Tokens)
*모든 수치는 W3C DTCG 표준 규격을 따릅니다.*

### 1-1. 색상 (Colors)
| 토큰명 | 값 | 용도 및 설명 |
| :--- | :--- | :--- |
| `color.brand.primary` | `#4F46E5` | 메인 브랜드 컬러 — Indigo. CTA 버튼·링크·포커스 링·활성 인디케이터 |
| `color.brand.primary.hover` | `#4338CA` | Primary 버튼 hover |
| `color.brand.secondary` | `#8B5CF6` | 보조 브랜드 컬러 — Violet. 강조 배지·점수 시각화 보조 |
| `color.text.primary` | `#1F2937` | 기본 본문 및 제목 텍스트 |
| `color.text.muted` | `#6B7280` | 부가 설명, 비활성화 텍스트 |
| `color.bg.canvas` | `#FFFFFF` | 전체 페이지 바탕색 |
| `color.bg.surface` | `#F9FAFB` | 카드, 섹션 등 구분용 배경색 |
| `color.border.base` | `#E5E7EB` | 선, 테두리, 구분선 |
| `color.status.success` | `#10B981` | V1~V5 점수 양호 (≥0.8) |
| `color.status.warning` | `#F59E0B` | V1~V5 점수 주의 (0.5~0.8) |
| `color.status.error` | `#EF4444` | V1~V5 점수 미달 (<0.5), 경고, 삭제 |

### 1-2. 타이포그래피 (Typography)
| 토큰명 | 값 | 설명 |
| :--- | :--- | :--- |
| `font.family.base` | `Pretendard, system-ui, sans-serif` | 기본 서체 (국문 가독성 중심). cdn.jsdelivr.net/gh/orioncactus/pretendard 또는 self-host |
| `font.family.mono` | `ui-monospace, SFMono-Regular, "JetBrains Mono", monospace` | 코드·점수 수치 표시 |
| `font.size.xs` | `12px` | 라벨, 배지 텍스트 |
| `font.size.sm` | `14px` | 작은 텍스트, 캡션, 보조 정보 |
| `font.size.base` | `16px` | 본문 기본 크기 (1rem) |
| `font.size.lg` | `20px` | 소제목, 큰 본문 |
| `font.size.xl` | `28px` | 페이지 타이틀 |
| `font.size.score` | `48px` | 게이지 차트 중앙 점수 표시 |
| `font.weight.normal` | `400` | 일반 텍스트용 두께 |
| `font.weight.medium` | `500` | 라벨, 버튼 |
| `font.weight.bold` | `700` | 강조 및 제목용 두께 |

### 1-3. 형태 및 간격 (Shapes & Spacing)
| 토큰명 | 값 | 설명 |
| :--- | :--- | :--- |
| `size.radius.sm` | `4px` | 배지, 작은 인디케이터 |
| `size.radius.md` | `8px` | 기본 버튼, 입력창, 카드의 모서리 둥글기 |
| `size.radius.lg` | `16px` | 차트 카드, 모달 |
| `size.radius.full` | `9999px` | 캡슐형 버튼, 태그용 |
| `size.spacing.xs` | `4px` | 토큰 간 미세 여백 |
| `size.spacing.sm` | `12px` | 요소 내부 간격, 버튼 패딩 |
| `size.spacing.md` | `24px` | 섹션 간 여백, 컨테이너 패딩 |
| `size.spacing.lg` | `48px` | 페이지 상하 패딩 |
| `size.shadow.card` | `0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.03)` | 카드 그림자 |
| `size.shadow.elevated` | `0 10px 15px rgba(0,0,0,0.07), 0 4px 6px rgba(0,0,0,0.05)` | 모달, 드롭다운 |

## 2. 🧱 주요 컴포넌트 규칙 (Component Rules)

### 🔘 버튼 (Buttons)
- **Primary**: `color.brand.primary` 배경 + 흰색 글자.
- **Secondary**: 투명 배경 + `color.brand.primary` 테두리와 글자.
- **Common**: 모든 버튼은 호버(Hover) 시 투명도가 0.8로 변하며, `size.radius.md`를 적용한다.

### 📥 입력창 (Inputs)
- 테두리는 `color.border.base`, 포커스 시 `color.brand.primary` 색상의 2px 테두리 적용.
- 모서리는 버튼과 동일하게 `size.radius.md` 적용.

### 💬 채팅 버블 (ChatBubble)
- 1:1 대화 / FGI 메신저 UI 의 메시지 단위 컨테이너.
- **사용자(나)**: `color.brand.primary` 배경 + 흰색 글자, 우측 정렬, `size.radius.lg` (좌하단 라운드 4px 만 끝부리 처리).
- **에이전트**: `color.bg.surface` 배경 + `color.text.primary` 글자, 좌측 정렬, `size.radius.lg` (우하단 4px).
- **모더레이터(FGI)**: 중앙 정렬, 점선 테두리 (`color.border.base`), `font.size.sm`, 옅은 배경.
- 인용·신뢰도 배지는 버블 하단에 inline 부착 (V1 응답 동기화율 시각화 시).

### 🎚️ 점수 시각화 컴포넌트

대시보드 V1~V5 평가 결과를 표시하는 컴포넌트군. 모두 `Recharts` 기반.

#### Gauge (V1 응답 동기화율 등 단일 지표)
- 0~1 또는 0~100 스케일 반원 게이지.
- 중앙 텍스트: `font.size.score` + `font.weight.bold`.
- 색상: 점수에 따라 `status.success` / `warning` / `error` 자동 전환 (임계값은 `EVAL_SPEC.md` 참조).

#### RadarChart (V1~V5 종합)
- 5축(`sync`, `stability`, `distinct`, `humanity`, `reasoning_delta`) 레이더.
- Stroke = `color.brand.primary`, Fill = `color.brand.primary` α 0.15.
- 축 라벨 = `font.size.sm` + `color.text.muted`.

#### ScoreBadge (인라인 점수 표시)
- 메시지/카드 옆에 붙는 작은 캡슐 배지. `size.radius.full`, `font.size.xs`, `font.weight.medium`.
- 점수 ≥0.8 → `status.success` 배경, 0.5~0.8 → `status.warning`, <0.5 → `status.error`.
- 좌측에 점(•) 인디케이터 + 우측에 점수(소수점 2자리).

### 🎤 FGIInterventionInput (사용자 토론 개입)
- FGI 회의실 하단 고정. 모더레이터 라운드 사이에 활성화되어 사용자가 즉석 발언 삽입.
- 평소: 비활성, `color.text.muted` 안내 ("모더레이터가 발언 차례를 전달하면 입력할 수 있습니다").
- 활성: `color.brand.primary` 2px 외곽선 + 가벼운 펄스 애니메이션 (≤1.5s).
- 단축키 `Enter` 전송, `Shift+Enter` 줄바꿈, `Esc` 입력 포기 (다음 에이전트 라운드로 양보).

## 3. 🤖 AI 작업 수칙 (AI Instructions)
1. **토큰 우선**: CSS 작성 또는 Tailwind 사용 시 위 토큰을 CSS 변수 또는 `tailwind.config.ts`로 매핑하여 사용한다.
2. **일관성 유지**: "모던하게", "예쁘게" 같은 모호한 요청보다 이 문서의 수치를 우선한다.
3. **미정의 토큰 도입 금지**: 새 색상/간격이 필요하면 임의로 hex 값을 쓰지 말고, **이 문서를 먼저 갱신**한 뒤 코드를 수정한다 (별도 commit `chore(design): ...`).
4. **접근성**: 모든 텍스트/배경 조합은 WCAG AA 대비비를 만족해야 한다. `color.text.muted` 위에 더 옅은 색을 얹지 말 것.
5. **차트 컴포넌트화**: Recharts 사용 시 raw 차트를 페이지에 직접 박지 말고, `frontend/src/components/dashboard/` 의 래퍼(`<Gauge />`, `<RadarChart />` 등) 컴포넌트로 추출한다.