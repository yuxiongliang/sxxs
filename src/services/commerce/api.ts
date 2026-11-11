import { request } from '@umijs/max';
import type { ApiResponse } from '@/services/system/types';
import type {
  AddressRecord,
  CartItemRecord,
  CartSummary,
  CommissionRuleRecord,
  OrderDetail,
  OrderRecord,
  PortalOrder,
  PortalProduct,
  PortalProductDetail,
  PayoutRecord,
  ProductRecord,
  SellerLedger,
  SellerOrderRecord,
  SellerProductRecord,
  SellerProfile,
  SellerRecord,
  SettlementBatchRecord,
} from './types';

async function unwrap<T>(promise: Promise<ApiResponse<T>>): Promise<T> {
  const response = await promise;
  if (response.code !== 200) throw new Error(response.message || '请求失败');
  return response.data;
}

export async function getSellerProfile() {
  return unwrap<SellerProfile>(
    request('/api/v1/portal/seller/profile', { method: 'GET' }),
  );
}

export async function listSellerProducts() {
  return unwrap<SellerProductRecord[]>(
    request('/api/v1/portal/seller/products', { method: 'GET' }),
  );
}

export async function createSellerProduct(data: {
  name: string;
  subtitle?: string;
  price_cents: number;
  stock: number;
}) {
  return unwrap<{ id: number; name: string; status: string }>(
    request('/api/v1/portal/seller/products', { method: 'POST', data }),
  );
}

export async function shipMySellerOrder(
  id: number,
  data: { carrier: string; tracking_no: string },
) {
  return unwrap<{ id: number; status: string }>(
    request(`/api/v1/portal/seller/orders/${id}/ship`, { method: 'POST', data }),
  );
}

export async function requestSellerPayout() {
  return unwrap<{ id: number; amount_cents: number; status: string }>(
    request('/api/v1/portal/seller/payouts', { method: 'POST' }),
  );
}

export async function listSellerOrders() {
  return unwrap<SellerOrderRecord[]>(
    request('/api/v1/portal/seller/orders', { method: 'GET' }),
  );
}

export async function listPortalProducts() {
  return unwrap<PortalProduct[]>(
    request('/api/v1/portal/products', { method: 'GET' }),
  );
}

export async function listPortalOrders() {
  return unwrap<PortalOrder[]>(
    request('/api/v1/portal/orders', { method: 'GET' }),
  );
}

export async function createPortalOrder(data: {
  sku_id: number;
  quantity: number;
  receiver_name: string;
  receiver_phone: string;
  receiver_address: { detail: string };
}) {
  return unwrap<PortalOrder>(
    request('/api/v1/portal/orders', {
      method: 'POST',
      data: {
        items: [{ sku_id: data.sku_id, quantity: data.quantity }],
        receiver_name: data.receiver_name,
        receiver_phone: data.receiver_phone,
        receiver_address: data.receiver_address,
      },
    }),
  );
}

export async function mockPayPortalOrder(id: number) {
  return unwrap<{ id: number; status: string }>(
    request(`/api/v1/portal/orders/${id}/mock-pay`, { method: 'POST' }),
  );
}

export async function confirmPortalOrder(id: number) {
  return unwrap<{ id: number; status: string }>(
    request(`/api/v1/portal/orders/${id}/confirm`, { method: 'POST' }),
  );
}

export async function listAdminSellers() {
  return unwrap<SellerRecord[]>(request('/api/v1/admin/sellers', { method: 'GET' }));
}

export async function listAdminProducts() {
  return unwrap<ProductRecord[]>(request('/api/v1/admin/products', { method: 'GET' }));
}

export async function reviewSeller(id: number, data: { status: string; kyc_status: string }) {
  return unwrap<SellerRecord>(
    request(`/api/v1/admin/sellers/${id}/review`, { method: 'POST', data }),
  );
}

