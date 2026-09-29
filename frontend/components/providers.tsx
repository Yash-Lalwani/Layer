'use client';
import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MotionConfig } from 'motion/react';
import { AuthProvider } from './auth/auth-provider';
export function Providers({ children }: { children: React.ReactNode }) { const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } })); return <QueryClientProvider client={client}><MotionConfig reducedMotion="user"><AuthProvider>{children}</AuthProvider></MotionConfig></QueryClientProvider>; }
