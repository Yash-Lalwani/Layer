'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Menu, PanelRightOpen } from 'lucide-react';
import { useAuth } from '@clerk/nextjs';
import { useApi } from '@/components/api-provider';
import { clearGuestToken, getGuestToken } from '@/lib/guest';
import type { Project, User } from '@/lib/types';
import { ProjectSidebar } from './project-sidebar';
import { ChatPanel } from './chat-panel';
import { SourcesPanel } from './sources-panel';
import { MemoryPanel } from './memory-panel';
import styles from './workspace.module.css';

export function WorkspaceShell({ selectedId }: { selectedId?: string }) {
  const router = useRouter();
  const api = useApi();
  const { isLoaded, isSignedIn } = useAuth();
  const [user, setUser] = useState<User | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [rightTab, setRightTab] = useState<'sources' | 'memory'>('sources');
  const [memoryVersion, setMemoryVersion] = useState(0);
  const selected = projects.find(project => project.id === selectedId);

  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn && !getGuestToken()) {
      router.replace('/login');
      return;
    }
    api.me().then(async nextUser => {
      setUser(nextUser);
      setProjects(await api.projects());
    }).catch(cause => { if (!isSignedIn) { clearGuestToken(); router.replace('/login'); } setError(cause instanceof Error ? cause.message : 'Could not load workspace'); }).finally(() => setLoading(false));
  }, [api, isLoaded, isSignedIn, router]);

  async function create(name: string, description: string) {
    setBusy(true);
    try {
      const project = await api.createProject(name, description || undefined);
      setProjects(current => [project, ...current]);
      setSidebarOpen(false);
      router.push(`/workspace/${project.id}`);
    } finally {
      setBusy(false);
    }
  }

  async function rename(id: string, name: string) {
    setBusy(true);
    try {
      const updated = await api.updateProject(id, { name });
      setProjects(current => current.map(project => project.id === id ? updated : project));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setBusy(true);
    try {
      await api.deleteProject(id);
      setProjects(current => current.filter(project => project.id !== id));
      if (selectedId === id) router.push('/workspace');
    } finally {
      setBusy(false);
    }
  }

  function openSettings(id: string) {
    setSidebarOpen(false);
    setSourcesOpen(true);
    if (selectedId !== id) router.push(`/workspace/${id}`);
  }

  const refreshProjects = useCallback(() => { api.projects().then(setProjects).catch(() => {}); }, [api]);

  if (!isLoaded || (!isSignedIn && !getGuestToken()) || loading && !error) return <div className={styles.loading}>Loading workspace…</div>;

  return <div className={styles.workspace}>
    {sidebarOpen && <button className={styles.scrim} aria-label="Close projects" onClick={() => setSidebarOpen(false)} />}
    <div className={`${styles.sidebarWrap} ${sidebarOpen ? styles.sidebarOpen : ''}`}>
      <ProjectSidebar projects={projects} selectedId={selectedId} userName={user?.name ?? ''} guestQuestionsLeft={user?.is_guest ? user.questions_left : null} busy={busy} onCreate={create} onRename={rename} onDelete={remove} onNavigate={() => setSidebarOpen(false)} onSettings={openSettings} />
    </div>
    <main className={styles.main}>
      <header className={styles.mainHeader}><button className={styles.mobileMenu} onClick={() => setSidebarOpen(true)} aria-label="Open projects"><Menu size={20} /></button><span>{selected?.name ?? 'Workspace'}</span><button className={styles.mobileSources} onClick={() => setSourcesOpen(true)} aria-label="Open sources"><PanelRightOpen size={20} /></button></header>
      <div className={`${styles.content} ${selected ? styles.chatContent : ''}`}>
        {error ? <div className={styles.notice} role="alert">{error}</div> : loading ? <p>Loading projects…</p> : selectedId && !selected ? <div className={styles.empty}><h1>Project not found</h1><p>Choose a project from the sidebar.</p></div> : selected ? <ChatPanel project={selected} questionsLeft={user?.questions_left ?? null} onQuestionsLeft={left => setUser(current => current ? { ...current, questions_left: left } : current)} onMemoryChanged={() => setMemoryVersion(value => value + 1)} /> : <div className={styles.empty}><div className={styles.emptyIcon}>L</div><h1>Welcome to your workspace</h1><p>Choose a project or create a new one.</p></div>}
      </div>
    </main>
    {sourcesOpen && <button className={styles.sourcesScrim} onClick={() => setSourcesOpen(false)} aria-label="Close sources" />}
    <div className={`${styles.rightPanel} ${sourcesOpen ? styles.sourcesOpen : ''}`}>
      <div className={styles.rightTabs}><button className={rightTab === 'sources' ? styles.rightTabActive : ''} onClick={() => setRightTab('sources')}>Sources</button><button className={rightTab === 'memory' ? styles.rightTabActive : ''} onClick={() => setRightTab('memory')}>Memory</button></div>
      {rightTab === 'sources' ? <SourcesPanel project={selected} onClose={() => setSourcesOpen(false)} onChanged={refreshProjects} /> : <MemoryPanel project={selected} version={memoryVersion} onClose={() => setSourcesOpen(false)} />}
    </div>
  </div>;
}
