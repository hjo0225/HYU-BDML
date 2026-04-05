'use client';

import { useState, type FormEvent, type ChangeEvent } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';

const ALLOWED_DOMAIN = '@hanyang.ac.kr';

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // 이메일 도메인 실시간 검증
  const emailInvalid =
    email.length > 3 && !email.toLowerCase().endsWith(ALLOWED_DOMAIN);
  const passwordMismatch =
    passwordConfirm.length > 0 && password !== passwordConfirm;
  const passwordShort = password.length > 0 && password.length < 8;

  const isFormValid =
    name.trim() &&
    email &&
    !emailInvalid &&
    password.length >= 8 &&
    password === passwordConfirm;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!isFormValid) return;
    setError('');
    setIsLoading(true);
    try {
      await register(email, password, name);
      router.replace('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : '회원가입에 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-card__header">
          <div className="auth-card__logo">
            <span className="auth-card__logo-mark">HY</span>
          </div>
          <h1 className="auth-card__title">계정 만들기</h1>
          <p className="auth-card__subtitle">한양대학교 이메일로 시작하세요</p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <div className="auth-form__field">
            <label htmlFor="register-name" className="auth-form__label">
              이름
            </label>
            <input
              id="register-name"
              type="text"
              className="auth-form__input"
              placeholder="홍길동"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              disabled={isLoading}
            />
          </div>

          <div className="auth-form__field">
            <label htmlFor="register-email" className="auth-form__label">
              이메일
            </label>
            <input
              id="register-email"
              type="email"
              className={`auth-form__input ${emailInvalid ? 'auth-form__input--error' : ''}`}
              placeholder="example@hanyang.ac.kr"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              disabled={isLoading}
            />
            {emailInvalid && (
              <p className="auth-form__field-error" role="alert">
                한양대학교 이메일(@hanyang.ac.kr)만 사용 가능합니다
              </p>
            )}
          </div>

          <div className="auth-form__field">
            <label htmlFor="register-password" className="auth-form__label">
              비밀번호
            </label>
            <input
              id="register-password"
              type="password"
              className={`auth-form__input ${passwordShort ? 'auth-form__input--error' : ''}`}
              placeholder="8자 이상"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
              disabled={isLoading}
            />
            {passwordShort && (
              <p className="auth-form__field-error" role="alert">
                비밀번호는 8자 이상이어야 합니다
              </p>
            )}
          </div>

          <div className="auth-form__field">
            <label htmlFor="register-password-confirm" className="auth-form__label">
              비밀번호 확인
            </label>
            <input
              id="register-password-confirm"
              type="password"
              className={`auth-form__input ${passwordMismatch ? 'auth-form__input--error' : ''}`}
              placeholder="비밀번호를 다시 입력하세요"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              required
              autoComplete="new-password"
              disabled={isLoading}
            />
            {passwordMismatch && (
              <p className="auth-form__field-error" role="alert">
                비밀번호가 일치하지 않습니다
              </p>
            )}
          </div>

          {error && (
            <div className="auth-form__error" role="alert">
              {error}
            </div>
          )}

          <button
            id="register-submit"
            type="submit"
            className="auth-form__submit"
            disabled={isLoading || !isFormValid}
          >
            {isLoading ? (
              <span className="auth-form__submit-loading">
                <span className="auth-form__spinner" />
                가입 중...
              </span>
            ) : (
              '가입하기'
            )}
          </button>
        </form>

        <div className="auth-card__footer">
          이미 계정이 있으신가요?{' '}
          <Link href="/login" className="auth-card__link">
            로그인
          </Link>
        </div>
      </div>
    </div>
  );
}
