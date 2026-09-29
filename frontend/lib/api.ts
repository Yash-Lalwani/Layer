import { clearToken, getToken } from './auth';
import type { AuthResponse, Project, User } from './types';

const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080';

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) {
    super(message);
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = path === '/auth/login' || path === '/auth/register' ? null : getToken();
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
    if (response.status === 401 && token) {
      clearToken();
      window.location.assign('/login');
    }
    throw new ApiError(error?.code ?? 'server_error', error?.message ?? 'Something went wrong', response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  register: (name: string, email: string, password: string) =>
    request<AuthResponse>('/auth/register', { method: 'POST', body: JSON.stringify({ name, email, password }) }),
  login: (email: string, password: string) =>
    request<AuthResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: () => request<User>('/auth/me'),
  projects: () => request<Project[]>('/projects'),
  project: (id: string) => request<Project>(`/projects/${id}`),
  createProject: (name: string, description?: string) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify({ name, description }) }),
  updateProject: (id: string, changes: { name?: string; description?: string | null }) =>
    request<Project>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }),
  deleteProject: (id: string) => request<{ ok: true }>(`/projects/${id}`, { method: 'DELETE' }),
};
