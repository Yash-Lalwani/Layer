'use client';

import { useCallback, useEffect, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Database, RefreshCw, X } from 'lucide-react';
import { SourceIcon } from '@/components/source-icon';
import { useApi } from '@/components/api-provider';
import type { DriveConfig, DriveFile, GmailConfig, JiraConfig, JiraProject, NotionConfig, NotionItem, Project, SourceConnection, SourceType } from '@/lib/types';
import { DrivePicker } from './drive-picker';
import { GmailFilter } from './gmail-filter';
import styles from './sources.module.css';

const names: Record<SourceType, string> = { drive: 'Google Drive', gmail: 'Gmail', jira: 'Jira', notion: 'Notion' };

export function SourcesPanel({ project, onClose, onChanged }: { project?: Project; onClose?: () => void; onChanged?: () => void }) {
  const api = useApi();
  const params = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const [sources, setSources] = useState<SourceConnection[]>([]);
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [picker, setPicker] = useState(false);
  const [jiraProjects, setJiraProjects] = useState<JiraProject[]>([]);
  const [notionQuery, setNotionQuery] = useState('');
  const [notionItems, setNotionItems] = useState<NotionItem[]>([]);
  const [busy, setBusy] = useState<SourceType | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [active, setActive] = useState<SourceType | null>(null);
  const [syncStartedAt, setSyncStartedAt] = useState<number | null>(null);
  const id = project?.id;

  const refresh = useCallback(async () => {
    if (!id) return;
    const [next, driveFiles] = await Promise.all([api.sources(id), api.driveFiles(id)]);
    setSources(next); setFiles(driveFiles);
  }, [api, id]);

  useEffect(() => {
    if (!id) { setSources([]); setFiles([]); return; }
    let cancelled = false;
    Promise.all([api.sources(id), api.driveFiles(id)]).then(([next, driveFiles]) => { if (!cancelled) { setSources(next); setFiles(driveFiles); } }).catch(cause => { if (!cancelled) setError(cause instanceof Error ? cause.message : 'Could not load sources'); });
    return () => { cancelled = true; };
  }, [api, id]);

  useEffect(() => {
    const connected = params.get('connected');
    const failed = params.get('connect_error');
    if (connected) { setNotice(`${names[connected as SourceType] ?? connected} connected`); refresh(); onChanged?.(); }
    if (failed) setError(`${names[failed as SourceType] ?? failed} connection failed. Try again.`);
    if (connected || failed) router.replace(pathname);
  }, [params, refresh, onChanged, router, pathname]);

  useEffect(() => {
    if (!id || (!syncStartedAt && !files.some(file => file.status === 'pending' || file.status === 'ingesting'))) return;
    const timer = window.setInterval(() => {
      Promise.all([api.driveFiles(id), api.sources(id)]).then(([nextFiles, nextSources]) => {
        setFiles(nextFiles); setSources(nextSources);
        const finishedAt = nextSources.find(item => item.type === 'drive')?.last_synced_at;
        if (syncStartedAt && finishedAt && new Date(finishedAt).getTime() >= syncStartedAt - 2000 && !nextFiles.some(file => file.status === 'pending' || file.status === 'ingesting')) setSyncStartedAt(null);
      }).catch(() => {});
    }, 3000);
    return () => window.clearInterval(timer);
  }, [api, id, files, syncStartedAt]);

  async function action(type: SourceType, run: () => Promise<void>) {
    setBusy(type); setError(''); setNotice('');
    try { await run(); await refresh(); onChanged?.(); return true; }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Source request failed'); return false; }
    finally { setBusy(null); }
  }

  async function connect(type: SourceType) {
    if (!id) return;
    await action(type, async () => { const result = await api.connectSource(id, type); window.location.assign(result.redirect_url); });
  }

  async function save(type: SourceType, config: DriveConfig | GmailConfig | JiraConfig | NotionConfig) {
    if (!id) return false;
    return action(type, async () => { await api.saveSourceConfig(id, type, config); setNotice(`${names[type]} settings saved`); });
  }

  async function open(type: SourceType) {
    setActive(active === type ? null : type);
    if (!id || active === type) return;
    if (project?.is_demo) return;
    try {
      if (type === 'jira') setJiraProjects(await api.jiraProjects(id));
      if (type === 'notion') setNotionItems(await api.searchNotion(id, ''));
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not load source options'); }
  }

  if (!project) return <aside className={styles.panel}><div className={styles.title}><Database size={18} />Sources</div><p className={styles.muted}>Select a project to connect sources.</p></aside>;

  return <aside className={styles.panel}>
    <div className={styles.title}><Database size={18} />Sources{onClose && <button className={styles.close} onClick={onClose} aria-label="Close sources"><X size={18} /></button>}</div>
    {project.is_demo && <p className={styles.muted}>Demo sources are pre-connected.</p>}
    {notice && <p className={styles.notice} role="status">{notice}</p>}
    {error && <p className={styles.error} role="alert">{error}</p>}
    <div className={styles.cards}>{(['drive', 'gmail', 'jira', 'notion'] as SourceType[]).map(type => {
      const source = sources.find(item => item.type === type);
      const connected = source?.status === 'connected';
      return <section className={styles.card} key={type}>
        <div className={styles.cardHeader}><SourceIcon type={type} /><div><strong>{names[type]}</strong><span>{connected ? source?.account_label || 'Connected' : source?.status === 'needs_reauth' ? 'Reconnect needed' : 'Not connected'}</span></div></div>
        {connected && <button className={styles.expand} onClick={() => open(type)} aria-expanded={active === type}>{active === type ? 'Hide settings' : 'Configure'}</button>}
        {!project.is_demo && <div className={styles.connectionActions}>{connected ? <button disabled={busy === type} onClick={() => action(type, async () => { await api.disconnectSource(id!, type); if (type === 'drive') setFiles([]); setActive(null); })}>Disconnect</button> : <button className={styles.primary} disabled={busy === type} onClick={() => connect(type)}>Connect</button>}</div>}
        {connected && active === type && type === 'drive' && <div className={styles.details}>
          <p className={styles.helper}>Only selected files and folders are synced when you click Sync.</p>
          <p className={styles.muted}>{(source?.config as DriveConfig | null)?.file_ids?.length ?? 0} files · {(source?.config as DriveConfig | null)?.folder_ids?.length ?? 0} folders selected</p>
          {!project.is_demo && <div className={styles.actions}><button onClick={() => setPicker(true)}>Choose files</button><button className={styles.primary} disabled={busy === type || syncStartedAt !== null} onClick={() => action(type, async () => { setSyncStartedAt(Date.now()); await api.syncDrive(id!); setNotice('Drive sync started'); await refresh(); })}><RefreshCw size={13} />{syncStartedAt ? 'Syncing…' : 'Sync'}</button></div>}
          {source?.last_synced_at && <p className={styles.muted}>Last synced {new Date(source.last_synced_at).toLocaleString()}</p>}
          <div className={styles.fileList}>{files.map(file => <div key={file.id}><a href={file.web_url} target="_blank" rel="noreferrer" title={file.name}>{file.name}</a><span className={`${styles.status} ${file.status === 'failed' ? styles.failed : ''}`}>{file.status}</span>{file.error && <small>{file.error}</small>}{!project.is_demo && <button aria-label={`Remove ${file.name}`} onClick={() => action(type, async () => { await api.removeDriveFile(id!, file.id); })}><X size={13} /></button>}</div>)}</div>
        </div>}
        {connected && active === type && type === 'gmail' && !project.is_demo && <GmailFilter key={JSON.stringify(source?.config)} projectId={id!} initial={(source?.config as GmailConfig | null) ?? { labels: [], senders: [], keywords: [], query: '' }} onSave={async config => { await save('gmail', config); }} />}
        {connected && active === type && type === 'gmail' && project.is_demo && <div className={styles.details}><p className={styles.helper}>Searched live whenever you ask.</p><p className={styles.muted}>Query: {(source?.config as GmailConfig | null)?.query || 'All mail'}</p></div>}
        {connected && active === type && type === 'jira' && <JiraSettings projects={jiraProjects} initial={(source?.config as JiraConfig | null) ?? { project_key: '', jql: null }} readOnly={project.is_demo} onSave={async config => { await save('jira', config); }} />}
        {connected && active === type && type === 'notion' && <div className={styles.details}>
          <p className={styles.helper}>Only selected pages and databases, including accessible child pages, can be used.</p>
          {project.is_demo && <p className={styles.muted}>{(source?.config as NotionConfig | null)?.page_ids?.length ?? 0} pages · {(source?.config as NotionConfig | null)?.database_ids?.length ?? 0} databases selected</p>}
          {!project.is_demo && <><div className={styles.search}><input value={notionQuery} onChange={event => setNotionQuery(event.target.value)} placeholder="Search pages or databases" /><button onClick={async () => { try { setNotionItems(await api.searchNotion(id!, notionQuery)); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Search failed'); } }}>Search</button></div><NotionSettings key={JSON.stringify(source?.config)} initial={(source?.config as NotionConfig | null) ?? { page_ids: [], database_ids: [] }} items={notionItems} onSave={async config => { await save('notion', config); }} /></>}
        </div>}
      </section>;
    })}</div>
    {picker && id && <DrivePicker projectId={id} config={(sources.find(item => item.type === 'drive')?.config as DriveConfig | null) ?? { file_ids: [], folder_ids: [] }} onSave={config => save('drive', config)} onClose={() => setPicker(false)} />}
  </aside>;
}

function JiraSettings({ projects, initial, readOnly, onSave }: { projects: JiraProject[]; initial: JiraConfig; readOnly: boolean; onSave: (config: JiraConfig) => Promise<void> }) {
  const [config, setConfig] = useState(initial);
  if (readOnly) return <div className={styles.details}><p className={styles.helper}>Issues are searched live within this project.</p><p className={styles.muted}>Jira project: {config.project_key}</p></div>;
  return <div className={styles.details}><p className={styles.helper}>Issues are searched live within this project.</p><label>Jira project<select disabled={readOnly} value={config.project_key} onChange={event => setConfig({ ...config, project_key: event.target.value })}><option value="">Choose a project</option>{projects.map(project => <option key={project.key} value={project.key}>{project.name} ({project.key})</option>)}</select></label><label>Additional JQL (optional)<input disabled={readOnly} value={config.jql ?? ''} onChange={event => setConfig({ ...config, jql: event.target.value || null })} placeholder="status = Open" /></label>{!readOnly && <button className={styles.primary} disabled={!config.project_key} onClick={() => onSave(config)}>Save Jira settings</button>}</div>;
}

function NotionSettings({ initial, items, onSave }: { initial: NotionConfig; items: NotionItem[]; onSave: (config: NotionConfig) => Promise<void> }) {
  const [config, setConfig] = useState(initial);
  function toggle(item: NotionItem) { const key = item.kind === 'page' ? 'page_ids' : 'database_ids'; setConfig({ ...config, [key]: config[key].includes(item.id) ? config[key].filter(id => id !== item.id) : [...config[key], item.id] }); }
  const elsewhere = [...config.page_ids.map(id => ({ id, kind: 'page' as const })), ...config.database_ids.map(id => ({ id, kind: 'database' as const }))].filter(selected => !items.some(item => item.id === selected.id));
  return <><p className={styles.muted}>{config.page_ids.length} pages · {config.database_ids.length} databases selected</p><div className={styles.notionList}>{items.map(item => <label key={item.id}><input type="checkbox" checked={(item.kind === 'page' ? config.page_ids : config.database_ids).includes(item.id)} onChange={() => toggle(item)} /><span>{item.title}</span><small>{item.kind}</small></label>)}</div>{elsewhere.length > 0 && <div className={styles.otherSelections}><strong>Selected elsewhere</strong>{elsewhere.map(item => <button key={item.id} onClick={() => toggle({ ...item, title: '', url: '' })}>{item.kind} {item.id.slice(0, 12)} <X size={12} /></button>)}</div>}<button className={styles.primary} onClick={() => onSave(config)}>Save selection</button></>;
}
