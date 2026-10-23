export type User = {
  id: string;
  email: string;
  role: 'admin' | 'member';
  active: boolean;
  theme: 'light' | 'dark';
};
export type Session = { user: User; csrf_cookie: string; expires_at: string };
export type Invitation = {
  id: string;
  created_at: string;
  expires_at: string;
  redeemed_at: string | null;
  revoked_at: string | null;
};
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}
export function cookieValue(source: string, name: string): string | undefined {
  return source
    .split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1);
}
export async function api<T>(
  path: string,
  method = 'GET',
  body?: unknown,
  session?: Session,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (method !== 'GET') {
    headers['Content-Type'] = 'application/json';
    const csrf = session && cookieValue(document.cookie, session.csrf_cookie);
    if (csrf) headers['X-CSRF-Token'] = csrf;
  }
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers,
      credentials: 'same-origin',
      body: method === 'GET' ? undefined : JSON.stringify(body ?? {}),
      signal: AbortSignal.timeout(10000),
    });
  } catch {
    throw new ApiError(0, 'Your cloud is unavailable. Please try again.');
  }
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      error?.error?.message ?? 'Request failed. Please try again.',
    );
  }
  return response.status === 204
    ? (undefined as T)
    : ((await response.json()) as T);
}
export function invitationFromHash(hash: string): string | null {
  const value = new URLSearchParams(hash.replace(/^#/, '')).get('invite');
  return value && /^[A-Za-z0-9_-]{43}$/.test(value) ? value : null;
}
