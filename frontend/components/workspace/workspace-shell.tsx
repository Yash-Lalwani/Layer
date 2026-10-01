'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Menu, PanelRightOpen } from 'lucide-react';
import { useAuth } from '@/components/auth/auth-provider';
import { api } from '@/lib/api';
import type { Project } from '@/lib/types';
import { ProjectSidebar } from './project-sidebar';
import { SourcesPanel } from './sources-panel';
import styles from './workspace.module.css';

export function WorkspaceShell({ selectedId }: { selectedId?: string }) {
  const router = useRouter();
  const { user, loading: authLoading, signOut } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const selected = projects.find(project => project.id === selectedId);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace('/login');
      return;
    }
    api.projects().then(setProjects).catch(cause => setError(cause instanceof Error ? cause.message : 'Could not load projects')).finally(() => setLoading(false));
  }, [authLoading, user, router]);

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

  function logout() {
    signOut();
    router.replace('/login');
  }

  function openSettings(id: string) {
    setSidebarOpen(false);
    setSourcesOpen(true);
    if (selectedId !== id) router.push(`/workspace/${id}`);
  }

  const refreshProjects = useCallback(() => { api.projects().then(setProjects).catch(() => {}); }, []);

  if (authLoading || !user) return <div className={styles.loading}>Loading workspace…</div>;

  return <div className={styles.workspace}>
    {sidebarOpen && <button className={styles.scrim} aria-label="Close projects" onClick={() => setSidebarOpen(false)} />}
    <div className={`${styles.sidebarWrap} ${sidebarOpen ? styles.sidebarOpen : ''}`}>
      <ProjectSidebar projects={projects} selectedId={selectedId} userName={user.name} busy={busy} onCreate={create} onRename={rename} onDelete={remove} onLogout={logout} onNavigate={() => setSidebarOpen(false)} onSettings={openSettings} />
    </div>
    <main className={styles.main}>
      <header className={styles.mainHeader}><button className={styles.mobileMenu} onClick={() => setSidebarOpen(true)} aria-label="Open projects"><Menu size={20} /></button><span>{selected?.name ?? 'Workspace'}</span><button className={styles.mobileSources} onClick={() => setSourcesOpen(true)} aria-label="Open sources"><PanelRightOpen size={20} /></button></header>
      <div className={styles.content}>
        {error ? <div className={styles.notice} role="alert">{error}</div> : loading ? <p>Loading projects…</p> : selectedId && !selected ? <div className={styles.empty}><h1>Project not found</h1><p>Choose a project from the sidebar.</p></div> : selected ? <div className={styles.empty}><div className={styles.emptyIcon}>{selected.name.slice(0, 1).toUpperCase()}</div><h1>{selected.name}</h1><p>{selected.description || 'Your project is ready.'}</p></div> : <div className={styles.empty}><div className={styles.emptyIcon}>L</div><h1>Welcome to your workspace</h1><p>Choose a project or create a new one.</p></div>}
      </div>
    </main>
    {sourcesOpen && <button className={styles.sourcesScrim} onClick={() => setSourcesOpen(false)} aria-label="Close sources" />}
    <div className={`${styles.rightPanel} ${sourcesOpen ? styles.sourcesOpen : ''}`}><SourcesPanel project={selected} onClose={() => setSourcesOpen(false)} onChanged={refreshProjects} /></div>
  </div>;
}
