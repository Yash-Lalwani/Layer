'use client';

import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MotionConfig } from 'motion/react';
import { ClerkProvider } from '@clerk/nextjs';
import { ApiProvider } from './api-provider';

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity, retry: false } },
  }));

  return <ClerkProvider afterSignOutUrl="/">
    <ApiProvider>
      <QueryClientProvider client={client}>
        <MotionConfig reducedMotion="user">{children}</MotionConfig>
      </QueryClientProvider>
    </ApiProvider>
  </ClerkProvider>;
}
