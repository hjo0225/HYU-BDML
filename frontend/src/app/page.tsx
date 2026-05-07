'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';

export default function LandingPage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && user) {
      router.push('/dashboard');
    }
  }, [user, isLoading, router]);

  if (isLoading) return null;

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4"
         style={{ background: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4F46E5 100%)' }}>
      <div className="max-w-2xl w-full text-center text-white">
        <div className="mb-6">
          <span className="text-5xl font-bold tracking-tight">Ditto</span>
          <span className="ml-2 text-2xl text-violet-300 font-light">Research</span>
        </div>

        <h1 className="text-xl md:text-2xl font-medium mb-4 text-indigo-100">
          AI 에이전트 생성 · 성장 · 평가 플랫폼
        </h1>
        <p className="text-indigo-200 mb-10 leading-relaxed text-sm md:text-base">
          Twin-2K-500 데이터셋 기반의 6-Lens 심리측정 프레임워크로 <br />
          실제 한국 소비자를 닮은 디지털 트윈 에이전트를 연구하세요.
        </p>

        <div className="grid grid-cols-3 gap-4 mb-10 text-sm">
          {[
            { label: '에이전트 생성', desc: '6-Lens 기반 심리 프로파일링' },
            { label: '1:1 대화·FGI', desc: '에이전트 성장 및 기억 형성' },
            { label: '성능 평가', desc: 'V1~V5 다차원 평가 대시보드' },
          ].map(({ label, desc }) => (
            <div key={label} className="bg-white/10 rounded-xl p-4 backdrop-blur-sm">
              <p className="font-semibold mb-1">{label}</p>
              <p className="text-indigo-200 text-xs">{desc}</p>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-center gap-4">
          <Link
            href="/login"
            className="px-6 py-3 bg-white text-indigo font-semibold rounded-lg
                       hover:bg-indigo-50 transition-colors"
          >
            로그인
          </Link>
          <Link
            href="/register"
            className="px-6 py-3 bg-violet text-white font-semibold rounded-lg
                       hover:bg-violet-hover transition-colors"
          >
            회원가입
          </Link>
        </div>
      </div>
    </div>
  );
}
