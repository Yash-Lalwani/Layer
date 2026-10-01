'use client';

import { createContext, useContext, useMemo } from 'react';
import { useAuth } from '@clerk/nextjs';
import { createApi, type Api } from '@/lib/api';

const ApiContext = createContext<Api | null>(null);

export function ApiProvider({ children }: { children: React.ReactNode }) {
  const { getToken } = useAuth();
  const api = useMemo(() => createApi(getToken), [getToken]);
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>;
}

export function useApi(): Api {
  const api = useContext(ApiContext);
  if (!api) throw new Error('ApiProvider is missing');
  return api;
}
