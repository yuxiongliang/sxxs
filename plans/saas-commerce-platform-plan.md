# C 端 SaaS C2C 商城 / 多卖家交易平台完整实现方案

> 关联权限设计：[RBAC 菜单权限高可用方案](./rbac-menu-permission-design.md)
> 适用阶段：从当前单租户管理后台演进为 C 端多租户 SaaS C2C 多卖家交易平台

## 1. 结论先行

- **后端同一套领域服务 + 同一个 PostgreSQL**，不做两套订单库。
- **前端分离**：Admin Web（Ant Design Pro 6）+ Portal Web（Next.js，C 端商城/H5）。
- **一个 tenant = 一个 C2C 交易市场（marketplace）**，内部有多个 seller/shop；同一套代码服务多个 tenant。
- **四级结构：平台 -> tenant（交易市场）-> seller（卖家/店铺）-> buyer（买家）**。
- **全局用户身份 + 租户成员关系**：同一个人可以属于多个 tenant；在同一 tenant 内可以同时是 buyer，也可以申请成为 seller。
- 注册用户是 C 端买家，角色 `customer`，数据范围 `self`，只能看自己的订单、地址、支付记录。
- 卖家是 `seller_owner` / `seller_staff`，数据范围 `seller`，只能看自己店铺的商品、订单、结算。
- 运营人员是 tenant 市场运营员工，角色 `operator`，数据范围 `department` 或 `tenant`，由 tenant 配置。
- 所有业务表强制 `tenant_id`，应用层过滤 + PostgreSQL RLS 双重隔离。
- 高可用靠无状态 FastAPI 多副本、Redis 权限缓存、PostgreSQL 主从、对象存储、异步任务队列和 CDN。

## 2. 目标与非目标

### 目标

1. C 端买家注册、登录、浏览多个卖家的商品、加购、下单、支付、查看自己的订单。
2. 多租户 SaaS：每个 tenant 是独立 C2C 市场，拥有自己的卖家、商品、订单、运营员工、支付配置、域名/市场装修。
3. 卖家入驻：买家可申请成为 seller，创建店铺、上架商品、处理自己店铺的订单、查看结算。
4. 管理端：平台管理员、租户市场管理员、市场运营按权限看到不同菜单和操作。
5. C2C 交易闭环：一次结算可拆成多个 seller_order；平台统一收款，按佣金规则结算给卖家。
6. 订单、库存、支付、退款、佣金、结算数据一致，支持支付回调和对账。
7. 高可用：单副本故障不影响整体；Redis 故障时权限回退数据库；订单数据绝不跨租户/跨卖家/跨买家泄漏。
8. C2C IM 即时聊天：买家与卖家按商品/订单发起会话，支持文字/图片/订单卡片、未读数、已读回执、离线补拉、屏蔽举报。
9. 可长期维护：模块边界清晰、OpenAPI 契约、Alembic 迁移、自动化测试、可观测性。

### 非目标（第一版不做）

- 跨 tenant 的联邦市场/联盟——tenant 之间数据和交易隔离。
- 直播带货、内容社区——后续可接第三方。
- 音视频通话、端到端加密（E2E）——第一版做服务端可审核的图文 IM，E2E 与平台审核/纠纷取证冲突，后续单独评估。
- 复杂促销引擎（满减、阶梯价、拼团、秒杀）——先做基础优惠券/价格，后续扩展。
- 自建支付网关——使用支付宝/微信官方服务端 SDK 及其 marketplace/分账能力。
- 多区域多活——先做同区域多副本 + 主从 + 备份，跨区域多活作为后续阶段。
- 自研搜索引擎——先用 PostgreSQL 全文检索，规模上来再接 Meilisearch/OpenSearch。

## 3. 总体架构

```text
                    ┌────────────────────────────┐
                    │ CDN / WAF / TLS            │
                    └─────────────┬──────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
   Admin Web                Portal Web                Webhooks
   Ant Design Pro 6         Next.js App Router        Alipay / WeChat
   admin.example.com        {tenant}.example.com      /api/v1/webhooks/*
          │                       │                       │
          └───────────────────────┼───────────────────────┘
                                  │
                         API Gateway / Nginx
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
   FastAPI 多副本（无状态）   WebSocket Gateway       Centrifugo（可选）
   /api/v1/*                 /ws/im                  > 1 万长连接时启用
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
   /api/v1/platform/*       /api/v1/admin/*         /api/v1/portal/*
   平台运营                  市场管理端              买家 / 卖家中心
          └───────────────────────┼───────────────────────┘
                                  │
             ┌────────────────────┼────────────────────┐
             │                    │                    │
        PostgreSQL 18.6       Redis 8 / Valkey      OSS / MinIO
        主库 + 只读副本        权限/会话/缓存/队列     商品图/附件/导出
                                  │
                             Arq / Worker
                       订单超时、支付回调、通知、导出
```

### 服务边界

| 服务 | 职责 |
|---|---|
| `api` | FastAPI：认证、租户、RBAC、卖家/商品、订单、支付、佣金/结算、通知、附件 |
| `realtime` | WebSocket IM：会话、消息、在线状态、已读回执、多实例 Redis 广播 |
| `worker` | Arq/Celery：订单超时关闭、库存释放、支付回调重试、通知、导出、结算、离线消息推送 |
| `admin` | Pro 6：平台/市场管理端（卖家审核、商品审核、订单、财务） |
| `portal` | Next.js：C 端市场、商品、购物车、结算、我的订单 + 卖家中心 |
| `postgres` | 业务事实源 |
| `redis` | 权限缓存、refresh token、限流、队列 |
| `oss` | 商品图、附件、导出文件 |

## 4. 仓库与代码结构

推荐最终 monorepo：

