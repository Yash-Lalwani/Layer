'use client';

import { useState } from 'react';
import { Copy, ExternalLink } from 'lucide-react';
import { SourceIcon } from '@/components/source-icon';
import type { AnswerPayload, Message } from '@/lib/types';
import styles from './chat.module.css';

export function AnswerView({ message, onMemoryDecision }: { message: Message; onMemoryDecision?: (message: Message, decision: 'approved' | 'rejected', facts: string[]) => Promise<void> }) {
  const answer = message.answer;
  if (!answer) return <p className={styles.answerText}>{message.content}</p>;
  if (answer.status === 'blocked') return <div className={styles.blocked}>{answer.blocked_reason}</div>;

  function cite(number: number) {
    const source = answer!.sources.find(item => item.number === number);
    return <button key={number} className={styles.citation} title={`${source?.title ?? 'Source'}: ${source?.snippet ?? ''}`}
      onClick={() => document.getElementById(`source-${message.id}-${number}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })}>[{number}]</button>;
  }

  return <div className={styles.answer}>
    {answer.statements.length ? <div className={styles.answerLines}>{answer.statements.map((statement, index) =>
      <p key={index}>{statement.text} {statement.citation_numbers.map(cite)}</p>
    )}</div> : <p className={styles.answerText}>{answer.text}</p>}
    {answer.insufficient_context && <p className={styles.insufficient}>Some parts could not be answered from this project’s configured sources.</p>}
    <div className={styles.answerActions}>
      {answer.verification.succeeded && <span className={styles.verified}>
        {answer.verification.supported} of {answer.verification.checked} claims verified
        {answer.verification.removed > 0 && ` · ${answer.verification.removed} unsupported removed`}
      </span>}
      <button title="Copy answer" aria-label="Copy answer" onClick={() => navigator.clipboard.writeText(answer.text)}><Copy size={15} /></button>
    </div>
    {answer.sources.length > 0 && <div className={styles.sourceCards}>{answer.sources.map(source =>
      <article key={source.number} id={`source-${message.id}-${source.number}`} className={styles.sourceCard}>
        <div><span className={styles.sourceNumber}>{source.number}</span><SourceIcon type={source.type} /><strong>{source.title}</strong></div>
        <p>{source.snippet}</p>
        <footer><span>{source.date ? new Date(source.date).toLocaleDateString() : ''}</span>{source.url && <a href={source.url} target="_blank" rel="noopener noreferrer">Open <ExternalLink size={12} /></a>}</footer>
      </article>
    )}</div>}
    <details className={styles.how}><summary>How I answered</summary>
      <ol>{answer.plan.map((step, index) => <li key={index}><span>{step.source}</span> {step.sub_question} <em>{step.status === 'answered' ? 'Answered' : 'No evidence'}</em></li>)}</ol>
      <p>{(answer.metadata.latency_ms / 1000).toFixed(1)} seconds</p>
    </details>
    {answer.pending_memory && onMemoryDecision && <MemoryApproval message={message} onDecision={onMemoryDecision} />}
    {message.memory_decision && <p className={styles.memoryResult}>{message.memory_decision === 'approved' ? 'Saved to project memory' : message.memory_decision === 'skipped' ? 'Memory suggestion skipped' : 'Not saved to memory'}</p>}
  </div>;
}

function MemoryApproval({ message, onDecision }: { message: Message; onDecision: (message: Message, decision: 'approved' | 'rejected', facts: string[]) => Promise<void> }) {
  const [facts, setFacts] = useState(message.answer!.pending_memory!.facts);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function decide(decision: 'approved' | 'rejected') {
    setBusy(true); setError('');
    try { await onDecision(message, decision, facts); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not save decision'); }
    finally { setBusy(false); }
  }
  return <div className={styles.memoryCard}>
    <strong>Save to project memory?</strong>
    <div>{facts.map((fact, index) => editing ? <input key={index} value={fact} maxLength={500} onChange={event => setFacts(current => current.map((item, i) => i === index ? event.target.value : item))} /> : <p key={index}>{fact}</p>)}</div>
    {error && <p role="alert">{error}</p>}
    <div className={styles.memoryActions}><button disabled={busy || !facts.some(Boolean)} onClick={() => void decide('approved')}>Approve</button><button disabled={busy} onClick={() => setEditing(!editing)}>{editing ? 'Done editing' : 'Edit'}</button><button disabled={busy} onClick={() => void decide('rejected')}>Reject</button></div>
    <small>Sending a new message will skip this.</small>
  </div>;
}
