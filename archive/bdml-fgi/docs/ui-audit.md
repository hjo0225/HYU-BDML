# UI Audit — Playwright 1회성 감사 보고서

> 본 문서는 `scripts/playwright-audit/audit.mjs` 실행 결과를 정리하는 템플릿이다.
> 실행 후 페이지별로 화면 캡처와 axe-core 위반·콘솔 에러를 채워 넣는다.

## 실행 환경

- **감사 일자**: _(스크립트 실행 후 채울 것)_
- **BASE_URL**: `http://localhost:3000`
- **뷰포트**: 데스크톱 1440×900 / 모바일 390×844
- **자동화 도구**: Playwright (Chromium) + axe-core 4.x (CDN)
- **원자료**: `scripts/playwright-audit/audit-results.json`, `scripts/playwright-audit/screenshots/`

## 우선순위 정의

| 등급 | 기준 |
|---|---|
| **P1** | 페이지 사용 불가 / WCAG critical·serious 위반 / 콘솔 에러로 기능 깨짐 |
| **P2** | 사용성 저해 (반응형 깨짐, 콘트라스트 부족, 키보드 내비 일부 막힘) |
| **P3** | 일관성·미감 개선 (간격, 폰트 사이즈, 마이크로카피) |

---

## 페이지별 감사 결과

각 페이지에 대해 다음 형식으로 정리한다. 채우지 않은 섹션은 "_(미감사)_"로 둔다.

### `/` — 랜딩 페이지

- **데스크톱 캡처**: `screenshots/desktop/landing.png`
- **모바일 캡처**: `screenshots/mobile/landing.png`
- **axe-core 위반**: _(채울 것)_
- **콘솔 에러**: _(채울 것)_
- **이슈 / 개선 제안**:
  - **P1**: _(예: 메인 CTA 버튼 클릭 영역이 모바일에서 44px 미만)_
  - **P2**:
  - **P3**:
- **관련 컴포넌트**: `frontend/src/app/page.tsx`, `frontend/src/styles/globals.css` (`.landing-*`)

### `/login`

- **데스크톱**: `screenshots/desktop/login.png`
- **모바일**: `screenshots/mobile/login.png`
- **이슈**:
- **관련**: `frontend/src/app/login/page.tsx`

### `/register`

- **데스크톱**: `screenshots/desktop/register.png`
- **모바일**: `screenshots/mobile/register.png`
- **이슈**:
- **관련**: `frontend/src/app/register/page.tsx`

### `/lab` — 실험실 목록

- **데스크톱**: `screenshots/desktop/lab-list.png`
- **모바일**: `screenshots/mobile/lab-list.png`
- **이슈**:
- **관련**: `frontend/src/app/lab/page.tsx`, `frontend/src/app/lab/layout.tsx`

### `/lab/chat/{twinId}` — Lab 1:1 메신저

- _(인증 불필요지만 동적 경로라 감사 스크립트가 자동 진입하지 않는다. 수동 캡처 권장.)_
- **수동 확인 항목**:
  - 메시지 말풍선 좌/우 정렬, 가독성
  - 입력 textarea 자동 높이
  - 모바일에서 inputbar가 가상 키보드와 겹치지 않는지
  - rate limit 도달(30회) 시 안내 표시

### `/dashboard` — 프로젝트 목록 (인증 필요)

- **데스크톱**: `screenshots/desktop/dashboard.png` (`AUDIT_EMAIL` 설정 시)
- **모바일**: `screenshots/mobile/dashboard.png`
- **이슈**:
- **관련**: `frontend/src/app/dashboard/page.tsx`

### `/research-input` — Phase 1

- **이슈**:
- **관련**: `frontend/src/app/(phases)/research-input/page.tsx`

### `/market-research` — Phase 2

- **이슈**:
- **관련**: `frontend/src/app/(phases)/market-research/page.tsx`

### `/agent-setup` — Phase 3

- **이슈**:
- **관련**: `frontend/src/app/(phases)/agent-setup/page.tsx`

### `/meeting` — Phase 4

- **이슈**:
- **관련**: `frontend/src/app/(phases)/meeting/page.tsx`

### `/minutes` — Phase 5

- **이슈**:
- **관련**: `frontend/src/app/(phases)/minutes/page.tsx`

---

## 수동 확인 필요 (자동 감사 한계)

자동 도구로 잡히지 않는 항목들이다. 캡처 결과를 보면서 채워 넣는다.

- [ ] 랜딩 히어로 그라데이션이 모바일에서 텍스트와 충분한 대비를 유지하는가
- [ ] Phase 4 회의 채팅 말풍선이 긴 발언에서도 줄바꿈이 자연스러운가
- [ ] Phase 3 위저드 step 전환 애니메이션이 부드러운가
- [ ] Stepper의 현재 단계가 모바일에서 잘리지 않는가
- [ ] Lab 메신저 입력창이 iOS Safari의 100vh 이슈를 겪지 않는가
- [ ] AppShell이 숨겨진 페이지(`/dashboard`, `/lab/*`)와 보이는 페이지의 시각적 구분
- [ ] 로그인 후 redirect 흐름이 의도대로 동작하는가 (`/`, `/login?redirect=...`)

---

## 다음 작업

1. P1 항목별 수정 PR 발행.
2. P2/P3는 디자인 백로그로 이관.
3. 다음 감사 시점: 다음 메이저 UI 변경 PR 머지 후.
