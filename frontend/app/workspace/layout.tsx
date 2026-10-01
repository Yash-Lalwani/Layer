import type { Metadata } from 'next';
import { auth } from '@clerk/nextjs/server';

export const metadata: Metadata = { title: 'Workspace | Layer' };

export default async function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, redirectToSignIn } = await auth();
  if (!isAuthenticated) return redirectToSignIn();
  return children;
}
