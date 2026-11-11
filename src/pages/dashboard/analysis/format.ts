/** 经营看板的纯格式化工具（可脱离浏览器测试）。 */

const YUAN = 100;

/** 分 -> 两位小数的元字符串，带千分位。 */
export function centsToYuan(cents: number): string {
  const safe = Number.isFinite(cents) ? cents : 0;
  const yuan = safe / YUAN;
  return yuan.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** 分 -> 显示用金额（默认带 ¥）。 */
export function formatCents(cents: number, withSymbol = true): string {
  return withSymbol ? `¥${centsToYuan(cents)}` : centsToYuan(cents);
}

/**
 * 环比百分比。上一期为 0 时返回 null —— 此时「增长 100%」没有意义，
 * 前端应显示「—」而不是编一个数字。
 */
export function percentChange(
  current: number,
  previous: number,
): number | null {
  if (!Number.isFinite(current) || !Number.isFinite(previous)) return null;
  if (previous === 0) return null;
  return Math.round(((current - previous) / previous) * 1000) / 10;
}

const ORDER_STATUS_LABELS: Record<string, string> = {
  pending_payment: '待支付',
  paid: '已支付',
  processing: '处理中',
  partially_shipped: '部分发货',
  shipped: '已发货',
  completed: '已完成',
  cancelled: '已取消',
  refunded: '已退款',
  closed: '已关闭',
};

export function statusLabel(status: string): string {
  return ORDER_STATUS_LABELS[status] ?? status;
}

/** 2026-11-11 -> 11-11 */
export function shortDay(iso: string): string {
  const parts = iso.split('-');
  return parts.length === 3 ? `${parts[1]}-${parts[2]}` : iso;
}
