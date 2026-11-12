/** 平台端业务接口。全部要求 aud=platform 的 token。 */
import { apiGet, apiPost, apiPut } from './http';

export interface PlatformAuthUser {
  id: number;
  username: string;
  nickname: string;
  email: string;
}

export interface PlatformSession {
  access_token: string;
  user: PlatformAuthUser;
  roles: string[];
  permissions: string[];
}

export interface PlatformMe {
  user: PlatformAuthUser;
  roles: string[];
  permissions: string[];
}

export const login = (username: string, password: string) =>
  apiPost<PlatformSession>('/platform/auth/login', { username, password });

export const platformMe = () => apiGet<PlatformMe>('/platform/auth/me');

export const logout = () => apiPost<null>('/platform/auth/logout');

// ---------------------------------------------------------------------------
// 租户 / 套餐 / 订阅 / 账单
// ---------------------------------------------------------------------------

export interface TenantRecord {
  id: number;
  name: string;
  slug: string;
  status: string;
  created_at?: string;
}

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

export const listTenants = () => apiGet<TenantRecord[]>('/platform/tenants');

export const createTenant = (data: {
  name: string;
  slug: string;
  email: string;
  nickname: string;
  password: string;
}) => apiPost<TenantRecord>('/platform/tenants', data);

export const listTenantsWithPlan = () =>
  apiGet<TenantWithPlan[]>('/platform/tenants-list');

export const updateTenant = (id: number, data: { name?: string; status?: string }) =>
  apiPut<{ id: number; name: string; status: string }>(`/platform/tenants/${id}`, data);

export const suspendTenant = (id: number, reason = '') =>
  apiPost<{ id: number; status: string }>(`/platform/tenants/${id}/suspend`, { reason });

export const resumeTenant = (id: number) =>
  apiPost<{ id: number; status: string }>(`/platform/tenants/${id}/resume`);

export const listPlans = () => apiGet<PlanRecord[]>('/platform/plans');

export const createPlan = (data: {
  code: string;
  name: string;
  price_cents: number;
  period?: string;
  trial_days?: number;
  quotas?: Record<string, number | null>;
  features?: string[];
}) => apiPost<PlanRecord>('/platform/plans', data);

export const subscribeTenant = (tenantId: number, planId: number) =>
  apiPost<SubscriptionRecord>(`/platform/tenants/${tenantId}/subscription`, {
    plan_id: planId,
  });

export const renewTenant = (tenantId: number, days?: number) =>
  apiPost<{ subscription: SubscriptionRecord; invoice: InvoiceRecord | null }>(
    `/platform/tenants/${tenantId}/renew`,
    { days },
  );

export const listInvoices = (params?: { tenant_id?: number; status?: string }) => {
  const search = new URLSearchParams();
  if (params?.tenant_id) search.set('tenant_id', String(params.tenant_id));
  if (params?.status) search.set('status', params.status);
  const query = search.toString();
  return apiGet<InvoiceRecord[]>(`/platform/invoices${query ? `?${query}` : ''}`);
};

export const payInvoice = (id: number) =>
  apiPost<InvoiceRecord>(`/platform/invoices/${id}/pay`);

export const runBillingCycle = () =>
  apiPost<{
    scanned: number;
    invoiced: number;
    renewed: number;
    cancelled: number;
    downgraded: number;
  }>('/platform/billing/run-cycle');

// ---------------------------------------------------------------------------
// 平台级配置
// ---------------------------------------------------------------------------

export interface PlatformSettingRecord {
  category: string;
  enabled: boolean;
  config: Record<string, unknown>;
  updated_at: string;
  /** 锁定后租户不可自定义 */
  policy_locked?: boolean;
  /** 配置版本，每保存一次 +1 */
  version?: number;
}

export interface PlatformSettingImpact {
  category: string;
  tenants_total: number;
  override: number;
  inherit: number;
  forced: number;
}

export const getPlatformSetting = (category: string) =>
  apiGet<PlatformSettingRecord>(`/platform/settings/${category}`);

