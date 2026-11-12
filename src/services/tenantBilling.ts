/**
 * 租户侧计费：只看自己的套餐与用量。
 *
 * 平台侧的租户/套餐/账单接口（/api/v1/platform/*）已迁到
 * 赛霄玄思 SaaS 管理平台（apps/platform），控制台不再调用。
 */
import { request } from '@umijs/max';
import type { ApiResponse } from '@/services/system/types';

export interface SubscriptionRecord {
  id: number;
  status: string;
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  trial_end?: string | null;
}

export interface TenantSubscriptionReport {
  tenant_id: number;
  plan?: {
    id: number;
    code: string;
    name: string;
    price_cents: number;
    period: string;
    features: string[];
  } | null;
  subscription?: SubscriptionRecord | null;
  used: Record<string, number>;
  quotas: Record<string, number | null>;
  remaining: Record<string, number | null>;
  exceeded: string[];
  days_left?: number | null;
}

async function unwrap<T>(promise: Promise<ApiResponse<T>>): Promise<T> {
  const response = await promise;
  if (response.code !== 200) throw new Error(response.message || '请求失败');
  return response.data;
}

/** 当前租户自己的套餐：控制台据此按套餐隐藏模块。 */
export async function getTenantSubscription() {
  return unwrap<TenantSubscriptionReport>(
    request('/api/v1/tenant/subscription', { method: 'GET' }),
  );
}
