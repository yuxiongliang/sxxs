import { request } from '@umijs/max';
import type {
  ApiResponse,
  RolePermissions,
  AttachmentRecord,
  AttachmentStats,
  NotificationRecord,
  NotificationStats,
  PageData,
  SettingRecord,
  SettingTestResult,
  UserRecord,
} from './types';

const API_PREFIX = process.env.API_BASE_URL || '/api/v1';

async function unwrap<T>(promise: Promise<ApiResponse<T>>): Promise<T> {
  const response = await promise;
  if (response.code !== 200) {
    throw new Error(response.message || '请求失败');
  }
  return response.data;
}

export async function listUsers(params: {
  current?: number;
  pageSize?: number;
  keyword?: string;
  role?: string;
  status?: string;
  department_id?: number;
}) {
  return unwrap<PageData<UserRecord>>(
    request(`${API_PREFIX}/users`, { method: 'GET', params }),
  );
}

export async function createUser(
  data: Partial<UserRecord> & { password: string },
) {
  return unwrap<UserRecord>(
    request(`${API_PREFIX}/users`, { method: 'POST', data }),
  );
}

export async function updateUser(
  id: number,
  data: Partial<UserRecord> & { password?: string },
) {
  return unwrap<UserRecord>(
    request(`${API_PREFIX}/users/${id}`, { method: 'PUT', data }),
  );
}

export async function deleteUser(id: number) {
  return unwrap<null>(
    request(`${API_PREFIX}/users/${id}`, { method: 'DELETE' }),
  );
}

export async function listDepartments(params?: {
  current?: number;
  pageSize?: number;
  keyword?: string;
  status?: string;
}) {
  return unwrap<PageData<import('./types').DepartmentRecord>>(
    request(`${API_PREFIX}/departments`, { method: 'GET', params }),
  );
}

export async function createDepartment(data: {
  name: string;
  code?: string;
  description?: string;
  status?: string;
  sort?: number;
}) {
  return unwrap<import('./types').DepartmentRecord>(
    request(`${API_PREFIX}/departments`, { method: 'POST', data }),
  );
}

export async function updateDepartment(
  id: number,
  data: Partial<{
    name: string;
    code: string;
    description: string;
    status: string;
    sort: number;
  }>,
) {
  return unwrap<import('./types').DepartmentRecord>(
    request(`${API_PREFIX}/departments/${id}`, { method: 'PUT', data }),
  );
}

export async function deleteDepartment(id: number) {
  return unwrap<null>(
    request(`${API_PREFIX}/departments/${id}`, { method: 'DELETE' }),
  );
}

export async function listRoles(params?: {
  current?: number;
  pageSize?: number;
  keyword?: string;
  status?: string;
}) {
  return unwrap<PageData<import('./types').RoleRecord>>(
    request(`${API_PREFIX}/roles`, { method: 'GET', params }),
  );
}

export async function createRole(data: {
  code: string;
  name: string;
  description?: string;
  status?: string;
  sort?: number;
}) {
  return unwrap<import('./types').RoleRecord>(
    request(`${API_PREFIX}/roles`, { method: 'POST', data }),
  );
}

export async function updateRole(
  id: number,
  data: Partial<{
    name: string;
    description: string;
    status: string;
    sort: number;
  }>,
) {
  return unwrap<import('./types').RoleRecord>(
    request(`${API_PREFIX}/roles/${id}`, { method: 'PUT', data }),
  );
}

export async function getRolePermissions(id: number) {
  return unwrap<RolePermissions>(
    request(`${API_PREFIX}/roles/${id}/permissions`, { method: 'GET' }),
  );
}

export async function updateRolePermissions(id: number, permissionCodes: string[]) {
  return unwrap<RolePermissions>(
    request(`${API_PREFIX}/roles/${id}/permissions`, {
      method: 'PUT',
      data: { permission_codes: permissionCodes },
    }),
  );
}

export async function deleteRole(id: number) {
  return unwrap<null>(
    request(`${API_PREFIX}/roles/${id}`, { method: 'DELETE' }),
  );
}

