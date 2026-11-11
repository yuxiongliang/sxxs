import { request } from '@umijs/max';
import type { ApiResponse } from '@/services/system/types';

export interface TenantRecord {
  id: number;
  name: string;
  slug: string;
  status: string;
  created_at?: string;
}

async function unwrap<T>(promise: Promise<ApiResponse<T>>): Promise<T> {
  const response = await promise;
  if (response.code !== 200) throw new Error(response.message || '请求失败');
  return response.data;
}

export async function listTenants() {
  return unwrap<TenantRecord[]>(request('/api/v1/platform/tenants', { method: 'GET' }));
}

export async function createTenant(data: {
  name: string;
  slug: string;
  email: string;
  nickname: string;
  password: string;
}) {
  return unwrap<TenantRecord>(
    request('/api/v1/platform/tenants', { method: 'POST', data }),
  );
}
// ---------------------------------------------------------------------------
// SaaS 计费：套餐 / 订阅 / 用量 / 账单 / 租户生命周期
// ---------------------------------------------------------------------------

export interface PlanRecord {
  id: number;
  code: string;
  name: string;
  description: string;
  price_cents: number;
  period: string;
  trial_days: number;
  quotas?: Record<string, number | null> | null;
  features?: string[] | null;
  status: string;
  sort: number;
}

export interface SubscriptionRecord {
  id: number;
  status: string;
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  trial_end?: string | null;
}

export interface TenantWithPlan extends TenantRecord {
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
  exceeded: string[];
  days_left?: number | null;
}

/** GET /api/v1/tenant/subscription — the caller's own tenant, plan and usage. */
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

export interface InvoiceRecord {
  id: number;
  tenant_id: number;
  invoice_no: string;
  amount_cents: number;
  currency: string;
  status: string;
  period_start: string;
  period_end: string;
  paid_at?: string | null;
  note: string;
}

export async function listTenantsWithPlan() {
  return unwrap<TenantWithPlan[]>(
    request('/api/v1/platform/tenants-list', { method: 'GET' }),
  );
}

export async function updateTenant(id: number, data: { name?: string; status?: string }) {
  return unwrap<{ id: number; name: string; status: string }>(
    request(`/api/v1/platform/tenants/${id}`, { method: 'PUT', data }),
  );
}

export async function suspendTenant(id: number, reason = '') {
  return unwrap<{ id: number; status: string }>(
    request(`/api/v1/platform/tenants/${id}/suspend`, { method: 'POST', data: { reason } }),
  );
}

export async function resumeTenant(id: number) {
  return unwrap<{ id: number; status: string }>(
    request(`/api/v1/platform/tenants/${id}/resume`, { method: 'POST' }),
  );
}

export async function listPlans() {
  return unwrap<PlanRecord[]>(request('/api/v1/platform/plans', { method: 'GET' }));
}

export async function createPlan(data: {
  code: string;
  name: string;
  price_cents: number;
  period?: string;
  trial_days?: number;
  quotas?: Record<string, number | null>;
  features?: string[];
}) {
  return unwrap<PlanRecord>(request('/api/v1/platform/plans', { method: 'POST', data }));
}

export async function subscribeTenant(tenantId: number, planId: number) {
  return unwrap<SubscriptionRecord>(
    request(`/api/v1/platform/tenants/${tenantId}/subscription`, {
      method: 'POST',
      data: { plan_id: planId },
    }),
  );
}

export async function renewTenant(tenantId: number, days?: number) {
  return unwrap<{ subscription: SubscriptionRecord; invoice: InvoiceRecord | null }>(
    request(`/api/v1/platform/tenants/${tenantId}/renew`, {
      method: 'POST',
      data: { days },
    }),
  );
}

export async function listInvoices(params?: { tenant_id?: number; status?: string }) {
  return unwrap<InvoiceRecord[]>(
    request('/api/v1/platform/invoices', { method: 'GET', params }),
  );
}

export async function payInvoice(id: number) {
  return unwrap<InvoiceRecord>(
    request(`/api/v1/platform/invoices/${id}/pay`, { method: 'POST' }),
  );
}

/**
 * The signed-in user's own plan. The console uses `plan.features` to hide
 * modules the tenant has not bought.
 */
export async function getTenantSubscription() {
  return unwrap<TenantSubscriptionReport>(
    request('/api/v1/tenant/subscription', { method: 'GET' }),
  );
}

/** Platform-side: run the recurring billing cycle immediately. */
export async function runBillingCycle() {
  return unwrap<{
    scanned: number;
    invoiced: number;
    renewed: number;
    cancelled: number;
    downgraded: number;
  }>(request('/api/v1/platform/billing/run-cycle', { method: 'POST' }));
}
