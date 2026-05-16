# 🏛️ DESIGN.md — Ditto

> 디자인 토큰 + 컴포넌트 규칙의 Single Source of Truth. UI 코드 작성 전 반드시 이 문서를 먼저 읽고, 정의된 토큰만 사용한다. 새 토큰이 필요하면 코드보다 이 문서를 먼저 수정한다.

## 1. 🎨 핵심 디자인 토큰 (Design Tokens)
*모든 수치는 W3C DTCG 표준 규격을 따릅니다.*

### 1-1. 색상 (Colors)

> **테마 방향: Indigo-tinted neutral.** 순수 회색이 아닌 indigo 색조로 살짝 물든 중성 팔레트를 사용한다. 브랜드 indigo(`#4F46E5`) 가 모든 표면에 자연스럽게 녹아드는 monochrome 브랜딩(Linear · Vercel 류) 을 지향. 인증 페이지 그라데이션(`auth-gradient`) 의 깊은 indigo(`#1e1b4b`) 가 본문 `text.primary` 와 동일 hex 라는 점이 이 결정의 기반. CSS 변수 정의는 [`frontend/src/styles/globals.css`](./frontend/src/styles/globals.css) `:root`.

| 토큰명 | 값 | CSS 변수 | 용도 및 설명 |
| :--- | :--- | :--- | :--- |
| `color.brand.primary` | `#4F46E5` | `--indigo` | 메인 브랜드 컬러 — Indigo. CTA 버튼·링크·포커스 링·활성 인디케이터 |
| `color.brand.primary.hover` | `#4338CA` | `--indigo-hover` | Primary 버튼 hover |
| `color.brand.primary.light` | `#eef2ff` | `--indigo-light` | Secondary 버튼 hover 배경, 활성 탭 배경 |
| `color.brand.secondary` | `#8B5CF6` | `--violet` | 보조 브랜드 컬러 — Violet. 강조 배지·점수 시각화 보조 |
| `color.brand.secondary.hover` | `#7C3AED` | `--violet-hover` | Violet 버튼 hover |
| `color.brand.secondary.light` | `#f5f3ff` | `--violet-light` | Violet 강조 배경 |
| `color.text.primary` | `#1e1b4b` | `--text-primary` | 기본 본문 및 제목 텍스트 — 깊은 indigo (검정 대신) |
| `color.text.secondary` | `#4338ca` | `--text-secondary` | 부제·강조 텍스트 — 중간 indigo |
| `color.text.muted` | `#9ca3af` | `--text-muted` | 부가 설명, 비활성화 텍스트 — 옅은 회색 |
| `color.bg.canvas` | `#f5f7ff` | `--bg` | 전체 페이지 바탕색 — 매우 옅은 indigo tint |
| `color.bg.surface` | `#ffffff` | `--surface` | 카드, 섹션, 입력창 배경 — 순수 흰색 (canvas 와 명확히 구분되도록 swap 됨) |
| `color.border.base` | `#e0e4f0` | `--border` | 선, 테두리, 구분선 — 옅은 indigo-gray |
| `color.bg.auth-gradient` | `linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4F46E5 100%)` | `--auth-gradient` | 로그인·회원가입·랜딩 hero 배경 그라데이션 |
| `color.status.success` | `#10b981` | `--success` | V1~V5 점수 양호 (≥0.8) |
| `color.status.warning` | `#f59e0b` | `--warning` | V1~V5 점수 주의 (0.5~0.8) |
| `color.status.error` | `#ef4444` | `--error` | V1~V5 점수 미달 (<0.5), 경고, 삭제 |

### 1-2. 타이포그래피 (Typography)

| DESIGN 토큰 | 값 | Tailwind 유틸 | 설명 |
| :--- | :--- | :--- | :--- |
| `font.family.base` | `Pretendard Variable, Apple SD Gothic Neo, Noto Sans KR, sans-serif` | `font-sans` (기본) | 국문 가독성 중심. CDN: `cdn.jsdelivr.net/gh/orioncactus/pretendard` |
| `font.family.mono` | `JetBrains Mono, Fira Code, monospace` | `font-mono` | 코드·점수 수치 표시 |
| `font.size.xs` | `12px` | `text-xs` | 라벨, 배지 |
| `font.size.sm` | `14px` | `text-sm` | 작은 텍스트, 캡션 |
| `font.size.base` | `16px` | `text-base` | 본문 기본 (1rem) |
| `font.size.lg` | `18px` | `text-lg` | 소제목, 큰 본문 (Tailwind 기본 18px 채택) |
| `font.size.xl` | `30px` | `text-3xl` | 페이지 타이틀 |
| `font.size.score` | `48px` | `text-score` | 게이지 차트 중앙 점수 (Tailwind 확장) |
| `font.weight.normal` | `400` | `font-normal` | 본문 |
| `font.weight.medium` | `500` | `font-medium` | 라벨·버튼 |
| `font.weight.bold` | `700` | `font-bold` | 강조·제목 |

### 1-3. 형태 및 간격 (Shapes & Spacing)

> **구현 원칙:** spacing · radius · fontSize 의 단계 스케일은 **Tailwind 기본값을 정식 채택**하고, Tailwind 에 없는 것만 `tailwind.config.ts` 에서 확장한다. 코드에서는 토큰명이 아닌 Tailwind 유틸(`p-3`, `rounded-lg`, `text-sm`) 을 직접 쓴다. 아래 표는 DESIGN.md ↔ Tailwind 매핑 레퍼런스.

| DESIGN 토큰 | 값 | Tailwind 유틸 | 비고 |
| :--- | :--- | :--- | :--- |
| `size.radius.sm` | `2px` | `rounded-sm` | 배지, 작은 인디케이터 |
| `size.radius.md` | `8px` | `rounded-lg` | 기본 버튼, 입력창, 카드 |
| `size.radius.lg` | `12px` | `rounded-xl` | 차트 카드, 모달 |
| `size.radius.full` | `9999px` | `rounded-full` | 캡슐형 버튼, 태그 |
| `size.spacing.xs` | `4px` | `p-1` / `gap-1` | 토큰 간 미세 여백 |
| `size.spacing.sm` | `12px` | `p-3` / `gap-3` | 요소 내부 간격, 버튼 패딩 |
| `size.spacing.md` | `24px` | `p-6` / `gap-6` | 섹션 간 여백, 컨테이너 패딩 |
| `size.spacing.lg` | `48px` | `p-12` / `gap-12` | 페이지 상하 패딩 |
| `size.shadow.card` | `0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.03)` | `shadow-card` | Tailwind 확장 (config 매핑) |
| `size.shadow.elevated` | `0 10px 15px rgba(0,0,0,0.07), 0 4px 6px rgba(0,0,0,0.05)` | `shadow-elevated` | Tailwind 확장 (config 매핑) |

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
- 메시지/카드 옆에 붙는 작은 캡슐 배지. `rounded-full`, `text-xs`, `font-medium`.
- **임계값은 [`docs/EVAL_SPEC.md`](./docs/EVAL_SPEC.md) §V1 의 SSOT 를 따른다.** 현재 V1 기준: ≥0.80 → `status.success`, 0.60~0.80 → `status.warning`, <0.60 → `status.error`. 옅은 배경은 Tailwind 기본 스케일(`bg-emerald-50` 등) 사용.
- 좌측에 점(•) 인디케이터 + 우측에 점수(소수점 2자리, 선택적 라벨).

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