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
