import { describe, expect, it } from 'vitest';
import {
  decodeJwtPayload,
  isTokenExpiringSoon,
  REFRESH_SKEW_SECONDS,
} from './refreshToken';

/** 构造一个只含 payload 的假 JWT（不校验签名，前端只关心 exp） */
function fakeJwt(payload: Record<string, unknown>): string {
  const b64 = (obj: Record<string, unknown>) =>
    Buffer.from(JSON.stringify(obj)).toString('base64url');
  return `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64(payload)}.sig`;
}

describe('decodeJwtPayload', () => {
  it('decodes a well-formed JWT payload', () => {
    const token = fakeJwt({ sub: '1', exp: 2000000000 });
    expect(decodeJwtPayload(token)?.sub).toBe('1');
    expect(decodeJwtPayload(token)?.exp).toBe(2000000000);
  });

  it('returns null for malformed tokens instead of throwing', () => {
    expect(decodeJwtPayload('')).toBeNull();
    expect(decodeJwtPayload('a.b')).toBeNull();
    expect(decodeJwtPayload('a.%%%.c')).toBeNull();
  });
});

describe('isTokenExpiringSoon', () => {
  const now = 1_700_000_000;

  it('treats an already expired token as expiring', () => {
    const token = fakeJwt({ exp: now - 10 });
    expect(isTokenExpiringSoon(token, now)).toBe(true);
  });

  it('refreshes ahead of expiry inside the skew window', () => {
    const token = fakeJwt({ exp: now + REFRESH_SKEW_SECONDS - 1 });
    expect(isTokenExpiringSoon(token, now)).toBe(true);
  });

  it('keeps a healthy token untouched', () => {
    const token = fakeJwt({ exp: now + 600 });
    expect(isTokenExpiringSoon(token, now)).toBe(false);
  });

  it('treats an unparseable token as expiring (fail-safe)', () => {
    expect(isTokenExpiringSoon('not-a-jwt', now)).toBe(true);
  });
});