export async function updateAdminProduct(
  id: number,
  data: {
    name?: string;
    subtitle?: string;
    description?: string;
    status?: string;
    main_image?: string;
  },
) {
  return unwrap<ProductRecord>(
    request(`/api/v1/admin/products/${id}`, { method: 'PUT', data }),
  );
}

export async function reviewProduct(id: number, data: { status: string }) {
  return unwrap<ProductRecord>(
    request(`/api/v1/admin/products/${id}/review`, { method: 'POST', data }),
  );
}

export async function getSellerLedger(id: number) {
  return unwrap<SellerLedger>(
    request(`/api/v1/admin/sellers/${id}/ledger`, { method: 'GET' }),
  );
}

export async function createSellerPayout(id: number) {
  return unwrap<{ id: number; amount_cents: number; status: string }>(
    request(`/api/v1/admin/sellers/${id}/payouts`, { method: 'POST' }),
  );
}

export async function listAdminOrders() {
  return unwrap<OrderRecord[]>(request('/api/v1/admin/orders', { method: 'GET' }));
}

export async function getAdminOrderDetail(id: number) {
  return unwrap<OrderDetail>(
    request(`/api/v1/admin/orders/${id}`, { method: 'GET' }),
  );
}

export async function shipSellerOrder(
  id: number,
  data: { carrier: string; tracking_no: string },
) {
  return unwrap<{ id: number; status: string }>(
    request(`/api/v1/admin/seller-orders/${id}/ship`, { method: 'POST', data }),
  );
}

export async function refundSellerOrder(
  id: number,
  data: { amount_cents: number; reason?: string },
) {
  return unwrap<{ id: number; status: string }>(
    request(`/api/v1/admin/seller-orders/${id}/refund`, { method: 'POST', data }),
  );
}

export async function mockPayOrder(id: number) {
  return unwrap<{ id: number; status: string }>(
    request(`/api/v1/admin/orders/${id}/mock-pay`, { method: 'POST' }),
  );
}

export async function cancelOrder(id: number) {
  return unwrap<{ id: number; status: string }>(
    request(`/api/v1/admin/orders/${id}/cancel`, { method: 'POST' }),
  );
}

// ---------------------------------------------------------------------------
// 买家商城：商品详情 / 购物车 / 地址簿
// ---------------------------------------------------------------------------

export async function getPortalProductDetail(id: number) {
  return unwrap<PortalProductDetail>(
    request(`/api/v1/portal/products/${id}`, { method: 'GET' }),
  );
}

export async function getPortalCart() {
  return unwrap<CartSummary>(request('/api/v1/portal/cart', { method: 'GET' }));
}

export async function addCartItem(data: { sku_id: number; quantity: number }) {
  return unwrap<CartItemRecord>(
    request('/api/v1/portal/cart/items', { method: 'POST', data }),
  );
}

export async function updateCartItem(
  id: number,
  data: { quantity?: number; selected?: boolean },
) {
  return unwrap<CartItemRecord>(
    request(`/api/v1/portal/cart/items/${id}`, { method: 'PUT', data }),
  );
}

export async function deleteCartItem(id: number) {
  return unwrap<null>(
    request(`/api/v1/portal/cart/items/${id}`, { method: 'DELETE' }),
  );
}

export async function clearPortalCart() {
  return unwrap<{ removed: number }>(
    request('/api/v1/portal/cart', { method: 'DELETE' }),
  );
}

export async function checkoutCart(data: {
  receiver_name: string;
  receiver_phone: string;
  receiver_address: Record<string, string>;
  address_id?: number;
  remark?: string;
}) {
  return unwrap<PortalOrder>(
    request('/api/v1/portal/cart/checkout', { method: 'POST', data }),
  );
}

export async function listAddresses() {
  return unwrap<AddressRecord[]>(
    request('/api/v1/portal/addresses', { method: 'GET' }),
  );
}

export async function createAddress(data: Omit<AddressRecord, 'id'>) {
  return unwrap<AddressRecord>(
    request('/api/v1/portal/addresses', { method: 'POST', data }),
  );
}