```text
repo/
├── apps/
│   ├── admin/                 # 现有 Ant Design Pro 6 迁移到这里
│   └── portal/                # Next.js App Router C 端
├── services/
│   ├── api/                   # FastAPI
│   ├── realtime/              # IM WebSocket 网关（也可合并在 api 内，规模大时拆出）
│   └── worker/                # Arq worker
├── packages/
│   ├── api-client/            # OpenAPI 生成的 TS client
│   └── design-tokens/         # 品牌色/间距（可选）
├── infra/
│   ├── docker-compose.dev.yml
│   ├── k8s/
│   └── nginx/
└── docs/
```

### 迁移策略

当前 `ant-design-pro` 和 `backend` 可以先保留：

1. 第一阶段：当前目录继续做 Admin，新增 `portal/` 和 `backend` 扩展。
2. 第二阶段：把 `backend` 抽成 `services/api`，把 Pro 抽成 `apps/admin`。
3. 第三阶段：引入 `packages/api-client`，Admin/Portal 共用生成的 API 类型。

不要在第一阶段就大搬迁，避免影响现有功能；但新代码按最终边界写。

## 5. 多租户模型

### 5.1 租户

```text
tenants
- id (uuid)
- name
- slug (unique, 用于子域名)
- status: trial/active/suspended/closed
- plan_id
- owner_user_id
- created_at / updated_at
```

- 每个 tenant 是一个 C2C 交易市场，不是一个商家。
- tenant 内可以有多个 seller/shop；seller 是独立经营者，买家可以在同一市场内跨店购买。
- 租户访问方式：`{slug}.example.com`（推荐）或 `example.com/t/{slug}`。
- Admin 登录后可切换有权限的 tenant；Portal 按域名解析 tenant。
- 平台管理员可以跨 tenant；租户管理员只能看自己的 tenant；seller 只能看自己的 shop。

### 5.2 全局用户 + 租户成员

```text
users
- id (uuid)
- email (unique)
- phone
- password_hash
- nickname
- avatar
- status
- created_at

tenant_members
- id
- tenant_id
- user_id
- status: invited/active/disabled
- joined_at
- unique(tenant_id, user_id)
```

同一个 C 端用户可以在多个 tenant 注册；全局身份唯一，成员关系按 tenant 隔离。买家可以申请成为 seller。

### 5.3 卖家 / 店铺（C2C 核心）

```text
sellers
- id (uuid)
- tenant_id
- owner_user_id
- seller_type: individual/business
- status: pending/active/suspended/closed
- kyc_status: none/pending/approved/rejected
- display_name, contact_phone
- created_at / updated_at

shops
- id (uuid)
- tenant_id, seller_id
- name, slug (unique per tenant)
- logo, banner, description
- status: draft/active/suspended
- rating, sales_count
- created_at / updated_at

seller_members
- id, tenant_id, seller_id, user_id
- role: owner/staff
- status: active/disabled
- unique(tenant_id, seller_id, user_id)
```

- 一个 seller 可以有一个或多个 shop（第一版建议 1 seller = 1 shop，表结构保留扩展）。
- buyer 申请成为 seller 后，需要 KYC/审核；通过后创建 shop。
- seller 只能操作自己的 `seller_id` 数据；不能跨 seller 查询。
- tenant 运营可以审核 seller、审核商品、处理纠纷，但不直接改卖家库存/订单金额。

### 5.4 租户隔离

每张业务表必须有：

```text
tenant_id UUID NOT NULL
```

包括：sellers、shops、seller_members、products、product_skus、orders、seller_orders、order_items、payments、refunds、payouts、settlements、commission_rules、attachments、notifications、settings、departments、roles、audit_logs。

- 所有查询必须带 `tenant_id`。
- 复合索引以 `tenant_id` 开头，例如 `(tenant_id, status, created_at)`。
- PostgreSQL RLS：每个请求事务执行 `SET LOCAL app.tenant_id = :tenant_id`；策略 `tenant_id = current_setting('app.tenant_id')::uuid`。
- 迁移/后台任务使用独立 DB role 绕过 RLS，并记录审计。
- 对象存储 key：`tenants/{tenant_id}/...`。
- Redis key：`t:{tenant_id}:...`。
- 所有跨租户访问测试必须纳入 CI。

### 5.5 租户解析

1. Portal：从 Host 解析 `slug`，查 tenant；只允许 `active/trial`。
2. Admin：JWT 里有 `tenant_id`；切换 tenant 时重新签发 token 或调用 `/auth/switch-tenant`。
3. API：不信任前端单独传的 `X-Tenant-ID`；必须与 JWT membership 校验。
4. 平台管理员：`platform_admin` 角色，可指定 tenant，但每次操作写审计。

## 6. 认证与权限

### 6.1 身份与 token

- 全局用户表 `users`；密码 argon2。
- Access token：10-15 分钟，JWT，claims：`sub`、`tenant_id`、`audience`（admin/portal）、`roles`、`permission_version`。
- Refresh token：7 天，HttpOnly + Secure + SameSite Cookie，轮换 + 复用检测。
- Admin 与 Portal 使用不同 audience，不能互相调用。
- Admin 强制 MFA（TOTP/短信）；Portal 支持邮箱/手机验证码。

### 6.2 角色

平台级：

- `platform_admin`：平台运营，跨租户。
- `platform_support`：只读客服。

租户级（市场运营）：

- `tenant_owner`：租户市场所有者，全部权限。
- `tenant_admin`：租户市场管理员，除账单/所有权外全部。
- `operator`：市场运营，卖家审核、商品审核、订单/售后/纠纷。
- `viewer`：只读。
- `customer`：C 端买家，仅自己的数据。
- `seller_owner`：C2C 卖家所有者，仅自己店铺的数据。
- `seller_staff`：卖家员工，按卖家内部权限。

### 6.3 权限码