export const savePlatformSetting = (
  category: string,
  payload: {
    enabled: boolean;
    config: Record<string, unknown>;
    policy_locked?: boolean;
  },
) => apiPut<PlatformSettingRecord>(`/platform/settings/${category}`, payload);

/** 影响面：改之前得知道会影响多少租户。 */
export const platformSettingImpact = (category: string) =>
  apiGet<PlatformSettingImpact>(`/platform/settings/${category}/impact`);

// ---------------------------------------------------------------------------
// 内容审核（平台专属：出结论 + 强制下架，不做日常管理）
// ---------------------------------------------------------------------------

export interface PlatformAttachment {
  id: number;
  name: string;
  original_name: string;
  mime_type: string;
  size: number;
  category: string;
  storage: string;
  url: string;
  uploader: string;
  uploader_role: string;
  source_module: string;
  visibility: string;
  review_status: string;
  review_kind: string;
  reject_reason?: string | null;
  admin_hidden: boolean;
  reviewed_at?: string | null;
  review_provider?: string | null;
  deleted_at?: string | null;
  created_at: string;
  tenant_id?: number | null;
  tenant_name?: string | null;
}

export interface ModerationQueueStats {
  pending: number;
  manual: number;
  failed: number;
  rejected: number;
  approved: number;
  takedown: number;
}

export interface ModerationLogEntry {
  id: number;
  provider: string;
  decision: string;
  categories: string[];
  confidence?: number | null;
  elapsed_ms: number;
  source: string;
  reviewer_id?: number | null;
  created_at: string;
}

export interface ModerationPage {
  list: PlatformAttachment[];
  total: number;
  current: number;
  pageSize: number;
}

export const moderationQueue = (params: {
  current?: number;
  pageSize?: number;
  review_status?: string;
  tenant_id?: number;
  source_role?: string;
  keyword?: string;
  only_takedown?: boolean;
}) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value));
    }
  });
  const query = search.toString();
  return apiGet<ModerationPage>(
    `/platform/moderation/queue${query ? `?${query}` : ''}`,
  );
};

export const moderationStats = () =>
  apiGet<ModerationQueueStats>('/platform/moderation/stats');

export const moderationReview = (
  id: number,
  decision: 'approved' | 'rejected',
  categories?: string[],
) =>
  apiPost<PlatformAttachment>(`/platform/moderation/${id}/review`, {
    decision,
    categories,
  });

export const moderationTakedown = (id: number) =>
  apiPost<PlatformAttachment>(`/platform/moderation/${id}/takedown`);

export const moderationRestore = (id: number) =>
  apiPost<PlatformAttachment>(`/platform/moderation/${id}/restore`);

export const moderationLogs = (id: number) =>
  apiGet<ModerationLogEntry[]>(`/platform/moderation/${id}/logs`);

/** 审核预览/下载：需要带平台 token，给 fetch 用，不能直接塞进 <img src>。 */
export const moderationDownloadUrl = (id: number) =>
  `/api/v1/platform/moderation/${id}/download`;

// ---------------------------------------------------------------------------
// 通知模板（scope 区分品牌归属：platform→租户 / tenant→买家）
// ---------------------------------------------------------------------------

export interface NotificationTemplateRecord {
  id: number;
  scope: 'platform' | 'tenant';
  code: string;
  name: string;
  channel: string;
  subject: string;
  body: string;
  variables: string[];
  enabled: boolean;
  mandatory: boolean;
  version: number;
  updated_at: string;
}

export const listNotificationTemplates = (scope?: 'platform' | 'tenant') =>
  apiGet<NotificationTemplateRecord[]>(
    `/platform/notification-templates${scope ? `?scope=${scope}` : ''}`,
  );

export const saveNotificationTemplate = (
  scope: string,
  code: string,
  payload: {
    name: string;
    channel: string;
    subject: string;
    body: string;
    enabled: boolean;
    mandatory: boolean;
  },
) =>
  apiPut<NotificationTemplateRecord>(
    `/platform/notification-templates/${scope}/${code}`,
    payload,
  );
