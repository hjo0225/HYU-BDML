'use client';

// FGI 종료 후 인사이트 보고서(build_report — LLM 다회 호출)가 만들어지는 동안 토론창 위에
// 띄우는 반복 재생 오버레이. report_building 이벤트 ~ session_end 사이의 공백을 채운다.
// 부모는 position:relative 컨테이너여야 한다(absolute inset-0).
// 색은 DESIGN 토큰(Tailwind)만 사용하고, 모션 keyframe 만 styled-jsx 로 둔다.
import { useEffect, useState } from 'react';

// 실제 build_report 단계(발화 분석 → 합의/이견 → 인사이트 → 1:1 검증 → 정리)를 반영한 문구.
const STEPS = [
  '발화를 빠짐없이 읽는 중',
  '합의와 이견을 가려내는 중',
  '핵심 인사이트를 정리하는 중',
  '1:1 후속 검증을 구성하는 중',
  '보고서를 다듬는 중',
];

export function ReportBuildingOverlay() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStep((s) => (s + 1) % STEPS.length), 1600);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-5 rounded-xl bg-indigo-950/70 backdrop-blur-[2px]">
      {/* 문서가 한 줄씩 조립되고 스캔 라인이 훑는 애니메이션 */}
      <div className="relative h-24 w-[72px]">
        <div className="absolute inset-0 overflow-hidden rounded-lg border border-white/30 bg-white shadow-elevated">
          <div className="space-y-1.5 p-3">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className="mb-line h-1.5 rounded-full bg-indigo-500"
                style={{ width: ['80%', '100%', '62%', '90%'][i], animationDelay: `${i * 0.18}s` }}
              />
            ))}
          </div>
          {/* 스캔 라인 — 위에서 아래로 반복 */}
          <div className="mb-scan absolute inset-x-0 h-5 bg-gradient-to-b from-indigo-500/40 to-transparent" />
        </div>
      </div>

      <div className="text-center">
        <p className="text-sm font-bold text-white">인사이트 보고서를 만드는 중…</p>
        {/* key 로 문구 교체 시 페이드 재생 */}
        <p key={step} className="mb-fade mt-1 text-xs text-white/80">
          {STEPS[step]}
        </p>
      </div>

      {/* 무한 진행 막대 */}
      <div className="relative h-1 w-40 overflow-hidden rounded-full bg-white/20">
        <div className="mb-slide absolute inset-y-0 w-1/3 rounded-full bg-white/85" />
      </div>

      <style jsx>{`
        .mb-line {
          animation: mb-shimmer 1.4s ease-in-out infinite;
        }
        .mb-scan {
          animation: mb-scan 1.9s ease-in-out infinite;
        }
        .mb-slide {
          animation: mb-slide 1.3s ease-in-out infinite;
        }
        .mb-fade {
          animation: mb-fade 0.5s ease;
        }
        @keyframes mb-shimmer {
          0%,
          100% {
            opacity: 0.3;
          }
          50% {
            opacity: 1;
          }
        }
        @keyframes mb-scan {
          0% {
            top: -20%;
            opacity: 0;
          }
          15% {
            opacity: 1;
          }
          85% {
            opacity: 1;
          }
          100% {
            top: 100%;
            opacity: 0;
          }
        }
        @keyframes mb-slide {
          0% {
            left: -35%;
          }
          100% {
            left: 100%;
          }
        }
        @keyframes mb-fade {
          from {
            opacity: 0;
            transform: translateY(4px);
          }
          to {
            opacity: 1;
            transform: none;
          }
        }
      `}</style>
    </div>
  );
}