```text
platform:tenant:read       platform:tenant:manage
platform:plan:manage       platform:audit:read

tenant:read                tenant:manage
department:read            department:manage
role:read                  role:manage
user:read                  user:write
seller:apply               seller:read
seller:manage              seller:kyc
product:read               product:manage
product:moderate
order:read:self            order:read:seller
order:read:tenant          order:read:all
order:create               order:manage
order:refund               order:export
payment:read               payment:manage
payout:read                payout:manage
commission:read            commission:manage
dispute:read               dispute:manage
review:read                review:moderate
im:conversation:read       im:message:send
im:moderate                im:support
attachment:read            attachment:upload
attachment:delete          notification:read
notification:send          setting:payment
setting:sms                setting:email
setting:storage            audit:read
```

### 6.4 数据范围

`role.data_scope`：

- `self`：买家只能看 `buyer_id = current_user.id` 的订单/地址/支付。
- `seller`：卖家只能看 `seller_id = current_seller.id` 的商品/订单/结算。
- `department`：只能看本部门/子部门数据。
- `tenant`：本租户市场全部数据（市场运营）。
- `platform`：跨租户（仅平台角色）。

规则：

- `customer` 固定 `self`，只能调用 portal buyer API。
- `seller_owner` / `seller_staff` 固定 `seller`，只能调用 portal seller API。
- `operator` 默认 `tenant`（市场运营需要看全市场订单）；如果按部门分工可设 `department`。
- `tenant_admin` / `tenant_owner` 为 `tenant`。
- `platform_admin` 为 `platform`。
- 绝不接受前端传 `user_id` / `seller_id` 作为数据范围依据；seller_id 必须从 seller membership 解析。

### 6.5 权限校验链

```text
JWT 验签 -> 解析 tenant/user/audience
  -> 校验 tenant membership/status
  -> 如果是 seller API：解析当前 seller_id（seller_members）
  -> 校验权限码（Redis/DB）
  -> service 层 data_scope 过滤（self/seller/tenant/platform）
  -> DAO 强制 tenant_id + buyer_id/seller_id 条件
  -> 返回数据
```

## 7. 核心数据模型

### 7.1 商品

```text
categories
- id, tenant_id, parent_id, name, slug, sort, status

products
- id, tenant_id, seller_id, shop_id, category_id
- name, subtitle, description
- status: draft/pending_review/on_sale/off_sale/rejected
- main_image, images(jsonb), tags(jsonb)
- created_by, created_at, updated_at

product_skus
- id, tenant_id, seller_id, product_id, sku_code, name
- price_cents, market_price_cents, cost_cents
- stock, locked_stock, status
- specs(jsonb)

inventory_logs
- id, tenant_id, seller_id, sku_id, change, reason, order_id, created_at
```

- 金额统一用整数分 `*_cents`，不用 float。
- SKU 是库存和价格的最小单位。
- 商品必须属于某个 seller/shop；市场运营可以审核/下架，但不能替卖家改库存。
- 商品图片走附件/OSS，不存 base64。

### 7.2 订单

```text
orders（买家一次结算的父订单）
- id, tenant_id, order_no (unique per tenant), buyer_id
- status: pending_payment/paid/partially_shipped/completed/
          cancelled/refunding/refunded/closed
- total_amount_cents, discount_amount_cents, payable_amount_cents
- receiver_name, receiver_phone, receiver_address(jsonb)
- remark, channel: portal
- paid_at, completed_at, cancelled_at
- created_at, updated_at

seller_orders（按卖家拆单）
- id, tenant_id, order_id, seller_id, shop_id
- seller_order_no (unique per tenant)
- status: pending_payment/paid/processing/shipped/completed/
          cancelled/refunding/refunded/closed
- goods_amount_cents, commission_amount_cents, payable_to_seller_cents
- shipped_at, completed_at
- created_at, updated_at

order_items
- id, tenant_id, order_id, seller_order_id, seller_id
- product_id, sku_id, product_name, sku_name, image
- price_cents, quantity, subtotal_cents

payments
- id, tenant_id, order_id, provider: alipay/wechat
- provider_trade_no, amount_cents, status
- raw_payload(jsonb), paid_at

refunds
- id, tenant_id, order_id, seller_order_id, payment_id
- amount_cents, reason, status

shipments
- id, tenant_id, seller_order_id, carrier, tracking_no, status, shipped_at

commission_rules
- id, tenant_id, category_id (nullable), seller_id (nullable)
- rate_bps（万分比）, fixed_fee_cents, priority, effective_from/to

payouts
- id, tenant_id, seller_id, period_start, period_end
- amount_cents, status: pending/processing/paid/failed
- provider_batch_no, paid_at

ledger_entries
- id, tenant_id, seller_id, order_id, seller_order_id
- type: sale/commission/refund/payout/adjustment
- amount_cents（正负）, balance_after_cents
- idempotency_key, created_at

settlements（对账批次）
- id, tenant_id, seller_id, period_start, period_end
- gross_amount_cents, commission_cents, refund_cents, net_amount_cents
- status, created_at
```

- 买家一次下单可以包含多个 seller 的商品；父订单统一支付，`seller_orders` 按卖家拆单履约。
- 退款按 `seller_order` 维度处理，避免一个卖家退款影响其他卖家。
- 平台统一收款，按佣金规则计算 `commission_amount_cents`，卖家可结算金额进入 `ledger_entries`。
- 所有资金变动写 ledger，不能只改余额字段。

### 7.3 购物车 / 地址 / 优惠

```text
carts / cart_items
- tenant_id, user_id, sku_id, quantity

user_addresses
- tenant_id, user_id, receiver, phone, province/city/district, detail, is_default

coupons / coupon_redemptions（可后置）
- tenant_id, code, type, value, min_amount, starts_at, ends_at, usage_limit
```

### 7.4 SaaS 计费

```text
plans
- id, code, name, price_cents, billing_cycle, features(jsonb), quotas(jsonb)

subscriptions
- id, tenant_id, plan_id, status, trial_ends_at, current_period_start/end

invoices
- id, tenant_id, subscription_id, amount_cents, status, paid_at

usage_records
- id, tenant_id, metric, quantity, recorded_at
```

