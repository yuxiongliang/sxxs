export interface SellerRecord {
  id: number;
  display_name: string;
  seller_type: string;
  status: string;
  kyc_status: string;
}

export interface ProductRecord {
  id: number;
  seller_id: number;
  shop_id: number;
  name: string;
  subtitle?: string;
  status: string;
  main_image?: string;
}

export interface OrderRecord {
  id: number;
  order_no: string;
  buyer_id: number;
  status: string;
  payable_amount_cents: number;
}

export interface SellerOrderRecord {
  id: number;
  seller_id: number;
  status: string;
  goods_amount_cents: number;
  commission_amount_cents: number;
  payable_to_seller_cents: number;
}

export interface OrderItemRecord {
  id: number;
  product_name: string;
  sku_name: string;
  price_cents: number;
  quantity: number;
  subtotal_cents: number;
}

export interface PortalProduct {
  id: number;
  seller_id: number;
  shop_id: number;
  name: string;
  subtitle?: string;
  status: string;
  main_image?: string;
  sku?: { id: number; name: string; price_cents: number; stock: number };
}

export interface SellerProfile {
  id: number;
  display_name: string;
  status: string;
  kyc_status: string;
  shop?: { id: number; name: string; slug: string } | null;
}

export interface SellerProductRecord {
  id: number;
  name: string;
  status: string;
  price_cents: number;
  stock: number;
}

export interface SellerOrderRecord {
  id: number;
  order_id: number;
  seller_order_no: string;
  status: string;
  goods_amount_cents: number;
  commission_amount_cents: number;
  payable_to_seller_cents: number;
}

export interface PortalOrder {
  id: number;
  order_no: string;
  status: string;
  payable_amount_cents: number;
  created_at?: string;
}

export interface SellerLedgerEntry {
  id: number;
  type: string;
  amount_cents: number;
  seller_order_id?: number;
  created_at: string;
}

export interface SellerLedger {
  seller_id: number;
  balance_cents: number;
  available_cents?: number;
  pending_cents?: number;
  hold_days?: number;
  entries: SellerLedgerEntry[];
}

export interface OrderDetail extends OrderRecord {
  seller_orders: SellerOrderRecord[];
  items: OrderItemRecord[];
}

export interface PortalProductSku {
  id: number;
  sku_code: string;
  name: string;
  price_cents: number;
  stock: number;
  status: string;
}

export interface PortalProductDetail {
  id: number;
  name: string;
  subtitle?: string;
  description?: string;
  status: string;
  main_image?: string;
  images?: string[];
  seller_id: number;
  seller_name?: string;
  shop_id: number;
  shop_name?: string;
  skus: PortalProductSku[];
}

export interface CartItemRecord {
  id: number;
  product_id: number;
  sku_id: number;
  seller_id: number;
  quantity: number;
  selected: boolean;
  product_name: string;
  sku_name: string;
  price_cents: number;
  stock: number;
  main_image?: string;
  subtotal_cents: number;
  available: boolean;
}

export interface CartSummary {
  items: CartItemRecord[];
  selected_count: number;
  selected_amount_cents: number;
  total_count: number;
  invalid_count: number;
}

export interface AddressRecord {
  id: number;
  receiver_name: string;
  receiver_phone: string;
  province: string;
  city: string;
  district: string;
  detail: string;
  is_default: boolean;
}

export interface CommissionRuleRecord {
  id: number;
  name: string;
  category_id?: number | null;
  seller_id?: number | null;
  rate_bps: number;
  fixed_fee_cents: number;
  priority: number;
  status: string;
}

export interface PayoutRecord {
  id: number;
  seller_id: number;
  amount_cents: number;
  status: string;
  reject_reason: string;
  settlement_batch_id?: number | null;
  requested_by?: number | null;
  reviewed_by?: number | null;
  paid_at?: string | null;
}

export interface SettlementBatchRecord {
  id: number;
  batch_no: string;
  period_start: string;
  period_end: string;
  status: string;
  total_amount_cents: number;
  seller_count: number;
  payout_count: number;
  note: string;
  confirmed_at?: string | null;
  paid_at?: string | null;
}