export async function updateAddress(
  id: number,
  data: Partial<Omit<AddressRecord, 'id'>>,
) {
  return unwrap<AddressRecord>(
    request(`/api/v1/portal/addresses/${id}`, { method: 'PUT', data }),
  );
}

export async function setDefaultAddress(id: number) {
  return unwrap<AddressRecord>(
    request(`/api/v1/portal/addresses/${id}/default`, { method: 'POST' }),
  );
}

export async function deleteAddress(id: number) {
  return unwrap<null>(
    request(`/api/v1/portal/addresses/${id}`, { method: 'DELETE' }),
  );
}

// ---------------------------------------------------------------------------
// 财务中心：佣金规则 / 提现审核 / 结算批次
// ---------------------------------------------------------------------------

export async function listCommissionRules() {
  return unwrap<CommissionRuleRecord[]>(
    request('/api/v1/admin/commission-rules', { method: 'GET' }),
  );
}

export async function createCommissionRule(data: {
  name: string;
  rate_bps: number;
  fixed_fee_cents?: number;
  seller_id?: number | null;
  category_id?: number | null;
  priority?: number;
  status?: string;
}) {
  return unwrap<CommissionRuleRecord>(
    request('/api/v1/admin/commission-rules', { method: 'POST', data }),
  );
}

export async function updateCommissionRule(
  id: number,
  data: Partial<Omit<CommissionRuleRecord, 'id'>>,
) {
  return unwrap<CommissionRuleRecord>(
    request(`/api/v1/admin/commission-rules/${id}`, { method: 'PUT', data }),
  );
}

export async function deleteCommissionRule(id: number) {
  return unwrap<null>(
    request(`/api/v1/admin/commission-rules/${id}`, { method: 'DELETE' }),
  );
}

export async function listPayouts(status?: string) {
  return unwrap<PayoutRecord[]>(
    request('/api/v1/admin/payouts', { method: 'GET', params: { status } }),
  );
}

export async function approvePayout(id: number) {
  return unwrap<PayoutRecord>(
    request(`/api/v1/admin/payouts/${id}/approve`, { method: 'POST' }),
  );
}

export async function rejectPayout(id: number, reason = '') {
  return unwrap<PayoutRecord>(
    request(`/api/v1/admin/payouts/${id}/reject`, { method: 'POST', data: { reason } }),
  );
}

export async function payPayout(id: number) {
  return unwrap<PayoutRecord>(
    request(`/api/v1/admin/payouts/${id}/pay`, { method: 'POST' }),
  );
}

export async function listSettlementBatches() {
  return unwrap<SettlementBatchRecord[]>(
    request('/api/v1/admin/settlement-batches', { method: 'GET' }),
  );
}

export async function createSettlementBatch(data: {
  period_start: string;
  period_end: string;
  note?: string;
}) {
  return unwrap<SettlementBatchRecord>(
    request('/api/v1/admin/settlement-batches', { method: 'POST', data }),
  );
}

export async function confirmSettlementBatch(id: number) {
  return unwrap<SettlementBatchRecord>(
    request(`/api/v1/admin/settlement-batches/${id}/confirm`, { method: 'POST' }),
  );
}

export async function paySettlementBatch(id: number) {
  return unwrap<SettlementBatchRecord>(
    request(`/api/v1/admin/settlement-batches/${id}/pay`, { method: 'POST' }),
  );
}

/** 当前用户的开店状态：none / pending / active。 */
export interface SellerApplicationState {
  has_seller: boolean;
  status: string;
  seller_id?: number;
  display_name?: string;
  kyc_status?: string;
  shop?: { id: number; name: string; slug: string; status?: string } | null;
}

export async function getSellerApplication() {
  return unwrap<SellerApplicationState>(
    request('/api/v1/portal/seller/application', { method: 'GET' }),
  );
}

export async function applySeller(data: { shop_name: string; contact_phone?: string }) {
  return unwrap<SellerApplicationState>(
    request('/api/v1/portal/seller/apply', { method: 'POST', data }),
  );
}
