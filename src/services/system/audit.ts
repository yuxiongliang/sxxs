import { request } from '@umijs/max';
import type { ApiResponse } from './types';

export interface AuditLogRecord {
  id: number;
  tenant_id?: number | null;
  actor_id?: number | null;
  action: string;
  target_type: string;
  target_id: string;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
  ip?: string | null;
  trace_id?: string | null;
  created_at: string;
}

export interface AuditLogQuery {
  current?: number;
  pageSize?: number;
  action?: string;
  target_type?: string;
  target_id?: string;
  actor_id?: number;
  tenant_id?: number;
}

async function unwrap<T>(promise: Promise<ApiResponse<T>>): Promise<T> {
  const response = await promise;
  if (response.code !== 200) throw new Error(response.message || '请求失败');
  return response.data;
}

export async function listAuditLogs(params: AuditLogQuery) {
  return unwrap<{ list: AuditLogRecord[]; total: number; current: number; pageSize: number }>(
    request('/api/v1/audit-logs', { method: 'GET', params }),
  );
}

export async function listAuditActions() {
  return unwrap<string[]>(request('/api/v1/audit-logs/actions', { method: 'GET' }));
}
