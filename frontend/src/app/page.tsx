'use client';

import Link from 'next/link';
import { Logo } from '@/components/layout/Logo';
import { useAuth } from '@/contexts/AuthContext';

export default function LandingPage() {
  // 자동 리다이렉트 제거(plan 0009 · item 0) — 데모 세션이 복원돼도 사용자가 직접 클릭해 이동.
  const { isLoading } = useAuth();

  if (isLoading) return null;

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 auth-page-bg">
      <div className="max-w-2xl w-full text-center text-white">
        <div className="mb-6 flex items-center justify-center">
          <Logo height={56} wordmarkClassName="text-5xl text-white" />
        </div>

        <h1 className="text-xl md:text-2xl font-medium mb-4 text-indigo-100">
          AI 에이전트 생성 · 성장 · 평가 플랫폼
        </h1>
        <p className="text-indigo-200 mb-10 leading-relaxed text-sm md:text-base">
          실제 소비자의 설문·인터뷰 응답을 학습한 AI 소비자 패널과 <br />
          1:1 대화·그룹 인터뷰(FGI)를 진행하고, 인사이트 보고서를 받아보세요.
        </p>

        <div className="grid grid-cols-3 gap-4 mb-10 text-sm">
          {[
            { label: 'AI 소비자 패널', desc: '실제 응답으로 만든 가상 소비자' },
            { label: '1:1 대화·FGI', desc: '대화·그룹 인터뷰로 의견 수집' },
            { label: '결과 분석', desc: '응답 신뢰도 점검 + 인사이트 보고서' },
          ].map(({ label, desc }) => (
            <div key={label} className="bg-white/10 rounded-xl p-4 backdrop-blur-sm">
              <p className="font-semibold mb-1">{label}</p>
              <p className="text-indigo-200 text-xs">{desc}</p>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-center gap-4">
          <Link
            href="/login"
            className="px-6 py-3 bg-white text-ditto-indigo font-semibold rounded-lg
                       hover:bg-indigo-50 transition-colors"
          >
            로그인
          </Link>
          <Link
            href="/register"
            className="px-6 py-3 bg-ditto-violet text-white font-semibold rounded-lg
                       hover:bg-ditto-violet-hover transition-colors"
          >
            회원가입
          </Link>
          <Link
            href="/demo"
            className="px-6 py-3 border border-white/60 text-white font-semibold rounded-lg
                       hover:bg-white/10 transition-colors"
          >
            ✨ 데모 사용해보기
          </Link>
        </div>
      </div>
    </div>
  );
}
