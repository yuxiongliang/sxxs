/**
 * 访问令牌存储。
 *
 * 两个前端用**不同的 key**：
 *   - 租户控制台：antd_pro_access_token
 *   - 平台管理端：sxxs_platform_access_token
 * 即便将来两者部署在同一站点下（sessionStorage 共享），也不会互相覆盖。
 */

export const ACCESS_TOKEN_KEY = 'antd_pro_access_token';
export const PLATFORM_ACCESS_TOKEN_KEY = 'sxxs_platform_access_token';

export interface TokenStorage {
  get: () => string | null;
  set: (token: string) => void;
  clear: () => void;
}

export function createTokenStorage(key: string): TokenStorage {
  return {
    get: () => sessionStorage.getItem(key),
    set: (token: string) => sessionStorage.setItem(key, token),
    clear: () => sessionStorage.removeItem(key),
  };
}
