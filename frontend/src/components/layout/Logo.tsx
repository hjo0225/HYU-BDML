'use client';

import Image from 'next/image';

// 원본 로고 비율 (frontend/public/logo.png — 294×194)
const LOGO_W = 294;
const LOGO_H = 194;

interface LogoProps {
  /** 로고 마크 높이(px). 너비는 원본 비율을 유지해 자동 계산. */
  height?: number;
  /** 'Mind-Bridge' 워드마크에 적용할 클래스(색·크기). 빈 문자열이면 텍스트 숨김. */
  wordmarkClassName?: string;
  className?: string;
}

/**
 * Mind-Bridge 브랜드 로고 — 마크 이미지 + 워드마크.
 * 사이드바·랜딩·인증 페이지에서 공용으로 사용한다.
 */
export function Logo({
  height = 24,
  wordmarkClassName = 'text-lg text-ditto-indigo',
  className = '',
}: LogoProps) {
  const width = Math.round((LOGO_W / LOGO_H) * height);
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <Image
        src="/logo.png"
        alt="Mind-Bridge 로고"
        width={width}
        height={height}
        priority
      />
      {wordmarkClassName && (
        <span className={`font-bold tracking-tight ${wordmarkClassName}`}>Mind-Bridge</span>
      )}
    </span>
  );
}
