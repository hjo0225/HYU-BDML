'use client';

import { useState, type FormEvent } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      await login(email, password);
      const redirect = searchParams.get('redirect') || '/';
      router.replace(redirect);
    } catch (err) {
      setError(err instanceof Error ? err.message : '로그인에 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        {/* 로고 영역 */}
        <div className="auth-card__header">
          <div className="auth-card__logo">
            <span className="auth-card__logo-mark">HY</span>
          </div>
          <h1 className="auth-card__title">AI 정성조사 시뮬레이션</h1>
          <p className="auth-card__subtitle">한양대학교 계정으로 로그인하세요</p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <div className="auth-form__field">
            <label htmlFor="login-email" className="auth-form__label">
              이메일
            </label>
            <input
              id="login-email"
              type="email"
              className="auth-form__input"
              placeholder="example@hanyang.ac.kr"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              disabled={isLoading}
            />
          </div>

          <div className="auth-form__field">
            <label htmlFor="login-password" className="auth-form__label">
              비밀번호
            </label>
            <input
              id="login-password"
              type="password"
              className="auth-form__input"
              placeholder="비밀번호를 입력하세요"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              disabled={isLoading}
            />
          </div>

          {error && (
            <div className="auth-form__error" role="alert">
              {error}
            </div>
          )}

          <button
            id="login-submit"
            type="submit"
            className="auth-form__submit"
            disabled={isLoading || !email || !password}
          >
            {isLoading ? (
              <span className="auth-form__submit-loading">
                <span className="auth-form__spinner" />
                로그인 중...
              </span>
            ) : (
              '로그인'
            )}
          </button>
        </form>

        <div className="auth-card__footer">
          계정이 없으신가요?{' '}
          <Link href="/register" className="auth-card__link">
            회원가입
          </Link>
        </div>
      </div>
    </div>
  );
}