### 7.5 审计

```text
audit_logs
- id, tenant_id, actor_id, actor_type, action
- target_type, target_id, before(jsonb), after(jsonb)
- ip, user_agent, trace_id, created_at
```

### 7.6 IM 即时聊天

```text
conversations
- id, tenant_id
- type: buyer_seller / buyer_support / order
- buyer_id, seller_id (nullable), shop_id (nullable)
- order_id (nullable), product_id (nullable)
- last_message_id, last_message_at
- buyer_unread_count, seller_unread_count
- status: active/closed/blocked
- unique(tenant_id, buyer_id, seller_id, order_id)（按业务定义）

conversation_members
- id, tenant_id, conversation_id, user_id
- role: buyer/seller/support
- last_read_seq, muted, joined_at

messages
- id, tenant_id, conversation_id, sender_id
- client_msg_id (unique per conversation，幂等)
- seq (per conversation 单调递增)
- type: text/image/order/product/system
- content (text), payload(jsonb)
- status: sent/delivered/read/deleted/moderated
- created_at, edited_at

message_receipts
- id, tenant_id, message_id, user_id, read_at

user_presence
- tenant_id, user_id, online, last_seen_at（Redis 为主，DB 可选）

user_blocks
- tenant_id, user_id, blocked_user_id, reason, created_at

im_reports
- id, tenant_id, conversation_id, message_id
- reporter_id, reason, status, handled_by, handled_at

im_attachments
- id, tenant_id, message_id, attachment_id, type
```

- `seq` 用会话级单调序号保证消息顺序；`client_msg_id` 保证客户端重试幂等。
- 消息正文存 PostgreSQL，图片/文件存 OSS，消息只存 attachment 引用。
- 会话按 `(tenant_id, buyer_id, seller_id)` 或 `(tenant_id, buyer_id, seller_id, order_id)` 建唯一约束，按业务选择；建议买家-卖家一个长期会话，订单作为系统消息卡片。
- 每个会话的未读数可以放在 conversations 冗余字段，读消息后更新；高并发时用 Redis 计数 + 定期落库。

## 8. API 设计

### 8.1 命名空间

```text
/api/v1/auth/*           register/login/refresh/logout/me/switch-tenant
/api/v1/platform/*       平台管理员：tenant/plan/subscription/audit
/api/v1/admin/*          租户市场管理端：sellers/products/orders/roles/settings/...
/api/v1/portal/*         买家：storefront/products/cart/orders/addresses/payments
/api/v1/portal/seller/*  卖家中心：shop/products/seller-orders/settlements
/api/v1/im/*             IM 会话、消息、已读、举报、WS ticket
/ws/im                   WebSocket 长连接（ticket 鉴权）
/api/v1/webhooks/*       支付宝/微信回调（验签 + 幂等）
```

### 8.2 关键接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/register` | C 端注册，创建全局用户 + tenant_members(customer) |
| POST | `/auth/login` | 登录，返回 access token + refresh cookie |
| GET | `/auth/me` | 用户、租户、角色、权限、permission_version |
| POST | `/auth/switch-tenant` | Admin 切换租户，重新签发 token |
| GET | `/portal/products` | 当前 tenant 上架商品列表（可跨卖家） |
| GET | `/portal/products/{id}` | 商品详情（含 seller/shop 信息） |
| GET/POST | `/portal/cart` | 买家购物车 |
| POST | `/portal/orders` | 下单（服务端重算价格/库存，按 seller 拆单） |
| GET | `/portal/orders` | **只返回当前买家订单** |
| GET | `/portal/orders/{id}` | 校验 `order.buyer_id == current_user.id` |
| POST | `/portal/orders/{id}/pay` | 创建支付单，返回支付宝/微信支付参数 |
| POST | `/portal/seller/apply` | 买家申请成为卖家 |
| GET/POST | `/portal/seller/products` | 卖家商品管理 |
| GET | `/portal/seller/orders` | **只返回当前卖家 seller_orders** |
| POST | `/portal/seller/orders/{id}/ship` | 卖家发货 |
| GET | `/portal/seller/settlements` | 卖家结算/账单 |
| POST | `/im/conversations` | 买家/卖家创建或获取会话 |
| GET | `/im/conversations` | 当前用户的会话列表（买家/卖家隔离） |
| GET | `/im/conversations/{id}/messages` | 按 seq 拉历史消息 |
| POST | `/im/conversations/{id}/messages` | 发送消息（client_msg_id 幂等） |
| POST | `/im/conversations/{id}/read` | 已读回执 |
| POST | `/im/ws-ticket` | 换取一次性 WebSocket ticket |
| GET | `/admin/im/conversations` | 运营/客服查看会话（需 im:moderate） |
| POST | `/admin/im/messages/{id}/moderate` | 下架/删除违规消息 |
| GET | `/admin/sellers` | 市场运营审核/管理卖家 |
| GET | `/admin/products` | 市场商品审核/管理 |
| POST | `/admin/products/{id}/review` | 商品审核通过/驳回 |
| GET | `/admin/orders` | 市场订单列表（按 data_scope） |
| POST | `/admin/orders/{id}/refund` | 市场退款 |
| GET | `/admin/disputes` | 纠纷/售后 |
| GET | `/admin/payouts` | 卖家结算批次 |
| GET | `/admin/roles` | 角色列表 |
| PUT | `/admin/roles/{id}/permissions` | 设置角色权限 |
| POST | `/webhooks/alipay` | 支付宝回调 |
| POST | `/webhooks/wechat` | 微信支付回调 |

### 8.3 契约

- 统一响应 `{code,message,data,trace_id}`。
- 列表 `{list,total,current,pageSize}`。
- 所有写接口支持 `Idempotency-Key`（下单、支付、退款、发货）。
- 金额用整数分。
- 时间 ISO 8601 UTC。
- OpenAPI 3.1 生成 `packages/api-client`，Admin/Portal 共用类型。

