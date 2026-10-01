'use client';

import { useEffect, useState } from 'react';
import { ChevronRight, Folder, FileText, X } from 'lucide-react';
import { useApi } from '@/components/api-provider';
import type { DriveConfig, DriveItem } from '@/lib/types';
import styles from './sources.module.css';

interface Props { projectId: string; config: DriveConfig; onSave: (config: DriveConfig) => Promise<boolean>; onClose: () => void }

export function DrivePicker({ projectId, config, onSave, onClose }: Props) {
  const api = useApi();
  const [folderId, setFolderId] = useState<string>();
  const [path, setPath] = useState<{ id: string; name: string }[]>([]);
  const [items, setItems] = useState<DriveItem[]>([]);
  const [files, setFiles] = useState(config.file_ids);
  const [folders, setFolders] = useState(config.folder_ids);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.browseDrive(projectId, folderId).then(result => { if (active) { setPath(result.path); setItems(result.items); } }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'Could not browse Drive'); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [api, projectId, folderId]);

  function toggle(item: DriveItem) {
    if (item.kind === 'folder') setFolders(current => current.includes(item.id) ? current.filter(id => id !== item.id) : [...current, item.id]);
    else setFiles(current => current.includes(item.id) ? current.filter(id => id !== item.id) : [...current, item.id]);
  }

  async function save() {
    setBusy(true); setError('');
    try { if (await onSave({ file_ids: files, folder_ids: folders })) onClose(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not save selection'); }
    finally { setBusy(false); }
  }

  return <div className={styles.pickerBackdrop} onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div className={styles.picker} role="dialog" aria-modal="true" aria-label="Choose Drive files and folders">
      <div className={styles.pickerHeader}><div><h2>Choose Drive sources</h2><p>Folders include their files and subfolders when you sync.</p></div><button aria-label="Close" onClick={onClose}><X size={19} /></button></div>
      <div className={styles.breadcrumbs}><button onClick={() => setFolderId(undefined)}>My Drive</button>{path.map(segment => <span key={segment.id}><ChevronRight size={13} /><button onClick={() => setFolderId(segment.id)}>{segment.name}</button></span>)}</div>
      <div className={styles.pickerList}>{loading ? <p>Loading…</p> : items.length === 0 ? <p>No files or folders here.</p> : items.map(item => <div key={item.id} className={styles.pickerRow}>
        <label><input type="checkbox" checked={item.kind === 'folder' ? folders.includes(item.id) : files.includes(item.id)} onChange={() => toggle(item)} aria-label={`Select ${item.name}`} />{item.kind === 'folder' ? <Folder size={17} /> : <FileText size={17} />}<span title={item.name}>{item.name}</span></label>
        {item.kind === 'folder' && <button onClick={() => setFolderId(item.id)} aria-label={`Open ${item.name}`}><ChevronRight size={17} /></button>}
      </div>)}</div>
      {(files.some(id => !items.some(item => item.id === id)) || folders.some(id => !items.some(item => item.id === id))) && <div className={styles.otherSelections}><strong>Selected elsewhere</strong>{files.filter(id => !items.some(item => item.id === id)).map(id => <button key={id} onClick={() => setFiles(current => current.filter(value => value !== id))}>File {id.slice(0, 12)} <X size={12} /></button>)}{folders.filter(id => !items.some(item => item.id === id)).map(id => <button key={id} onClick={() => setFolders(current => current.filter(value => value !== id))}>Folder {id.slice(0, 12)} <X size={12} /></button>)}</div>}
      {error && <p className={styles.error} role="alert">{error}</p>}
      <div className={styles.pickerFooter}><span>{files.length} files · {folders.length} folders selected</span><button className={styles.primary} disabled={busy} onClick={save}>{busy ? 'Saving…' : 'Save selection'}</button></div>
    </div>
  </div>;
}
