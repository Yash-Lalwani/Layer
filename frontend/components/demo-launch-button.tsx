'use client';

import { useState } from 'react';
import { ArrowUpRight } from 'lucide-react';
import { useApi } from '@/components/api-provider';
import { saveGuestToken } from '@/lib/guest';
import { Button } from './ui/button';

export function DemoLaunchButton() {
  const api = useApi();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function launch() {
    setBusy(true); setError('');
    try {
      const guest = await api.startDemo();
      saveGuestToken(guest.token, guest.project_id);
      window.location.assign(`/workspace/${guest.project_id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The demo is unavailable');
      setBusy(false);
    }
  }
  return <><Button className="pill" disabled={busy} onClick={() => void launch()}>{busy ? 'Opening demo…' : 'Try the demo'} <ArrowUpRight /></Button>{error && <p role="alert">{error}</p>}</>;
}
