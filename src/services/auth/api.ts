import { request } from '@umijs/max';
import type { ApiResponse } from '@/services/system/types';

export interface AuthTenant {
  id: number;
  name: string;
  slug: string;
  status: string;
  roles: string[];
}

export interface AuthUser {
  id: number;
  username: string;
  nickname: string;
  email: string;
  avatar?: string | null;
}

export interface AuthSession {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
  tenants: AuthTenant[];
  current_tenant: AuthTenant;
  roles: string[];
  permissions: string[];
  permission_version: number;
}

export interface MeSession {
  user: AuthUser;
  tenants: AuthTenant[];
  current_tenant: AuthTenant;
  roles: string[];
  permissions: string[];
  permission_version: number;
}

async function unwrap<T>(promise: Promise<ApiResponse<T>>): Promise<T> {
  const response = await promise;
  if (response.code !== 200) throw new Error(response.message || '请求失败');
  return response.data;
}

export async function login(data: {
  username: string;
  password: string;
  tenant_id?: number;
}) {
  return unwrap<AuthSession>(
    request('/api/v1/auth/login', { method: 'POST', data }),
  );
}

export async function me() {
  return unwrap<MeSession>(request('/api/v1/auth/me', { method: 'GET' }));
}

export async function logout() {
  return unwrap<null>(request('/api/v1/auth/logout', { method: 'POST' }));
}
