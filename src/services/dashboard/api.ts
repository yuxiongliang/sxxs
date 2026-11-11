import { request } from '@umijs/max';
import type { ApiResponse } from '@/services/system/types';

export interface DashboardKpi {
  gmv_today_cents: number;
  gmv_yesterday_cents: number;
  orders_today: number;
  orders_yesterday: number;
  new_buyers_today: number;
  buyers_total: number;
  pending_payment_orders: number;
  products_on_sale: number;
  products_pending_review: number;
  sellers_active: number;
  sellers_pending: number;
  payouts_pending_count: number;
  payouts_pending_cents: number;
  im_reports_open: number;
}

export interface DashboardTrendPoint {
  date: string;
  gmv_cents: number;
  orders: number;
}

export interface DashboardStatusBucket {
  status: string;
  count: number;
}

export interface DashboardTopProduct {
  product_id: number;
  name: string;
  quantity: number;
  gmv_cents: number;
}

export interface DashboardUsage {
  plan: string | null;
  plan_name: string | null;
  subscription_status: string | null;
  products_used: number;
  products_quota: number | null;
  members_used: number;
  members_quota: number | null;
  days_left: number | null;
}

export interface DashboardOverview {
  range: { days: number; start: string; end: string; timezone: string };
  kpi: DashboardKpi;
  totals: { orders: number; gmv_cents: number };
  trend: DashboardTrendPoint[];
  order_status: DashboardStatusBucket[];
  top_products: DashboardTopProduct[];
  usage: DashboardUsage;
}

async function unwrap<T>(promise: Promise<ApiResponse<T>>): Promise<T> {
  const response = await promise;
  if (response.code !== 200) throw new Error(response.message || '请求失败');
  return response.data;
}

/** 经营看板聚合数据（真实业务表，非 mock）。 */
export async function getDashboardOverview(days = 30) {
  return unwrap<DashboardOverview>(
    request('/api/v1/dashboard/overview', { method: 'GET', params: { days } }),
  );
}