## 9. Admin Web（Pro 6）

### 菜单

```text
Dashboard
卖家管理
  - 卖家入驻审核
  - 店铺管理
  - 卖家违规/封禁
商品管理
  - 商品审核
  - 分类管理
  - 品牌/属性
订单管理
  - 市场订单
  - 卖家订单
  - 退款/售后
  - 纠纷处理
  - 发货监控
用户管理
  - 买家列表
  - 部门管理
  - 角色管理
财务
  - 佣金规则
  - 卖家结算
  - 对账/发票
客服中心
  - 会话监管
  - 举报/违规消息
  - 客服工单
内容/附件
触达通知
系统设置
  - 支付设置
  - 短信设置
  - 邮件系统
  - 存储设置
租户设置（tenant_admin）
```

### 关键点

- 顶部增加 tenant 切换器（仅平台管理员/多租户成员可见）。
- `access.ts` 使用权限码；路由 `access` 控制菜单。
- `PageTabs` 在切换 tenant 时清空或按 tenant 隔离。
- 卖家管理：入驻审核、KYC、店铺状态、违规记录。
- 商品审核：卖家提交商品 -> pending_review -> 运营通过/驳回。
- 订单列表列：订单号、买家、卖家/店铺、金额、佣金、状态、支付方式、创建时间、操作。
- 商品编辑：SKU 表格、库存、图片上传（复用 `AttachmentUpload`）。
- 财务：佣金规则、卖家结算批次、退款/对账。
- 客服中心：会话监管、举报处理、违规消息下架；运营默认只能看本 tenant，查看买家 PII 需额外审计权限。
- 角色管理增加权限树；用户管理支持多角色。
- 所有金额展示用 `Intl.NumberFormat('zh-CN', {style:'currency',currency:'CNY'})`。

## 10. Portal Web（Next.js）

### 技术选型

- Next.js App Router（当前稳定版），React 19，TypeScript。
- Tailwind CSS + Ant Design Mobile（或团队偏好的 C 端组件库）。
- 服务端渲染商品列表/详情，利于 SEO；用户中心/订单页客户端渲染。
- 独立部署到 `{tenant}.example.com` 或 `shop.example.com`。

### 页面

```text
/
/products
/products/[slug]
/shops/[slug]
/cart
/checkout
/orders
/orders/[id]
/account
/account/addresses
/login
/register
/payment/result
/messages
/messages/[id]
/seller/apply
/seller
/seller/products
/seller/orders
/seller/messages
/seller/settlements
/seller/settings
```

### 多租户

- Next.js middleware 解析 Host 的 tenant slug。
- 服务端请求带 `X-Tenant-Slug` 到 API；API 再校验 tenant 状态。
- 不同 tenant 可配置 logo、主题色、banner、支付方式。
- 静态资源按 tenant 前缀缓存；HTML 可按 tenant 做 ISR。

### 下单流程

```text
商品详情 -> 加入购物车（可跨卖家） -> 结算页
  -> 服务端校验价格/库存/优惠
  -> 创建父订单 orders（pending_payment）
  -> 按卖家拆 seller_orders + 锁定各 SKU 库存
  -> 创建支付单（平台统一收款） -> 跳转支付宝/微信
  -> 支付回调验签 -> 更新 payment/orders/seller_orders
  -> 确认库存 -> 各卖家发货 -> 买家确认/自动确认
  -> 佣金入账 -> 结算批次 -> 卖家提现
```

### 订单可见性

- 买家订单 API 只使用 `current_user.id`，不接收 `buyer_id` 参数。
- 买家订单详情先按 `(tenant_id, id)` 查，再判断 `order.buyer_id == current_user.id`；不满足返回 404/403。
- 卖家订单 API 只使用 `current_seller.id`，不接收 `seller_id` 参数；只能查自己的 `seller_orders`。
- 市场运营按 `data_scope=tenant` 查本 tenant 全部订单；平台管理员跨 tenant 受平台权限限制。
- 列表默认按 `created_at desc`；分页 cursor 或 page/pageSize。
- 不在 CDN 缓存订单响应；设置 `Cache-Control: private, no-store`。

## 11. 订单状态机与库存

### 状态机

```text
pending_payment -> paid -> processing -> shipped -> completed
       |               |
       v               v
    cancelled       refunding -> refunded
       |
       v
     closed（超时未支付）
```

规则：

- 父订单负责支付状态；`seller_orders` 负责履约状态。
- 只有 `pending_payment -> paid` 由支付回调触发。
- `paid -> processing` 可由卖家/运营确认或自动。
- 每个 `seller_order` 独立发货；父订单在全部 seller_order 发货后进入 completed。
- 退款按 `seller_order` 维度走 `refunds`，不能直接改订单金额。
- 状态变更使用事务 + 行锁/乐观锁 `version`。
- 部分退款/部分发货必须支持，父订单状态用聚合计算。

### 库存

- 下单时 `UPDATE product_skus SET stock = stock - :qty, locked_stock = locked_stock + :qty WHERE id=:id AND stock >= :qty`；受影响行数为 0 则库存不足。
- 支付成功：`locked_stock -= qty`；取消/超时：`stock += qty, locked_stock -= qty`。
- 库存流水写 `inventory_logs`；支持对账。
- 秒杀/高并发后续引入 Redis 预扣 + 异步落库；第一版数据库原子更新足够。

## 12. 支付与对账

- 支付宝/微信官方服务端 SDK；平台统一收款，密钥存 KMS/Vault，按 tenant/平台加密保存。
- 优先使用支付宝/微信的 marketplace/分账产品；如果 provider 不支持分账，则平台先收款，再按结算周期打款给卖家。
- 支付回调：验签 -> 幂等（provider_trade_no 唯一）-> 事务更新 payment/orders/seller_orders -> 写 ledger -> 发通知。
- 佣金规则按 category/seller 优先级计算；`commission_amount_cents` 与 `payable_to_seller_cents` 写入 seller_order。
- 结算：T+7 生成 settlements/payouts，卖家可提现；退款从对应 seller_order 的待结算/余额扣回。
- 回调失败重试 + 死信队列；每日对账任务拉取平台账单与 seller_orders 核对。
- 退款走原支付渠道；退款回调同样验签/幂等。
- 不在前端保存商户私钥；前端只拿 prepay 参数/二维码。

