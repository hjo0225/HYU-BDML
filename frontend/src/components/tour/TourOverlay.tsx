'use client';

// 데모 가이드 투어 오버레이 (plan 0009 · item 0·1).
// 하단 배너(구 TourBanner)를 대체. 현재 경로가 현재 스텝 경로와 일치할 때만 렌더(route-scoped)
// → 랜딩·로그인 등에서는 노출되지 않는다. 대상 요소를 스포트라이트로 강조하고 말풍선으로 안내.
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { TOUR_STEPS, useTour } from '@/contexts/TourContext';

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

const PAD = 8; // 강조 영역 여백(px)

export function TourOverlay() {
  const router = useRouter();
  const pathname = usePathname();
  const { active, step, projectId, setStep, end } = useTour();
  const [rect, setRect] = useState<Rect | null>(null);

  const cur = TOUR_STEPS[step];
  // 현재 경로가 현재 스텝 경로와 일치할 때만 활성 (route-scoped).
  const onStepRoute = !!(active && projectId && cur && pathname === cur.path(projectId));
  const noSpotlight = cur?.spotlight === false;  // 모달처럼 자체 딤이 있는 스텝

  // 대상 요소 위치를 주기적으로 측정 (비동기 로드·스크롤·리사이즈 대응).
  // noSpotlight(모달) 스텝도 측정한다 — 딤은 생략하되 말풍선을 폼 기준으로 배치하기 위해.
  useEffect(() => {
    if (!onStepRoute || !cur) {
      setRect(null);
      return;
    }
    const measure = () => {
      const el = document.querySelector(cur.target);
      if (!el) {
        setRect(null);
        return;
      }
      const r = el.getBoundingClientRect();
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
    };
    measure();
    const id = window.setInterval(measure, 250);
    window.addEventListener('resize', measure);
    window.addEventListener('scroll', measure, true);
    return () => {
      window.clearInterval(id);
      window.removeEventListener('resize', measure);
      window.removeEventListener('scroll', measure, true);
    };
  }, [onStepRoute, cur, step]);

  if (!onStepRoute || !cur || !projectId) return null;

  const isLast = step === TOUR_STEPS.length - 1;
  const go = (i: number) => {
    setStep(i);
    router.push(TOUR_STEPS[i].path(projectId));
  };

  // 강조 영역 (PAD 만큼 확장). 화면 경계로 클램프.
  const hole = rect
    ? {
        top: Math.max(0, rect.top - PAD),
        left: Math.max(0, rect.left - PAD),
        width: rect.width + PAD * 2,
        height: rect.height + PAD * 2,
      }
    : null;

  const CM = 37.795;          // 1cm @ 96dpi
  const BUBBLE_W = 340;       // 말풍선 폭 (w-[340px])

  // 말풍선 위치 — 대상 아래 우선, 공간 부족 시 위. 대상 없으면 상단/중앙.
  const bubbleStyle: React.CSSProperties = (() => {
    // 스포트라이트 없는 스텝(모달): 폼 왼쪽 모서리에서 2cm 떨어진 왼쪽에 배치.
    if (noSpotlight) {
      if (!rect || typeof window === 'undefined') {
        return { top: 96, left: 16 };  // 폼 측정 전 폴백
      }
      const left = Math.max(16, rect.left - 2 * CM - BUBBLE_W);
      const top = Math.max(16, Math.min(rect.top, window.innerHeight - 220));
      return { top, left };
    }
    if (!hole || typeof window === 'undefined') {
      return { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' };
    }
    // 강조 영역 왼쪽 배치 — 우측 끝을 강조 왼쪽에 맞추고, 공간 부족 시 폭을 줄인다.
    if (cur?.bubblePos === 'left') {
      const gap = 12;
      let width = BUBBLE_W;
      let left = hole.left - gap - width;
      if (left < 16) {
        width = Math.max(220, hole.left - gap - 16);
        left = 16;
      }
      const top = Math.max(16, Math.min(hole.top, window.innerHeight - 240));
      return { top, left, width };
    }
    // 강조 사각형과 가로(폭·왼쪽 정렬)를 맞춘다. 단 너무 좁아지지 않게 최소폭 보장.
    const width = Math.min(Math.max(hole.width, 300), window.innerWidth - 32);
    const below = hole.top + hole.height + 12;
    const placeBelow = below + 200 < window.innerHeight;
    const left = Math.min(Math.max(16, hole.left), window.innerWidth - width - 16);
    return placeBelow
      ? { top: below, left, width }
      : { top: Math.max(16, hole.top - 12), left, width, transform: 'translateY(-100%)' };
  })();

  const Bubble = (
    <div
      className="fixed z-[120] w-[340px] max-w-[calc(100vw-32px)] rounded-2xl border border-ditto-indigo/30 bg-surface p-4 shadow-elevated"
      style={bubbleStyle}
      role="dialog"
      aria-label="데모 투어 안내"
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="rounded-full bg-ditto-indigo-light px-2.5 py-1 text-2xs font-semibold text-ditto-indigo">
          데모 투어 {step + 1}/{TOUR_STEPS.length}
        </span>
        <button onClick={end} className="text-xs text-text-muted hover:text-text-primary">
          투어 종료
        </button>
      </div>
      <p className="mb-1 text-sm font-semibold text-text-primary">{cur.title}</p>
      <p className="mb-3 text-xs leading-relaxed text-text-secondary">{cur.desc}</p>
      <div className="flex items-center justify-end gap-2">
        {step > 0 && (
          <button
            onClick={() => go(step - 1)}
            className="min-w-[72px] rounded-lg border border-border px-4 py-1.5 text-center text-xs font-semibold text-text-secondary hover:border-ditto-indigo"
          >
            이전
          </button>
        )}
        {isLast ? (
          <button
            onClick={end}
            className="min-w-[72px] rounded-lg bg-ditto-indigo px-4 py-1.5 text-center text-xs font-semibold text-white hover:bg-ditto-indigo-hover"
          >
            투어 완료
          </button>
        ) : (
          <button
            onClick={() => go(step + 1)}
            className="min-w-[72px] rounded-lg bg-ditto-indigo px-4 py-1.5 text-center text-xs font-semibold text-white hover:bg-ditto-indigo-hover"
          >
            다음 →
          </button>
        )}
      </div>
    </div>
  );

  // 스포트라이트 없는 스텝(모달 등): 말풍선만 (딤은 모달이 담당).
  if (noSpotlight) {
    return Bubble;
  }

  // 대상 미발견 → 전체 딤 + 중앙 말풍선 폴백.
  if (!hole) {
    return (
      <>
        <div className="pointer-events-none fixed inset-0 z-[110] bg-black/80" aria-hidden />
        {Bubble}
      </>
    );
  }

  // 스포트라이트 — 전체 화면을 딤 처리하되 강조 영역만 "둥근 사각형"으로 도려낸다.
  // SVG path + evenodd: 바깥 사각형(전체 화면) − 안쪽 둥근 사각형(구멍).
  // 딤은 순수 시각용(pointer-events:none) — 클릭·휠 스크롤이 모두 통과해 페이지를 자유롭게 스크롤할 수 있다.
  const W = typeof window !== 'undefined' ? window.innerWidth : 0;
  const H = typeof window !== 'undefined' ? window.innerHeight : 0;
  const r = Math.min(12, hole.width / 2, hole.height / 2); // 테두리 rounded-xl(12px)과 동일
  const x = hole.left;
  const y = hole.top;
  const w = hole.width;
  const h = hole.height;
  const cutout =
    `M0 0 H${W} V${H} H0 Z ` +
    `M${x + r} ${y} ` +
    `H${x + w - r} A${r} ${r} 0 0 1 ${x + w} ${y + r} ` +
    `V${y + h - r} A${r} ${r} 0 0 1 ${x + w - r} ${y + h} ` +
    `H${x + r} A${r} ${r} 0 0 1 ${x} ${y + h - r} ` +
    `V${y + r} A${r} ${r} 0 0 1 ${x + r} ${y} Z`;

  return (
    <>
      <svg className="fixed inset-0 z-[110]" width="100%" height="100%" aria-hidden style={{ pointerEvents: 'none' }}>
        <path d={cutout} fillRule="evenodd" fill="rgba(0,0,0,0.8)" style={{ pointerEvents: 'none' }} />
      </svg>
      {/* 강조 테두리 (클릭 통과) */}
      <div
        className="pointer-events-none fixed z-[115] rounded-xl ring-2 ring-white/90"
        style={{ top: hole.top, left: hole.left, width: hole.width, height: hole.height }}
        aria-hidden
      />
      {Bubble}
    </>
  );
}
