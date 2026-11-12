/** 平台端枚举值的中文文案。
 *
 * 后端返回的是机器值（active/pending/paid…），直接渲染会把英文露给运营。
 * 统一在这里做映射：**取不到就原样返回**，避免因为新增枚举值而显示空白。
 */

export const PLAN_STATUS: Record<string, string> = {
  active: '在售',
  archived: '已下架',
};

export const INVOICE_STATUS: Record<string, string> = {
  pending: '待支付',
  paid: '已支付',
  void: '已作废',
};

export const SUBSCRIPTION_STATUS: Record<string, string> = {
  trialing: '试用中',
  active: '正常',
  past_due: '已逾期',
  cancelled: '已取消',
};

export const TENANT_STATUS: Record<string, string> = {
  active: '正常',
  suspended: '已停用',
  closed: '已关闭',
};

export const DOMAIN_STATUS: Record<string, string> = {
  active: '已生效',
  pending: '待验证',
  failed: '验证失败',
  disabled: '已停用',
};

export const USER_STATUS: Record<string, string> = {
  active: '正常',
  disabled: '已停用',
};

export const USER_ROLE: Record<string, string> = {
  platform_admin: '平台管理员',
  platform_support: '平台客服',
  tenant_owner: '租户所有者',
  tenant_admin: '租户管理员',
  operator: '运营',
  viewer: '只读',
  customer: '买家',
  seller_owner: '卖家',
  seller_staff: '卖家员工',
  admin: '超级管理员',
};

export const NOTIFICATION_CHANNEL: Record<string, string> = {
  inbox: '站内信',
  sms: '短信',
  email: '邮件',
};

export const NOTIFICATION_SCOPE: Record<string, string> = {
  platform: '平台 → 租户',
  tenant_buyer: '租户 → 买家',
  tenant_seller: '租户 → 卖家',
};

export const REVIEW_STATUS: Record<string, string> = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已驳回',
  failed: '审核失败',
  skipped: '无需审核',
};

export const VISIBILITY: Record<string, string> = {
  public: '公开',
  private: '私有',
  tenant: '租户内',
  internal: '内部',
};

export const PERIOD_LABEL: Record<string, string> = {
  monthly: '按月',
  yearly: '按年',
  lifetime: '永久买断',
  custom: '自定义档期',
};

export const PAYMENT_SOURCE: Record<string, string> = {
  inherit: '跟随平台',
  override: '租户自定义',
  forced_inherit: '平台锁定',
};

/** 取不到映射就原样返回，空值显示破折号 */
export const labelOf = (
  dict: Record<string, string>,
  value?: string | null,
): string => {
  if (value === null || value === undefined || value === '') return '—';
  return dict[value] ?? value;
};
