/**
 * 平台端 HTTP 层。
 *
 * 刻意不用 umi request：这里需要精确控制 401 续期（用平台专属 cookie 换新 token），
 * 而 umi request 的 errorConfig 语义会让「续期后重试」很难写清楚。
 */
import { PLATFORM_ACCESS_TOKEN_KEY, createTokenStorage } from '@shared';

export const tokens = createTokenStorage(PLATFORM_ACCESS_TOKEN_KEY);

const API_BASE = '/api/v1';

interface Envelope<T> {
  code: number;
  message: string;
  data: T;
}

async function send(path: string, init: RequestInit): Promise<Response> {
  const token = tokens.get();
  const headers = new Headers(init.headers);
  headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return fetch(`${API_BASE}${path}`, { ...init, headers, credentials: 'include' });
}

/** 用 httpOnly cookie 换新的 access token。失败返回 false。 */
export async function tryRefresh(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/platform/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) return false;
    const body = (await response.json()) as Envelope<{ access_token: string }>;
    if (body.code !== 200 || !body.data?.access_token) return false;
    tokens.set(body.data.access_token);
    return true;
  } catch {
    return false;
  }
}

export async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<T> {
  const response = await send(path, init);

  if (response.status === 401 && retry) {
    if (await tryRefresh()) return requestJson<T>(path, init, false);
    tokens.clear();
    if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
      window.location.assign(
        `/login?redirect=${encodeURIComponent(window.location.pathname)}`,
      );
    }
    throw new Error('登录已过期');
  }

  const body = (await response.json().catch(() => null)) as Envelope<T> | null;
  if (!response.ok) {
    throw new Error(body?.message ?? `请求失败（${response.status}）`);
  }
  if (!body || typeof body !== 'object' || !('code' in body)) {
    return body as unknown as T;
  }
  if (body.code !== 200) throw new Error(body.message || '请求失败');
  return body.data;
}

export const apiGet = <T>(path: string) => requestJson<T>(path, { method: 'GET' });

export const apiPost = <T>(path: string, data?: unknown) =>
  requestJson<T>(path, {
    method: 'POST',
    body: data === undefined ? undefined : JSON.stringify(data),
  });

export const apiPut = <T>(path: string, data?: unknown) =>
  requestJson<T>(path, { method: 'PUT', body: JSON.stringify(data) });
