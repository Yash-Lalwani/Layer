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

export interface AuthResponse {
  token: string;
  user: User;
}

