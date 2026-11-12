/** 租户控制台枚举值的中文文案（与平台端各留一份，两个 app 独立部署）。 */

export const PRODUCT_STATUS: Record<string, string> = {
  draft: '草稿',
  pending_review: '待审核',
  on_sale: '在售',
  off_sale: '已下架',
  rejected: '已驳回',
};

export const ORDER_STATUS: Record<string, string> = {
  pending_payment: '待支付',
  paid: '已支付',
  processing: '处理中',
  partially_shipped: '部分发货',
  shipped: '已发货',
  completed: '已完成',
  cancelled: '已取消',
  refunding: '退款中',
  refunded: '已退款',
  closed: '已关闭',
};

export const SELLER_STATUS: Record<string, string> = {
  pending: '待审核',
  active: '正常',
  suspended: '已停用',
  closed: '已关闭',
};

export const KYC_STATUS: Record<string, string> = {
  none: '未提交',
  pending: '待审核',
  approved: '已通过',
  rejected: '已驳回',
};

export const PAYOUT_STATUS: Record<string, string> = {
  pending: '待处理',
  approved: '已批准',
  rejected: '已驳回',
  paid: '已打款',
};

export const BATCH_STATUS: Record<string, string> = {
  draft: '草稿',
  confirmed: '已确认',
  paid: '已打款',
};

export const ACTIVITY_STATUS: Record<string, string> = {
  active: '启用',
  archived: '已停用',
  disabled: '已停用',
};

export const labelOf = (
  dict: Record<string, string>,
  value?: string | null,
): string => {
  if (value === null || value === undefined || value === '') return '—';
  return dict[value] ?? value;
};
