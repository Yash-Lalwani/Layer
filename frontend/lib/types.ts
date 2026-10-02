export type SourceType = 'drive' | 'gmail' | 'jira' | 'notion';

export interface User {
  id: string;
  name: string;
  email: string | null;
  is_guest: boolean;
  questions_left: number | null;
  created_at: string;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  is_demo: boolean;
  connected_sources: SourceType[];
  created_at: string;
  updated_at: string;
}

export interface DriveConfig { file_ids: string[]; folder_ids: string[] }
export interface GmailConfig { labels: string[]; senders: string[]; keywords: string[]; query: string }
export interface JiraConfig { project_key: string; jql: string | null }
export interface NotionConfig { page_ids: string[]; database_ids: string[] }
export interface SourceConnection {
  type: SourceType;
  status: 'not_connected' | 'connected' | 'needs_reauth' | 'error';
  account_label: string | null;
  config: DriveConfig | GmailConfig | JiraConfig | NotionConfig | null;
  last_synced_at: string | null;
}
export interface DriveItem { id: string; name: string; kind: 'folder' | 'file'; mime_type: string | null; modified_time: string | null }
export interface DriveFile { id: string; name: string; mime_type: string; web_url: string; status: 'pending' | 'ingesting' | 'ingested' | 'unchanged' | 'failed'; error: string | null; modified_time: string | null; ingested_at: string | null }
export interface EmailPreview { id: string; subject: string; from: string; date: string; snippet: string }
export interface JiraProject { key: string; name: string }
export interface NotionItem { id: string; title: string; kind: 'page' | 'database'; url: string }

export interface ChatSession { id: string; project_id: string; title: string; created_at: string; updated_at: string }
export interface Source { number: number; type: SourceType | 'web'; title: string; snippet: string; url: string | null; date: string | null }
export interface Statement { text: string; citation_numbers: number[] }
export interface PlanStep { sub_question: string; source: SourceType; status: 'answered' | 'no_evidence' }
export interface Verification { checked: number; supported: number; removed: number; succeeded: boolean }
export interface AnswerPayload {
  status: 'completed' | 'blocked'; blocked_reason: string | null; text: string;
  statements: Statement[]; sources: Source[]; plan: PlanStep[];
  verification: Verification; insufficient_context: boolean; pending_memory: { approval_id: string; facts: string[] } | null;
  metadata: { latency_ms: number };
}
export interface Message {
  id: string; chat_id: string; role: 'user' | 'assistant'; content: string;
  answer: AnswerPayload | null; memory_decision: 'approved' | 'rejected' | 'skipped' | null; created_at: string;
}
export interface MemoryFact { id: string; text: string; source_chat_id: string | null; created_at: string }
export type StreamEvent =
  | { type: 'step'; data: { step: string; source?: SourceType; label: string } }
  | { type: 'token'; data: { text: string } }
  | { type: 'final'; data: { user_message: Message; assistant_message: Message; questions_left: number | null } }
  | { type: 'error'; data: { code: string; message: string } };