## 13. SaaS 计费

SaaS 有两层计费，必须分开：

1. **平台 -> tenant（市场）**：SaaS 订阅费。
   - `plans`：基础版/专业版/旗舰版；功能开关 + 配额（卖家数、商品数、员工数、订单数、GMV、存储）。
   - `subscriptions`：trial -> active -> past_due -> suspended -> cancelled。
   - `usage_records`：订单数、GMV、存储、短信条数；定时聚合。
   - 超额策略：软限制提醒/硬限制阻断，按 plan 配置。
   - 账单支付走支付宝/微信；发票信息存 tenant。
   - 平台管理员可手动延期/补偿/暂停。

2. **tenant -> seller（市场向卖家）**：交易佣金/服务费。
   - `commission_rules`：按 category/seller 配置佣金比例或固定费。
   - `settlements` / `payouts`：按结算周期把货款扣除佣金后结算给卖家。
   - `ledger_entries`：每一笔 sale/commission/refund/payout 都记流水，支持对账。
   - 是否向卖家收订阅费/保证金/提现手续费，作为 tenant 可配置项。

平台如果也要从 GMV 抽成，需要单独 `platform_take_rate`，不要和 tenant 给卖家的佣金混在一个字段里。

## 14. 高可用与部署

### 14.1 拓扑

```text
CDN/WAF
  ├─ Admin static (S3/OSS + CDN)
  ├─ Portal Next.js (Node/Edge runtime, 多副本)
  └─ API Gateway/Nginx
       ├─ FastAPI x N（K8s HPA / ECS）
       └─ WebSocket Gateway x N（IM，支持 Upgrade）
            ├─ PostgreSQL 主库 + 只读副本（PITR）
            ├─ Redis Sentinel/Cluster（权限/会话/队列）
            ├─ OSS/MinIO（附件/图片）
            └─ Worker x N（Arq）
```

### 14.2 关键策略

- API 无状态；JWT 自校验；refresh token 存 Redis。
- 权限缓存：Redis `perm:tenant:{tenant_id}:user:{user_id}:v{version}`；TTL 5-15 分钟；角色变更 `INCR version` + Pub/Sub。
- Redis 故障：回源 PostgreSQL，fail closed；PostgreSQL 故障：受保护接口 503。
- 订单列表/详情禁止 CDN 缓存；商品列表可 CDN/ISR。
- 数据库连接池按副本数配置；`pool_pre_ping`；慢查询监控。
- 异步任务：订单超时关闭、库存释放、支付回调重试、通知、导出、结算、对账。
- 结算/支付事件使用 Outbox + 幂等消费者；ledger_entries 加唯一 `idempotency_key`，避免重复入账。
- 限流：按 IP、user、tenant、seller、接口维度；登录/注册/下单/支付回调/IM 发送重点限流。
- IM：WebSocket 连接数按实例限流；Redis Pub/Sub 广播；Redis 故障时客户端降级轮询。
- 健康检查：`/health` liveness，`/ready` DB/Redis readiness。
- 零停机迁移：Alembic expand/contract；先加列/表，再双写/回填，最后切读。
- 备份：PostgreSQL PITR + 每日全量；OSS 版本化；Redis 持久化；每季度恢复演练。

### 14.3 可观测性

- OpenTelemetry trace：请求 -> DB -> Redis -> 支付回调。
- Prometheus + Grafana：QPS、延迟、错误率、订单量、支付成功率、库存锁定。
- Loki/ELK：结构化日志，带 `trace_id/tenant_id/user_id`。
- Sentry：Admin/Portal 前端错误。
- 审计日志：权限变更、订单改价、退款、跨租户操作。

## 15. 安全与合规

- 密码 argon2；admin MFA；登录限流/锁定。
- JWT access 短期 + refresh 轮换；Cookie HttpOnly/Secure/SameSite；CSRF 防护。
- 多租户隔离测试：A 租户 token 不能读 B 租户任何数据。
- C2C 卖家隔离测试：seller A token 不能读 seller B 的商品/订单/结算。
- 买家隔离测试：buyer A 不能读 buyer B 的订单/地址/支付。
- 卖家只能看到履约所需的买家信息，列表默认脱敏手机号/地址。
- 对象存储私有 Bucket + presigned URL；上传 MIME/大小/病毒扫描。
- 支付密钥 KMS/Vault 加密；日志脱敏；PII 加密/最小化。
- 订单/支付回调幂等；防重放（nonce/timestamp/signature）。
- 内容安全：商品图片/文本审核（可后置）。
- 数据导出/删除：tenant 注销流程、保留期、合规审计。

## 16. 分阶段实施计划

### Phase 0：架构底座（1-2 周）

- 确定 tenant 模型、全局用户 + membership。
- 加 `tenant_id` 到现有表；创建默认 tenant 迁移现有数据。
- 建立 Alembic、OpenAPI client、CI、环境配置。

### Phase 1：认证 / RBAC / 租户（3-4 周）

- `users/tenant_members/roles/permissions/role_permissions/member_roles`。
- `/auth/*`、`/auth/me`、`switch-tenant`、JWT/refresh。
- `require_permission`、data_scope、RLS、审计。
- Admin 接入 access.ts、路由 access、菜单过滤。

### Phase 2：卖家 / 商品 / 市场后台（4-6 周）

- sellers/shops/seller_members、KYC/入驻审核。
- categories/products/skus/inventory；商品 pending_review 审核流。
- Admin 卖家管理、商品审核、SKU/库存/图片。
- orders/order_items/payments/refunds 基础表。

