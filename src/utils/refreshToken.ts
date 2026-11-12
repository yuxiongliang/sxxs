/**
 * access token 的过期判断与静默续期。
 *
 * 为什么在「请求发出前」续期，而不是收到 401 再重放：
 *   Umi 的 requestInterceptors 支持 async，可以在拿到响应前就把 token 换新，
 *   调用方（React Query / 业务代码）完全无感知；而 401 重放需要改动错误处理
 *   链路，且并发请求同时 401 时容易打爆 refresh 接口。
 *
 * 并发去重：多个请求同时发现 token 快过期时，只发一次 refresh，
 * 其余请求 await 同一个 Promise —— 否则 refresh token 轮换会让彼此失效。
 */
import { getAccessToken, setAccessToken } from '@/utils/authToken';

export const REFRESH_PATH = '/api/v1/auth/refresh';
/** 提前多少秒续期：留出网络往返余量，避免刚好卡在过期瞬间 */
export const REFRESH_SKEW_SECONDS = 60;

export interface JwtPayload {
  exp?: number;
  iat?: number;
  [key: string]: unknown;
}

/** base64url 解码（JWT 用的就是 base64url），浏览器与 Node 都可用 */
function base64UrlDecode(input: string): string {
  const normalized = input.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
  if (typeof atob === 'function') return atob(padded);
  return Buffer.from(padded, 'base64').toString('binary');
}

/** 解析 JWT 的 payload；格式非法返回 null（绝不抛错，避免拖垮请求） */
export function decodeJwtPayload(token: string): JwtPayload | null {
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  try {
    return JSON.parse(base64UrlDecode(parts[1])) as JwtPayload;
  } catch {
    return null;
  }
}

/**
 * token 是否已过期或即将过期。
 * 无法解析 exp 时返回 true（宁可多续一次，也不要带着可疑 token 发请求）。
 */
export function isTokenExpiringSoon(
  token: string,
  nowSeconds: number = Math.floor(Date.now() / 1000),
  skewSeconds: number = REFRESH_SKEW_SECONDS,
): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== 'number') return true;
  return payload.exp - skewSeconds <= nowSeconds;
}

let inflight: Promise<string | null> | null = null;

async function requestNewToken(): Promise<string | null> {
  try {
    // 用原生 fetch 而不是 umi request：避免再次进入拦截器造成递归
    const response = await fetch(REFRESH_PATH, {
      method: 'POST',
      credentials: 'include', // refresh token 在 HttpOnly cookie 里
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) return null;
    const body = await response.json();
    const token: string | undefined = body?.data?.access_token;
    if (!token) return null;
    setAccessToken(token);
    return token;
  } catch {
    return null;
  }
}

/** 单飞去重地续期；失败返回 null 由调用方决定如何降级 */
export function refreshAccessToken(): Promise<string | null> {
  if (inflight) return inflight;
  inflight = requestNewToken().finally(() => {
    inflight = null;
  });
  return inflight;
}

/**
 * 取一个可用的 access token：快过期就先续期。
 * 续期失败时回退到原有 token（让后端明确返回 401，而不是前端假装没有 token）。
 */
export async function getFreshAccessToken(): Promise<string | null> {
  const token = getAccessToken();
  if (!token) return null;
  if (!isTokenExpiringSoon(token)) return token;
  const refreshed = await refreshAccessToken();
  return refreshed ?? token;
}
