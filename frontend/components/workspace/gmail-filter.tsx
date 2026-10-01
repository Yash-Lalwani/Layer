'use client';

import { FormEvent, useState } from 'react';
import { X } from 'lucide-react';
import { useApi } from '@/components/api-provider';
import type { EmailPreview, GmailConfig } from '@/lib/types';
import styles from './sources.module.css';

function makeQuery(config: GmailConfig) {
  const quoted = (value: string) => value.includes(' ') ? `"${value.replaceAll('"', '').trim()}"` : value.trim();
  const anyOf = (prefix: string, values: string[]) => {
    const terms = values.filter(Boolean).map(value => `${prefix}${quoted(value)}`);
    return terms.length > 1 ? `{${terms.join(' ')}}` : (terms[0] ?? '');
  };
  return [anyOf('label:', config.labels), anyOf('from:', config.senders), ...config.keywords.map(quoted)].filter(Boolean).join(' ');
}

function Chips({ label, values, suggestions, onChange }: { label: string; values: string[]; suggestions?: string[]; onChange: (next: string[]) => void }) {
  const [draft, setDraft] = useState('');
  function add(event: FormEvent) {
    event.preventDefault();
    const value = draft.trim();
    if (value && !values.includes(value)) onChange([...values, value]);
    setDraft('');
  }
  return <div className={styles.filterField}><span>{label}</span><div className={styles.chips}>{values.map(value => <span key={value} className={styles.chip}>{value}<button aria-label={`Remove ${value}`} onClick={() => onChange(values.filter(item => item !== value))}><X size={12} /></button></span>)}</div><form onSubmit={add}><input value={draft} onChange={event => setDraft(event.target.value)} placeholder={`Add ${label.toLowerCase().slice(0, -1)}`} list={suggestions ? 'gmail-labels' : undefined} /><button type="submit">Add</button></form>{suggestions && <datalist id="gmail-labels">{suggestions.map(value => <option key={value} value={value} />)}</datalist>}</div>;
}

export function GmailFilter({ projectId, initial, onSave }: { projectId: string; initial: GmailConfig; onSave: (config: GmailConfig) => Promise<void> }) {
  const api = useApi();
  const [config, setConfig] = useState(initial);
  const [labels, setLabels] = useState<string[]>([]);
  const [results, setResults] = useState<EmailPreview[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const current = { ...config, query: makeQuery(config) };

  async function act(kind: 'labels' | 'preview' | 'save') {
    setBusy(true); setError('');
    try {
      if (kind === 'labels') setLabels(await api.gmailLabels(projectId));
      if (kind === 'preview') setResults(await api.previewGmail(projectId, current));
      if (kind === 'save') await onSave(current);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Gmail request failed'); }
    finally { setBusy(false); }
  }

  return <div className={styles.details}>
    <p className={styles.helper}>Searched live whenever you ask.</p>
    <button className={styles.textButton} disabled={busy} onClick={() => act('labels')}>Load Gmail labels</button>
    <Chips label="Labels" values={config.labels} suggestions={labels} onChange={value => setConfig({ ...config, labels: value })} />
    <Chips label="Senders" values={config.senders} onChange={value => setConfig({ ...config, senders: value })} />
    <Chips label="Keywords" values={config.keywords} onChange={value => setConfig({ ...config, keywords: value })} />
    <div className={styles.filterField}><span>Resulting query</span><code>{current.query || 'All mail'}</code></div>
    <div className={styles.actions}><button disabled={busy} onClick={() => act('preview')}>Preview 10 emails</button><button className={styles.primary} disabled={busy} onClick={() => act('save')}>Save filter</button></div>
    {error && <p className={styles.error} role="alert">{error}</p>}
    {results && <div className={styles.preview}>{results.length === 0 ? <p>No matching emails.</p> : results.map(message => <div key={message.id}><strong>{message.subject}</strong><small>{message.from} · {message.date}</small><p>{message.snippet}</p></div>)}</div>}
  </div>;
}
