'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useProject } from '@/contexts/ProjectContext';

export default function Home() {
  const router = useRouter();
  const { project } = useProject();

  useEffect(() => {
    router.replace(`/phase-${project.currentPhase}`);
  }, [router, project.currentPhase]);

  return null;
}