export async function resetUserPassword(id: number) {
  return unwrap<{ password: string }>(
    request(`${API_PREFIX}/users/${id}/reset-password`, { method: 'POST' }),
  );
}

export async function getSetting(category: string) {
  return unwrap<SettingRecord>(
    request(`${API_PREFIX}/settings/${category}`, { method: 'GET' }),
  );
}

/**
 * 保存租户设置。
 *
 * `config` 不传表示**只切换来源**（跟随系统/自定义），后端会保留原有配置；
 * 否则「跟随系统」时提交的是平台脱敏值（******），会把自己的配置毁掉。
 */
export async function saveSetting(
  category: string,
  data: {
    source?: 'inherit' | 'override';
    enabled: boolean;
    config?: Record<string, unknown>;
  },
) {
  return unwrap<SettingRecord>(
    request(`${API_PREFIX}/settings/${category}`, { method: 'PUT', data }),
  );
}

export async function testSetting(
  category: string,
  config?: Record<string, unknown>,
) {
  return unwrap<SettingTestResult>(
    request(`${API_PREFIX}/settings/${category}/test`, {
      method: 'POST',
      data: config ? { config } : {},
    }),
  );
}

export async function listAttachments(params: {
  current?: number;
  pageSize?: number;
  category?: string;
  keyword?: string;
  source_role?: string;
  review_status?: string;
  recycle?: boolean;
}) {
  return unwrap<PageData<AttachmentRecord>>(
    request(`${API_PREFIX}/attachments`, { method: 'GET', params }),
  );
}

export async function getAttachmentStats() {
  return unwrap<AttachmentStats>(
    request(`${API_PREFIX}/attachments/stats`, { method: 'GET' }),
  );
}

export async function uploadAttachment(file: File, sourceModule = 'manual') {
  const form = new FormData();
  form.append('file', file);
  form.append('source_module', sourceModule);
  return unwrap<AttachmentRecord>(
    request(`${API_PREFIX}/attachments/upload`, {
      method: 'POST',
      data: form,
    }),
  );
}

export async function deleteAttachment(id: number) {
  return unwrap<null>(
    request(`${API_PREFIX}/attachments/${id}`, { method: 'DELETE' }),
  );
}

export async function restoreAttachment(id: number) {
  return unwrap<AttachmentRecord>(
    request(`${API_PREFIX}/attachments/${id}/restore`, { method: 'POST' }),
  );
}

export async function listNotifications(params: {
  current?: number;
  pageSize?: number;
  channel?: string;
  status?: string;
}) {
  return unwrap<PageData<NotificationRecord>>(
    request(`${API_PREFIX}/notifications`, { method: 'GET', params }),
  );
}

export async function getNotificationStats() {
  return unwrap<NotificationStats>(
    request(`${API_PREFIX}/notifications/stats`, { method: 'GET' }),
  );
}

export async function sendNotification(data: {
  title: string;
  channel: string;
  template?: string;
  audience?: string;
  content?: string;
  scheduled_at?: string;
}) {
  return unwrap<NotificationRecord>(
    request(`${API_PREFIX}/notifications/send`, { method: 'POST', data }),
  );
}

export async function retryNotification(id: number) {
  return unwrap<NotificationRecord>(
    request(`${API_PREFIX}/notifications/${id}/retry`, { method: 'POST' }),
  );
}

export interface TenantBrandRecord {
  tenant_id: number;
  slug: string;
  name: string;
  display_name: string;
  logo_url?: string | null;
  favicon_url?: string | null;
  theme_color?: string | null;
}

export async function getTenantBrand() {
  return unwrap<TenantBrandRecord>(
    request(`${API_PREFIX}/tenant/brand`, { method: 'GET' }),
  );
}

export async function saveTenantBrand(data: {
  display_name?: string;
  logo_url?: string;
  favicon_url?: string;
  theme_color?: string;
}) {
  return unwrap<TenantBrandRecord>(
    request(`${API_PREFIX}/tenant/brand`, { method: 'PUT', data }),
  );
}
