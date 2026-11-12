import {
  ACCESS_TOKEN_KEY,
  createTokenStorage,
} from '../../packages/shared/src/auth/token';

const storage = createTokenStorage(ACCESS_TOKEN_KEY);

export function getAccessToken(): string | null {
  return storage.get();
}

export function setAccessToken(token: string) {
  storage.set(token);
}

export function clearAccessToken() {
  storage.clear();
}
