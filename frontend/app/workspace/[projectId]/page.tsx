'use client';

import { useParams } from 'next/navigation';
import { WorkspaceShell } from '@/components/workspace/workspace-shell';

export default function ProjectPage() {
  const { projectId } = useParams<{ projectId: string }>();
  return <WorkspaceShell selectedId={projectId} />;
}