### Phase 3：Portal 商城 + 卖家中心（4-6 周）

- Next.js Portal：市场首页、商品列表/详情、店铺页、购物车、结算。
- 注册/登录、地址、我的订单、支付结果页。
- 卖家中心：申请入驻、商品管理、卖家订单、结算。
- 租户主题/域名/SEO。

### Phase 4：支付 / 拆单 / 佣金 / 履约（4-6 周）

- 支付宝/微信支付、回调、对账、退款。
- 一次结算按 seller 拆 seller_orders；库存锁定/释放、订单超时关闭。
- 卖家发货、买家确认收货、佣金计算、ledger、settlement/payout。
- IM：会话表、消息 seq、WebSocket ticket、Redis Pub/Sub、已读/未读、离线补拉、举报/审核。
- 通知（短信/邮件/站内信/Web Push）。

### Phase 5：SaaS 计费与市场运营（3-4 周）

- plans/subscriptions/invoices/usage（平台 -> tenant）。
- 平台管理员后台、租户开通/暂停/续费。
- tenant -> seller 佣金规则、结算批次、提现/对账。
- 配额与功能开关。

### Phase 6：高可用与规模化（持续）

- Redis 权限缓存/版本化、Pub/Sub。
- 多副本、只读副本、队列、监控告警、压测、灾备演练。

## 17. 测试策略

- 后端：pytest + pytest-asyncio；service/DAO 单元测试；API 集成测试；租户/卖家/买家隔离矩阵测试。
- 前端 Admin：Vitest + Playwright；权限菜单/按钮/路由 403。
- Portal：Playwright E2E：注册 -> 浏览 -> 加购 -> 下单 -> 支付沙箱 -> 我的订单。
- 卖家中心 E2E：申请入驻 -> 上架商品 -> 接单 -> 发货 -> 查看结算。
- C2C 拆分测试：跨卖家购物车 -> 一个父订单 -> 多个 seller_orders -> 部分退款/部分发货。
- 支付：沙箱 + 回调重放/幂等测试 + 对账测试。
- IM：WebSocket 多实例广播、断线重连、last_seq 补拉、client_msg_id 幂等、已读/未读、屏蔽/举报。
- 并发：k6/Locust 压测下单/库存/IM；验证不超卖、消息不丢不乱序。
- 故障：停 Redis/停副本/DB 只读切换演练；IM 在 Redis 故障时降级轮询。

## 18. 验收标准

1. 租户 A 的买家只能看到租户 A 的商品和自己的订单；访问租户 B 数据返回 404/403。
2. 买家 A 不能看到买家 B 的订单；买家不能调用卖家/管理接口。
3. 卖家 A 只能看到自己 shop 的商品、seller_orders、结算；访问卖家 B 数据返回 404/403。
4. 运营人员只能看到授权菜单；直接调管理接口返回 403。
5. 平台管理员可以跨租户，但所有操作有审计。
6. 下单价格/库存由服务端计算；一次结算跨多个卖家时正确拆 seller_orders。
7. 支付回调重复投递不会重复发货/重复加库存/重复记 ledger。
8. 佣金、退款、结算、payout 的 ledger 余额可对账。
9. Redis 故障时权限回源 DB，接口不 fail open。
10. 单 FastAPI 副本故障不影响下单/查询。
11. 买家/卖家只能看到自己的 IM 会话；跨买家/跨卖家/跨租户返回 404/403。
12. IM 多实例广播正常；Redis 故障时轮询补拉，消息不丢。
13. 重复 client_msg_id 不产生重复消息；断线重连按 seq 补齐。
14. 违规消息下架后普通用户不可见，运营审计可见。
15. Admin/Portal 独立发布，互不影响。

## 19. 关键取舍与风险

- **共享数据库 vs 每租户独立库**：第一版共享库 + `tenant_id` + RLS，成本低；超大 tenant 或合规要求再拆库。
- **静态路由 vs 动态菜单**：第一版静态路由 + 权限码，稳定；完全动态菜单后续加 `componentRegistry`。
- **Portal 独立前端**：多一个部署单元，但安全/体验/发布隔离收益更大。
- **支付/库存**：第一版数据库原子扣减足够；秒杀场景再上 Redis 预扣。
- **C2C 信任与合规**：卖家 KYC、商品审核、纠纷/退款、禁售品、卖家保证金/提现风控需要单独设计，不能只做技术闭环。
- **IM 长连接**：WebSocket 连接数、跨实例广播、弱网重连和消息顺序是主要复杂度；第一版 FastAPI + Redis Pub/Sub，规模上来再拆 Centrifugo。
- **IM 审核**：C2C 私聊容易出现站外引流/欺诈，必须做敏感词、举报、违规下架和审计；不做审核的 IM 会变成风控漏洞。
- **资金合规**：平台代收代付/分账涉及支付机构合规和结算资质，优先使用支付宝/微信 marketplace/分账产品，必要时接持牌机构。
- **多区域多活**：第一版同区域多副本 + PITR；跨区域多活成本高，后置。

## 20. 已确认前提

1. 一个 tenant = 一个 C2C 交易市场（marketplace），内部有多个 seller/shop；不是单商户店铺。
2. 买家在同一 tenant 内可以跨店购买；一次结算按卖家拆成多个 seller_orders。
3. 平台统一收款，tenant 收佣金后结算给卖家；平台可另收 SaaS 订阅费。
4. C 端用户注册按 tenant 市场注册；同一邮箱可在多个 tenant 成为会员。
5. 支付先接支付宝/微信；海外支付后续扩展。
6. 第一版共享 PostgreSQL，通过 tenant_id + seller_id 隔离；不为每个 tenant/seller 独立数据库。
7. IM 第一版只做图文/订单卡片/系统消息，不做音视频通话和端到端加密；消息保存在 PostgreSQL，图片/文件在 OSS。
8. IM 第一版按“买家-卖家长期会话”设计，订单作为系统消息卡片；如业务要求按订单隔离，改为 `(tenant_id,buyer_id,seller_id,order_id)` 唯一键。

