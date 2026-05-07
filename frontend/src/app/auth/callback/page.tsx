'use client';

import { Suspense, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { auth } from '@/lib/api';

function CallbackInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { setSession } = useAuth();

  useEffect(() => {
    const token = searchParams.get('access_token');
    const error = searchParams.get('error');

    if (error || !token) {
      router.replace('/login?error=' + (error ?? 'oauth_failed'));
      return;
    }

    auth.me(token)
      .then(user => {
        setSession(token, user);
        router.replace('/dashboard');
      })
      .catch(() => router.replace('/login?error=oauth_failed'));
  }, [searchParams, router, setSession]);

  return (
    <div className="min-h-screen flex items-center justify-center auth-page-bg">
      <p className="text-white text-sm">Google 인증 처리 중...</p>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center auth-page-bg">
        <p className="text-white text-sm">로딩 중...</p>
      </div>
    }>
      <CallbackInner />
    </Suspense>
  );
}
