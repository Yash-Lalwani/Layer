import type { Metadata } from 'next';
import { auth } from '@clerk/nextjs/server';
import { cookies } from 'next/headers';
import { guestCookie } from '@/lib/guest';

export const metadata: Metadata = { title: 'Workspace | Layer' };

export default async function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, redirectToSignIn } = await auth();
  const guestToken = (await cookies()).get(guestCookie)?.value;
  if (!isAuthenticated && !guestToken) return redirectToSignIn();
  return children;
}
