import type { ChatSession, DriveConfig, DriveFile, DriveItem, EmailPreview, GmailConfig, JiraConfig, JiraProject, MemoryFact, Message, NotionConfig, NotionItem, Project, SourceConnection, SourceType, User } from './types';

const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080';

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) {
    super(message);
  }
}

export function createApi(getToken: () => Promise<string | null>) {
  async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const token = await getToken();
    const response = await fetch(`${baseUrl}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const error = body?.error;
      throw new ApiError(error?.code ?? 'server_error', error?.message ?? 'Something went wrong', response.status);
    }
    return response.json() as Promise<T>;
  }

  return {
    startDemo: () => request<{ token: string; project_id: string; questions_left: number }>('/auth/demo', { method: 'POST', body: '{}' }),
    me: () => request<User>('/auth/me'),
    projects: () => request<Project[]>('/projects'),
    project: (id: string) => request<Project>(`/projects/${id}`),
    createProject: (name: string, description?: string) =>
      request<Project>('/projects', { method: 'POST', body: JSON.stringify({ name, description }) }),
    updateProject: (id: string, changes: { name?: string; description?: string | null }) =>
      request<Project>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }),
    deleteProject: (id: string) => request<{ ok: true }>(`/projects/${id}`, { method: 'DELETE' }),
    sources: (id: string) => request<SourceConnection[]>(`/projects/${id}/sources`),
    connectSource: (id: string, type: SourceType) => request<{ redirect_url: string }>(`/projects/${id}/sources/${type}/connect`, { method: 'POST' }),
    disconnectSource: (id: string, type: SourceType) => request<{ ok: true }>(`/projects/${id}/sources/${type}`, { method: 'DELETE' }),
    saveSourceConfig: (id: string, type: SourceType, config: DriveConfig | GmailConfig | JiraConfig | NotionConfig) => request<SourceConnection>(`/projects/${id}/sources/${type}/config`, { method: 'PUT', body: JSON.stringify(config) }),
    browseDrive: (id: string, folderId?: string) => request<{ path: { id: string; name: string }[]; items: DriveItem[] }>(`/projects/${id}/sources/drive/browse${folderId ? `?folder_id=${encodeURIComponent(folderId)}` : ''}`),
    driveFiles: (id: string) => request<DriveFile[]>(`/projects/${id}/sources/drive/files`),
    syncDrive: (id: string) => request<{ started: true }>(`/projects/${id}/sources/drive/sync`, { method: 'POST' }),
    removeDriveFile: (id: string, fileId: string) => request<{ ok: true }>(`/projects/${id}/sources/drive/files/${encodeURIComponent(fileId)}`, { method: 'DELETE' }),
    gmailLabels: (id: string) => request<string[]>(`/projects/${id}/sources/gmail/labels`),
    previewGmail: (id: string, config: GmailConfig) => request<EmailPreview[]>(`/projects/${id}/sources/gmail/preview`, { method: 'POST', body: JSON.stringify(config) }),
    jiraProjects: (id: string) => request<JiraProject[]>(`/projects/${id}/sources/jira/projects`),
    searchNotion: (id: string, q: string) => request<NotionItem[]>(`/projects/${id}/sources/notion/search?q=${encodeURIComponent(q)}`),
    chats: (projectId: string) => request<ChatSession[]>(`/projects/${projectId}/chats`),
    createChat: (projectId: string) => request<ChatSession>(`/projects/${projectId}/chats`, { method: 'POST', body: '{}' }),
    renameChat: (chatId: string, title: string) => request<ChatSession>(`/chats/${chatId}`, { method: 'PATCH', body: JSON.stringify({ title }) }),
    deleteChat: (chatId: string) => request<{ ok: true }>(`/chats/${chatId}`, { method: 'DELETE' }),
    messages: (chatId: string) => request<Message[]>(`/chats/${chatId}/messages`),
    memory: (projectId: string) => request<MemoryFact[]>(`/projects/${projectId}/memory`),
    deleteMemory: (projectId: string, factId: string) => request<{ ok: true }>(`/projects/${projectId}/memory/${factId}`, { method: 'DELETE' }),
    approveMemory: (chatId: string, approvalId: string, decision: 'approved' | 'rejected', facts: string[]) =>
      request<Message>(`/chats/${chatId}/memory-approval`, { method: 'POST', body: JSON.stringify({ approval_id: approvalId, decision, facts }) }),
    streamMessage: async (chatId: string, content: string): Promise<Response> => {
      const token = await getToken();
      const response = await fetch(`${baseUrl}/chats/${chatId}/messages/stream`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ content }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new ApiError(body?.error?.code ?? 'server_error', body?.error?.message ?? 'Could not send message', response.status);
      }
      return response;
    },
  };
}

export type Api = ReturnType<typeof createApi>;
