'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useProject } from '@/contexts/ProjectContext';

const PHASE_PATHS: Record<number, string> = {
  1: '/research-input',
  2: '/market-research',
  3: '/agent-setup',
  4: '/meeting',
  5: '/minutes',
};

export default function Home() {
  const router = useRouter();
  const { project } = useProject();

  useEffect(() => {
    router.replace(PHASE_PATHS[project.currentPhase] ?? '/research-input');
  }, [router, project.currentPhase]);

  return null;
}