> 当前已确认：tenant 是 C2C marketplace，不是单商户。按 seller/shop/seller_order/commission/payout 模型执行。

## 21. IM 即时聊天（C2C 买卖家沟通）

### 21.1 目标

- 买家在商品详情/订单详情发起与卖家的会话。
- 卖家在卖家中心查看自己店铺的会话并回复。
- 支持文字、图片、订单卡片、商品卡片、系统消息。
- 支持未读数、已读回执、离线消息补拉、消息重试幂等。
- 支持屏蔽、举报、运营审核/下架违规消息。
- 多租户、多卖家、多买家严格隔离。

### 21.2 会话模型

建议第一版：**一个买家 + 一个卖家在一个 tenant 内一个长期会话**，订单/商品作为系统消息卡片进入会话；如果业务要求按订单隔离，可把唯一键改成 `(tenant_id, buyer_id, seller_id, order_id)`。

```text
conversations
- tenant_id, buyer_id, seller_id, shop_id
- last_message_id, last_message_at
- buyer_unread_count, seller_unread_count
- status: active/closed/blocked
```

权限：

- 买家：只能看 `buyer_id = current_user.id` 的会话。
- 卖家：只能看 `seller_id = current_seller.id` 的会话。
- 市场运营：`im:moderate` 可查看本 tenant 会话用于纠纷/审核；查看敏感信息写审计。
- 平台管理员：跨 tenant 需 `platform:im:moderate`，默认不开放。

### 21.3 消息模型与顺序

- `messages.seq`：每个 conversation 内单调递增，服务端生成，保证顺序。
- `client_msg_id`：客户端生成，唯一约束 `(conversation_id, client_msg_id)`，重试不重复插入。
- 消息类型：`text`、`image`、`order`、`product`、`system`。
- 图片/文件先走附件上传，消息只存 `attachment_id`。
- 已读：`conversation_members.last_read_seq` + `message_receipts`。
- 未读数：conversation 冗余计数 + Redis 计数，读消息后更新，定期落库。

### 21.4 实时链路

```text
客户端 A
  -> POST /im/conversations/{id}/messages
  -> FastAPI 事务写 messages + seq + unread
  -> Redis Pub/Sub publish {conversation_id, message_id, seq}
  -> 所有 WebSocket 实例收到广播
  -> 每个实例查找本机连接，推送给会话成员
  -> 客户端 B 收到 -> ACK -> 已读回执
```

- WebSocket 入口：`/ws/im?ticket=...`。
- 不把长期 access token 放 URL；先用 `POST /im/ws-ticket` 换一次性 ticket（Redis 60 秒有效，绑定 user/tenant）。
- 连接建立后服务端校验 tenant membership / seller membership。
- 心跳 ping/pong 30 秒；客户端指数退避重连。
- 重连后携带 `last_seq`，先拉历史缺口，再恢复实时。

### 21.5 多实例与高可用

- WebSocket 连接是长连接，连接建立后固定在某一个实例；负载均衡只需支持 Upgrade，不要求后续请求粘性。
- 跨实例消息通过 Redis Pub/Sub（或 Redis Streams）广播；每个实例只推本机连接。
- 连接注册表放 Redis：`im:online:{tenant_id}:{user_id}` -> instance_id，TTL 60 秒，心跳续期。
- Redis 故障：WebSocket 推送失败，客户端降级为轮询 `GET /im/conversations/{id}/messages?after_seq=`；消息仍先落 PostgreSQL，不丢。
- PostgreSQL 故障：发送接口返回 503；客户端保留本地待发送队列，用 `client_msg_id` 重试。
- 超大规模（>1 万长连接）：引入 Centrifugo 作为独立实时网关，FastAPI 只负责鉴权和持久化，Centrifugo 负责连接/广播。
- 离线推送：Worker 检测用户不在线，发站内信/邮件/短信/Web Push；不把推送当消息事实源。

### 21.6 审核与安全

- 文本敏感词/垃圾广告检测；图片走内容安全审核。
- 举报 -> `im_reports` -> 运营处理；违规消息可 `moderated` 下架，保留审计副本。
- 用户可屏蔽对方；屏蔽后不能新建会话/发送消息。
- 卖家只能看到履约所需买家信息；默认脱敏手机号/地址。
- 消息保留期按 tenant 配置；注销/删除遵循隐私政策。
- 不做端到端加密（第一版），否则平台无法做纠纷取证与内容审核；敏感信息靠访问控制、传输 TLS、存储加密。

### 21.7 前端

Portal（买家）：

- 商品详情/订单详情「联系卖家」。
- `/messages` 会话列表，未读 badge。
- `/messages/[id]` 聊天窗口：文字、图片、订单卡片、已读、举报/屏蔽。
- WebSocket 断线自动重连 + 轮询兜底。

Portal（卖家中心）：

- `/seller/messages` 会话列表，按店铺隔离。
- 聊天窗口 + 快捷回复 + 订单卡片。
- 客服/店员可加入会话（seller_members）。

Admin：

- 客服中心：会话检索、举报处理、违规消息下架。
- 所有查看/操作写审计日志。

### 21.8 测试与验收

- 买家 A 不能读买家 B 的会话/消息。
- 卖家 A 不能读卖家 B 的会话/消息。
- 租户 A 的运营不能读租户 B 的会话。
- 多实例：A 连接实例 1，B 连接实例 2，消息经 Redis 广播后双方都收到。
- Redis 挂掉：WebSocket 断开/无推送，轮询能补齐消息，不丢消息。
- 重复发送同一个 `client_msg_id` 只落一条消息。
- 断线重连后按 `last_seq` 补齐缺口，消息顺序正确。
- 违规消息下架后普通用户不可见，运营审计可见。

