/** 平台端业务接口。全部要求 aud=platform 的 token。 */
import { apiDelete, apiGet, apiPost, apiPut } from './http';

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
  /** 平台级业务类目（决定抽佣比例）；null = 未分类 = 不抽佣 */
  service_category: {
    id: number;
    code: string;
    name: string;
    commission_bps: number;
  } | null;
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
  service_category_id?: number | null;
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
// 通知模板（scope 三档：platform→租户 / tenant_buyer→买家 / tenant_seller→卖家）
// ---------------------------------------------------------------------------

export type NotificationTemplateScope =
  | 'platform'
  | 'tenant_buyer'
  | 'tenant_seller';

export interface NotificationTemplateRecord {
  id: number;
  scope: NotificationTemplateScope;
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

/** 可用变量（含中文释义与示例）：新增变量由后端提供，前端不写死。 */
export interface NotificationVariable {
  name: string;
  label: string;
  description: string;
  example: string;
}

export const listNotificationTemplates = (scope?: NotificationTemplateScope) =>
  apiGet<NotificationTemplateRecord[]>(
    `/platform/notification-templates${scope ? `?scope=${scope}` : ''}`,
  );

export const listNotificationVariables = () =>
  apiGet<NotificationVariable[]>('/platform/notification-templates/variables');

export const saveNotificationTemplate = (
  scope: NotificationTemplateScope,
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

// ---------------------------------------------------------------------------
// 平台审计（只含 tenant_id 为空的平台行）
// ---------------------------------------------------------------------------

export interface PlatformAuditRecord {
  id: number;
  actor_id: number | null;
  action: string;
  target_type: string;
  target_id: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  created_at: string;
}

export const listPlatformAudit = (params: {
  current?: number;
  pageSize?: number;
}) => {
  const parts: string[] = [];
  if (params.current !== undefined) parts.push('current=' + params.current);
  if (params.pageSize !== undefined) parts.push('pageSize=' + params.pageSize);
  const q = parts.join('&');
  return apiGet<{ list: PlatformAuditRecord[]; total: number }>(
    q ? '/platform/audit?' + q : '/platform/audit',
  );
};

// ---------------------------------------------------------------------------
// 租户概览（品牌 / 支付 / 域名状态）
// ---------------------------------------------------------------------------

export interface TenantOverviewRecord {
  tenant_id: number;
  name: string;
  slug: string;
  status: string;
  brand: { display_name: string; customized: boolean; has_logo: boolean };
  payment: { source: string; configured: boolean };
  domain: {
    supported: boolean;
    primary_host: string | null;
    active: number;
    pending: number;
    total: number;
  };
}

export const listTenantOverview = () =>
  apiGet<TenantOverviewRecord[]>('/platform/overview/tenants');

// ---------------------------------------------------------------------------
// 服务类目（平台级业务类目：决定租户归属与抽佣比例，不是商品类目）
// ---------------------------------------------------------------------------

export interface ServiceCategoryRecord {
  id: number;
  code: string;
  name: string;
  description: string;
  /** 抽佣比例，万分比：500 = 5% */
  commission_bps: number;
  status: 'active' | 'archived';
  sort: number;
  tenant_count?: number;
}

export const listServiceCategories = (includeArchived = false) =>
  apiGet<ServiceCategoryRecord[]>(
    `/platform/service-categories${includeArchived ? '?include_archived=true' : ''}`,
  );

export const createServiceCategory = (data: {
  code: string;
  name: string;
  description?: string;
  commission_bps: number;
  sort?: number;
}) => apiPost<ServiceCategoryRecord>('/platform/service-categories', data);

export const updateServiceCategory = (
  id: number,
  data: {
    name?: string;
    description?: string;
    commission_bps?: number;
    status?: 'active' | 'archived';
    sort?: number;
  },
) => apiPut<ServiceCategoryRecord>(`/platform/service-categories/${id}`, data);

export const assignTenantCategory = (tenantId: number, categoryId: number | null) =>
  apiPut<{ tenant_id: number; service_category_id: number | null }>(
    `/platform/tenants/${tenantId}/service-category`,
    { service_category_id: categoryId },
  );

// ---------------------------------------------------------------------------// 租户域名（B6）：自有子域创建即 active；客户自带域名要按 TXT 验证所有权
// ---------------------------------------------------------------------------

export interface TenantDomainRecord {
  id: number;
  tenant_id: number;
  host: string;
  kind: 'subdomain' | 'custom';
  status: 'pending' | 'active' | 'failed' | 'disabled';
  is_primary: boolean;
  verified_at: string | null;
  /** 自定义域名才有：让运营直接复制给客户的 TXT 记录 */
  dns_record?: { type: 'TXT'; name: string; value: string };
}

export const listTenantDomains = (tenantId: number) =>
  apiGet<TenantDomainRecord[]>(`/platform/tenants/${tenantId}/domains`);

export const createTenantDomain = (
  tenantId: number,
  data: { host: string; kind?: 'subdomain' | 'custom' },
) => apiPost<TenantDomainRecord>(`/platform/tenants/${tenantId}/domains`, data);

export const verifyTenantDomain = (tenantId: number, domainId: number) =>
  apiPost<TenantDomainRecord>(
    `/platform/tenants/${tenantId}/domains/${domainId}/verify`,
  );

export const deleteTenantDomain = (tenantId: number, domainId: number) =>
  apiDelete<null>(`/platform/tenants/${tenantId}/domains/${domainId}`);