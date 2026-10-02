'use client';

import { useEffect, useState } from 'react';
import { Brain, X } from 'lucide-react';
import { useApi } from '@/components/api-provider';
import type { MemoryFact, Project } from '@/lib/types';
import styles from './memory.module.css';

export function MemoryPanel({ project, version, onClose }: { project?: Project; version: number; onClose: () => void }) {
  const api = useApi();
  const [facts, setFacts] = useState<MemoryFact[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!project) { setFacts([]); return; }
    let active = true;
    api.memory(project.id).then(rows => active && setFacts(rows)).catch(cause => active && setError(cause instanceof Error ? cause.message : 'Could not load memory'));
    return () => { active = false; };
  }, [api, project?.id, version]);

  async function remove(factId: string) {
    if (!project) return;
    try { await api.deleteMemory(project.id, factId); setFacts(current => current.filter(fact => fact.id !== factId)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not delete fact'); }
  }

  return <aside className={styles.panel}>
    <div className={styles.title}><Brain size={18} />Memory<button onClick={onClose} aria-label="Close memory"><X size={18} /></button></div>
    {!project ? <p>Select a project to view its memory.</p> : facts.length === 0 ? <p>Layer will ask before remembering anything about this project.</p> :
      <div className={styles.list}>{facts.map(fact => <article key={fact.id}><p>{fact.text}</p><div><small>{new Date(fact.created_at).toLocaleDateString()}</small><button onClick={() => void remove(fact.id)}>Delete</button></div></article>)}</div>}
    {error && <p className={styles.error} role="alert">{error}</p>}
  </aside>;
}
