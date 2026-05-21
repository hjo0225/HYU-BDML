'use client';

// 데모 진입 = 가이드 투어 런처 (plan 0008 v2 · item 0c).
// 데모 세션을 부트스트랩하고, 투어를 시작한 뒤 실서비스 첫 화면(프로젝트 목록)으로 이동한다.
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { LoadingState } from '@/components/ui/Spinner';
import { useAuth } from '@/contexts/AuthContext';
import { useTour, TOUR_STEPS } from '@/contexts/TourContext';
import { demo as demoApi } from '@/lib/api';
import type { User } from '@/lib/types';

export default function DemoLauncher() {
  const router = useRouter();
  const { setSession } = useAuth();
  const { start } = useTour();
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        const sess = await demoApi.startSession();
        setSession(sess.access_token, sess.user as User);
        start(sess.project_id);
        router.replace(TOUR_STEPS[0].path(sess.project_id));
      } catch (e) {
        setError(e instanceof Error ? e.message : '데모를 시작할 수 없습니다.');
      }
    })();
  }, [router, setSession, start]);

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 px-4 text-center">
        <p className="text-error">{error}</p>
        <p className="text-sm text-text-muted">백엔드가 실행 중인지, 데모 에이전트가 시드되었는지 확인하세요.</p>
        <Link href="/" className="text-sm text-ditto-indigo hover:underline">← 홈으로</Link>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <LoadingState label="데모를 준비하고 실서비스 화면으로 이동하는 중…" />
    </div>
  );
}
