'use client';

import { FormEvent, useState } from 'react';
import Link from 'next/link';
import { MoreHorizontal, Plus, X } from 'lucide-react';
import { SourceIcon } from '@/components/source-icon';
import type { Project } from '@/lib/types';
import styles from './workspace.module.css';

interface Props {
  projects: Project[];
  selectedId?: string;
  userName: string;
  busy: boolean;
  onCreate: (name: string, description: string) => Promise<void>;
  onRename: (id: string, name: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onLogout: () => void;
  onNavigate: () => void;
}

export function ProjectSidebar({ projects, selectedId, userName, busy, onCreate, onRename, onDelete, onLogout, onNavigate }: Props) {
  const [dialog, setDialog] = useState<'create' | 'rename' | 'delete' | null>(null);
  const [target, setTarget] = useState<Project | null>(null);
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState('');

  function openDialog(mode: 'create' | 'rename' | 'delete', project: Project | null = null) {
    setDialog(mode);
    setTarget(project);
    setName(project?.name ?? '');
    setDescription('');
    setConfirmation('');
    setError('');
    setOpenMenu(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    try {
      if (dialog === 'create') await onCreate(name.trim(), description.trim());
      if (dialog === 'rename' && target) await onRename(target.id, name.trim());
      if (dialog === 'delete' && target) await onDelete(target.id);
      setDialog(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Something went wrong');
    }
  }

  return <aside className={styles.sidebar}>
    <div className={styles.sidebarTop}>
      <Link href="/workspace" className={styles.brand} onClick={onNavigate}><img src="/layer-logo.svg" width="31" height="31" alt="" />Layer</Link>
      <button className={styles.newProject} onClick={() => openDialog('create')}><Plus size={17} />New project</button>
    </div>
    <div className={styles.projectSection}>
      <div className={styles.sectionLabel}>PROJECTS</div>
      {projects.length === 0 && <p className={styles.sidebarEmpty}>Your projects will appear here.</p>}
      <ul className={styles.projectList}>{projects.map(project =>
        <li key={project.id} className={project.id === selectedId ? styles.projectSelected : ''}>
          <Link href={`/workspace/${project.id}`} className={styles.projectLink} onClick={onNavigate} title={project.name}>
            <span className={styles.projectInitial}>{project.name.slice(0, 1).toUpperCase()}</span>
            <span className={styles.projectName}>{project.name}</span>
          </Link>
          <div className={styles.projectIcons}>{project.connected_sources.map(type => <SourceIcon key={type} type={type} />)}</div>
          <button className={styles.moreButton} aria-label={`Options for ${project.name}`} aria-expanded={openMenu === project.id} onClick={() => setOpenMenu(openMenu === project.id ? null : project.id)}><MoreHorizontal size={17} /></button>
          {openMenu === project.id && <div className={styles.projectMenu}>
            <button onClick={() => openDialog('rename', project)}>Rename</button>
            <button onClick={() => openDialog('delete', project)}>Delete</button>
          </div>}
        </li>
      )}</ul>
    </div>
    <div className={styles.userArea}><div className={styles.avatar}>{userName.slice(0, 1).toUpperCase()}</div><span>{userName}</span><button onClick={onLogout}>Log out</button></div>

    {dialog && <div className={styles.dialogBackdrop} onMouseDown={event => { if (event.target === event.currentTarget && !busy) setDialog(null); }}>
      <div className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="project-dialog-title">
        <button className={styles.closeDialog} aria-label="Close" onClick={() => setDialog(null)} disabled={busy}><X size={18} /></button>
        <h2 id="project-dialog-title">{dialog === 'create' ? 'New project' : dialog === 'rename' ? 'Rename project' : 'Delete project'}</h2>
        <form onSubmit={submit}>
          {dialog === 'delete' ? <>
            <p>This will delete <strong>{target?.name}</strong> and its collection. Type the project name to confirm.</p>
            <label>Project name<input value={confirmation} onChange={event => setConfirmation(event.target.value)} autoFocus /></label>
          </> : <>
            <label>Name<input value={name} onChange={event => setName(event.target.value)} required maxLength={100} autoFocus /></label>
            {dialog === 'create' && <label>Description <span>(optional)</span><textarea value={description} onChange={event => setDescription(event.target.value)} maxLength={500} rows={3} /></label>}
          </>}
          {error && <p className={styles.dialogError} role="alert">{error}</p>}
          <div className={styles.dialogActions}><button type="button" onClick={() => setDialog(null)} disabled={busy}>Cancel</button><button type="submit" disabled={busy || (dialog === 'delete' ? confirmation !== target?.name : !name.trim())}>{busy ? 'Please wait…' : dialog === 'delete' ? 'Delete project' : dialog === 'rename' ? 'Save name' : 'Create project'}</button></div>
        </form>
      </div>
    </div>}
  </aside>;
}

