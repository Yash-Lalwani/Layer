export const guestCookie = 'layer_demo_token';
const guestProjectCookie = 'layer_demo_project';

function cookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const entry = document.cookie.split('; ').find(item => item.startsWith(`${name}=`));
  return entry ? decodeURIComponent(entry.split('=').slice(1).join('=')) : null;
}

export function getGuestToken(): string | null {
  return cookie(guestCookie);
}

export function isGuestProjectPage(): boolean {
  const projectId = cookie(guestProjectCookie);
  return Boolean(projectId && window.location.pathname.startsWith(`/workspace/${projectId}`));
}

export function saveGuestToken(token: string, projectId: string): void {
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = `${guestCookie}=${encodeURIComponent(token)}; Path=/; SameSite=Lax; Max-Age=86400${secure}`;
  document.cookie = `${guestProjectCookie}=${encodeURIComponent(projectId)}; Path=/; SameSite=Lax; Max-Age=86400${secure}`;
}

export function clearGuestToken(): void {
  document.cookie = `${guestCookie}=; Path=/; SameSite=Lax; Max-Age=0`;
  document.cookie = `${guestProjectCookie}=; Path=/; SameSite=Lax; Max-Age=0`;
}
