'use client';

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { Plus, Send, Trash2 } from 'lucide-react';
import { useApi } from '@/components/api-provider';
import { readStream } from '@/lib/stream';
import type { ChatSession, Message, Project } from '@/lib/types';
import { AnswerView } from './answer-view';
import styles from './chat.module.css';

function suggestions(project: Project): string[] {
  if (project.is_demo) return [
    'Summarize Phoenix goals, launch tasks, and blockers across the sources.',
    'What changed recently, and how does it affect the launch?',
    'What durable decision should the team remember?',
  ];
  const sources = project.connected_sources;
  if (sources.length > 1) return [
    `Summarize ${project.name} across its connected sources.`,
    'What are the current goals, tasks, and blockers?',
    'What changed most recently, and why?',
  ];
  if (sources.includes('drive')) return ['Summarize the selected project documents.', 'What are the main decisions?', 'What remains open?'];
  return ['Summarize this project.', 'What are the main goals?', 'What should I know first?'];
}

export function ChatPanel({ project, questionsLeft, onQuestionsLeft, onMemoryChanged }: { project: Project; questionsLeft: number | null; onQuestionsLeft?: (left: number) => void; onMemoryChanged?: () => void }) {
  const api = useApi();
  const [chats, setChats] = useState<ChatSession[]>([]);
  const [chatId, setChatId] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState('');
  const [pendingQuestion, setPendingQuestion] = useState('');
  const [draft, setDraft] = useState('');
  const [steps, setSteps] = useState<string[]>([]);
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    setLoading(true); setChatId(''); setMessages([]); setError('');
    api.chats(project.id).then(items => {
      if (!active) return;
      setChats(items);
      setChatId(items[0]?.id ?? '');
    }).catch(cause => active && setError(cause instanceof Error ? cause.message : 'Could not load chats'))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [api, project.id]);

  useEffect(() => {
    if (!chatId) { setMessages([]); return; }
    if (sending) return;
    let active = true;
    api.messages(chatId).then(items => active && setMessages(items))
      .catch(cause => active && setError(cause instanceof Error ? cause.message : 'Could not load messages'));
    return () => { active = false; };
  }, [api, chatId, sending]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, draft, steps]);

  async function newChat() {
    if (sending) return;
    try {
      const created = await api.createChat(project.id);
      setChats(current => [created, ...current]);
      setChatId(created.id); setMessages([]); setError('');
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not create chat'); }
  }

  async function renameChat() {
    const chat = chats.find(item => item.id === chatId);
    if (!chat || sending) return;
    const title = window.prompt('Chat title', chat.title)?.trim();
    if (!title || title === chat.title) return;
    try {
      const updated = await api.renameChat(chatId, title);
      setChats(current => current.map(item => item.id === chatId ? updated : item));
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not rename chat'); }
  }

  async function deleteChat() {
    if (!chatId || sending || !window.confirm('Delete this chat and its messages?')) return;
    try {
      await api.deleteChat(chatId);
      const remaining = chats.filter(item => item.id !== chatId);
      setChats(remaining); setChatId(remaining[0]?.id ?? ''); setMessages([]); setError('');
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not delete chat'); }
  }

  async function decideMemory(message: Message, decision: 'approved' | 'rejected', facts: string[]) {
    const pending = message.answer?.pending_memory;
    if (!pending) return;
    const updated = await api.approveMemory(message.chat_id, pending.approval_id, decision, facts);
    setMessages(current => current.map(item => item.id === updated.id ? updated : item));
    onMemoryChanged?.();
  }

  async function send(text: string) {
    const content = text.trim();
    if (!content || content.length > 2000 || sending || questionsLeft === 0) return;
    setSending(true); setError(''); setDraft(''); setSteps([]); setPendingQuestion(content); setQuestion('');
    try {
      let targetId = chatId;
      if (!targetId) {
        const created = await api.createChat(project.id);
        targetId = created.id;
        setChats(current => [created, ...current]); setChatId(targetId);
      }
      let streamError = '';
      const response = await api.streamMessage(targetId, content);
      await readStream(response, event => {
        if (event.type === 'step') setSteps(current => [...current, event.data.label]);
        if (event.type === 'token') setDraft(current => current + event.data.text);
        if (event.type === 'error') streamError = event.data.message;
        if (event.type === 'final') {
          if (event.data.questions_left !== null) onQuestionsLeft?.(event.data.questions_left);
          setMessages(current => [...current, event.data.user_message, event.data.assistant_message]);
          setChats(current => current.map(item => item.id === targetId && item.title === 'New chat' ? { ...item, title: content.slice(0, 80) } : item));
          setDraft(''); setSteps([]);
        }
      });
      if (streamError) throw new Error(streamError);
      setMessages(await api.messages(targetId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not finish the answer');
      setDraft(''); setSteps([]); setQuestion(content);
    } finally { setSending(false); setPendingQuestion(''); }
  }

  function onSubmit(event: FormEvent) { event.preventDefault(); void send(question); }
  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send(question); }
  }

  return <div className={styles.chat}>
    <header className={styles.chatHeader}>
      <select aria-label="Choose chat" value={chatId} onChange={event => setChatId(event.target.value)} disabled={sending}>
        {!chatId && <option value="">New chat</option>}
        {chats.map(chat => <option key={chat.id} value={chat.id}>{chat.title}</option>)}
      </select>
      <button onClick={newChat} disabled={sending} title="New chat"><Plus size={17} /><span>New</span></button>
      <button onClick={renameChat} disabled={!chatId || sending} title="Rename chat">Rename</button>
      <button onClick={deleteChat} disabled={!chatId || sending} title="Delete chat" aria-label="Delete chat"><Trash2 size={16} /></button>
    </header>
    <div className={styles.conversation}>
      {loading ? <p className={styles.muted}>Loading chats…</p> : messages.length === 0 && !sending ?
        <div className={styles.welcome}><div className={styles.welcomeIcon}>{project.name.slice(0, 1).toUpperCase()}</div><h1>Ask about {project.name}</h1>
          <p>Answers draw from the sources selected for this project.</p>
          <div className={styles.suggestions}>{suggestions(project).map(item => <button key={item} onClick={() => void send(item)}>{item}</button>)}</div>
        </div> : <div className={styles.messageList}>{messages.map(message =>
          <article key={message.id} className={message.role === 'user' ? styles.userMessage : styles.assistantMessage}>
            <div className={styles.messageRole}>{message.role === 'user' ? 'You' : 'Layer'}</div>
            {message.role === 'user' ? <p>{message.content}</p> : <AnswerView message={message} onMemoryDecision={decideMemory} />}
          </article>
        )}
          {pendingQuestion && <article className={styles.userMessage}><div className={styles.messageRole}>You</div><p>{pendingQuestion}</p></article>}
          {sending && <article className={styles.assistantMessage}><div className={styles.messageRole}>Layer</div>
            <div className={styles.steps}>{steps.map((step, index) => <span key={index} className={index === steps.length - 1 ? styles.activeStep : ''}>{step}</span>)}</div>
            <p className={styles.provisional}>{draft || 'Working…'}</p><small>Draft answer · Checking citations before finalizing</small>
          </article>}
          <div ref={bottomRef} />
        </div>}
    </div>
    <div className={styles.composerWrap}>
      {questionsLeft === 0 && <div className={styles.demoLimit}>You’ve used the 7 demo questions. <Link href="/register">Sign up to keep exploring.</Link></div>}
      {error && <div className={styles.error} role="alert">{error}</div>}
      <form onSubmit={onSubmit} className={styles.composer}>
        <textarea value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={onKeyDown}
          maxLength={2000} rows={2} placeholder="Ask a question about this project…" aria-label="Ask a question" disabled={sending || questionsLeft === 0} />
        <button type="submit" disabled={sending || questionsLeft === 0 || !question.trim()} aria-label="Send message"><Send size={18} /></button>
      </form>
      <div className={styles.composerHint}><span>Enter to send · Shift+Enter for a new line</span>{question.length >= 1800 && <span>{question.length}/2000</span>}</div>
    </div>
  </div>;
}
