# Admin Console (Ant Design Pro 6 + FastAPI)

This repository contains the admin console of 赛霄玄思, a multi-tenant C2C marketplace platform.

## Frontend routes

| Route | Page |
|---|---|
| `/users` | 用户管理（重定向到 `/users/list`） |
| `/users/list` | 用户列表 |
| `/users/departments` | 部门管理 |
| `/users/roles` | 角色管理 |
| `/system/settings/payment` | 支付设置（支付宝 / 微信支付） |
| `/system/settings/sms` | 短信设置（阿里云短信） |
| `/system/settings/email` | 邮件系统（QQ / 163 / 企业邮箱 / 自定义 SMTP） |
| `/system/settings/storage` | 存储设置（本地 / 阿里云 OSS） |
| `/attachments` | 全局附件管理 |
| `/notifications` | 触达通知（短信 / 邮件 / 站内信） |

## Page tabs

- A horizontal page tab bar is rendered above the content area.
- Opening a route from the sidebar adds a tab.
- Tabs can be closed individually with the tab close icon; the home tab (`/dashboard/analysis`) is fixed.
- `关闭全部` resets to the home tab.
- Tab labels are resolved from the existing `menu.*` i18n keys.

## Backend

The FastAPI app lives in `backend/` and uses **PostgreSQL 18.6** on `127.0.0.1:5433` by default. PostgreSQL 16 on 5432 is kept for other local projects.

```bash
cd backend
uv sync
createdb -p 5433 ant_design_pro_admin 2>/dev/null || true
psql -p 5433 -d ant_design_pro_admin -f scripts/migrate_20261110_user_profile.sql
uv run uvicorn app.main:app --host 127.0.0.1 --port 9000
```

- OpenAPI docs: http://127.0.0.1:9000/docs
- Health check: http://127.0.0.1:9000/health
- All business endpoints: `/api/v1`
- First startup creates tables and seeds demo users/settings/attachments/notifications.

## Frontend development

```bash
cd ant-design-pro
npm start          # 租户控制台 http://localhost:8010
cd apps/platform && npm start   # 平台端控制台 http://localhost:8001
# dev proxy: /api/v1 -> http://127.0.0.1:9000
```

**端口为什么是 8010 而不是 8000**：租户端用 utoopack 开发服务器，它会额外占用
`PORT + 1` 的 `127.0.0.1` 端口（8000 → 8001）作为内部助手端口。8001 是平台端的
正式端口，被这个助手占住后 `http://127.0.0.1:8001` 会落到租户端的 404 上。
所以租户端固定 8010（助手落在 8011），把 8001 完整留给平台端。
同一个 `localhost` 的另一个坑：平台端只监听 IPv6 通配地址，`localhost` 走 `::1`
能通；加了转发/助手抢走 IPv4 时就会出现「同一个端口两个应用」。改端口后两端不再重叠。

For a production build against a real API:

```bash
API_BASE_URL=https://api.example.com/api/v1 npm run build
```

## Authentication & RBAC

- `POST /api/v1/auth/login` issues a short-lived JWT access token and an HttpOnly refresh cookie.
- `GET /api/v1/auth/me` returns user, tenants, roles, permission codes and permission version.
- `POST /api/v1/auth/refresh` rotates the refresh token; `POST /api/v1/auth/logout` revokes it.
- Admin endpoints use `require_permission(...)`; unauthorized direct API calls return 401/403.
- Demo accounts: the seeded usernames are `admin` (administrator) and `lisi` (operator).
  Their initial passwords are produced by the seeding logic for **local demos only** and
  are intentionally not documented here. Change them before exposing the service publicly.
- Permissions are stored in `permissions`, `role_permissions`, `member_roles`; the front-end maps them in `src/access.ts`.
- Redis stores refresh tokens and short-lived permission cache entries. If Redis is unavailable, protected APIs fail closed.

### Platform-scoped permissions

Tenant provisioning is **not** a tenant role. `platform:tenant:read` and
`platform:tenant:manage` are only granted to `platform_admin` (and the legacy
demo `admin`); `platform_support` gets the read code. A `tenant_owner` must
never be able to enumerate or create tenants — the front-end gate is
`access: 'canTenantManage'` in `config/routes.ts`.

Membership is per tenant: a user of tenant B never gets a demo-tenant
membership, and `seed_auth_data` only backfills the seeded demo accounts
(`admin`, `lisi`, `wangwu`, `zhaoliu`, `chenqi`).

## User management

- The sidebar **用户管理** is a submenu: **用户列表 / 部门管理 / 角色管理**.
- `departments` and `roles` are dictionary tables with their own CRUD APIs.
- User records carry `department_id`, `birthday`, `gender` and a hashed login password.
- Password hashes use `pwdlib[argon2]`; the API never returns password hashes or plaintext passwords.
- Existing databases must run `backend/scripts/migrate_20261110_user_profile.sql` once; it is idempotent.

## Attachment center

All module uploads should use `src/components/AttachmentUpload` and the `/api/v1/attachments/upload` endpoint. The shared upload component records metadata in PostgreSQL and writes the blob to `backend/uploads/` in this demo. Swap the storage adapter for OSS presigned uploads later without changing page code.

## API contract

Successful response:

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {}
}
```

List response data uses the ProTable shape:

```json
{
  "list": [],
  "total": 0,
  "current": 1,
  "pageSize": 10
}
```

## Demo limitations

- Payment, SMS, email and OSS connection tests validate configuration only; they do not call real vendor APIs.
- Admin JWT authentication and RBAC are implemented; C-end registration, seller center, multi-tenant data scoping and Portal are still subsequent phases.
- Before exposing publicly: rotate `JWT_SECRET`, set `COOKIE_SECURE=true`, add rate limiting, secret encryption (KMS/Vault), tenant-scoped business tables and audit review.
- Role management currently maintains the role dictionary only; permission-point assignment and enforcement are a separate iteration.
- `backend/app/seed.py` and `create_all` are for local development. Use Alembic migrations and managed PostgreSQL in production.

## Backend tests

The FastAPI backend ships a pytest suite (plan §17/§18: unit, API and isolation
matrix tests). It is fully isolated from development data.

```bash
cd backend
uv pip install --python .venv/bin/python "pytest>=8" "pytest-asyncio>=0.24" "httpx>=0.28"
.venv/bin/python -m pytest tests/          # 93 tests
.venv/bin/python -m pytest tests/ -q -k tenant
```

- PostgreSQL: dedicated database `ant_design_pro_admin_test`, schema rebuilt from
  the SQLAlchemy metadata and seeded once per session.
- Redis: database index `15`, flushed around every test.
- Every test runs inside an outer transaction that is rolled back, so tests are
  order independent.
- Lint/type gates: `uvx ruff check app tests` and `uvx pyright app`.

| Module | Covers |
|---|---|
| `test_system_auth.py` | health, login/refresh/logout, register, 401/403, disabled accounts |
| `test_rbac_permissions.py` | operator/admin matrix, customer lockdown, token audience |
| `test_users_management.py` | user CRUD, membership + role sync, department CRUD, permission version |
| `test_tenant_isolation.py` | cross-tenant isolation, settings isolation, forged tenant token, restart regression |
| `test_commerce_order_flow.py` | server-side pricing, stock reserve/release, seller split, buyer isolation, fulfilment |
| `test_im_conversations.py` | conversation isolation, seq ordering, `client_msg_id` idempotency, unread counts |
| `test_seller_finance.py` | seller centre scoping, pending_review products, ledger, payment replay, payout |

## Database migrations (Alembic)

The schema is owned by **Alembic**; `Base.metadata.create_all` is no longer used
at runtime.

```bash
cd backend
.venv/bin/python -m alembic upgrade head          # apply pending revisions
.venv/bin/python -m alembic current               # show the stamped revision
.venv/bin/python -m alembic revision --autogenerate -m "add xyz"
.venv/bin/python -m alembic downgrade -1
```

- `migrations/env.py` reads the URL from `app.core.config.settings`, so the CLI
  and the API always target the same database. `ALEMBIC_DATABASE_URL` overrides
  it for a one-off run against another database.
- The baseline revision `1612718d5c9b` creates all 31 tables.
- On startup `ensure_schema_at_head()` runs `upgrade head` (disable with
  `DB_AUTO_MIGRATE=false` once migrations run in a release pipeline).
- A database created by the old `create_all` path has no `alembic_version`; the
  startup hook detects that and **stamps the baseline** before upgrading, so an
  existing dev database is adopted instead of failing.
- `tests/test_migrations.py` builds the schema twice — once by replaying
  migrations, once from the models — and fails on any column/index/unique/FK
  drift, plus asserts that `--autogenerate` produces an empty diff.

> Cold start on an empty database is covered: `upgrade head` creates 31 tables +
> `alembic_version`, then `seed_demo_data()` seeds 5 users and the demo tenant.

## Rate limiting

A Redis fixed-window limiter sits in front of every route
(`app/core/rate_limit.py`, registered as middleware).

| Scope | Default | Env |
|---|---|---|
| global (`rl:global:{ip}`) | 600 req / 60 s | `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS` |
| auth (`rl:auth:{ip}`) — login/register/refresh | 20 req / 60 s | `RATE_LIMIT_AUTH_REQUESTS`, `RATE_LIMIT_AUTH_WINDOW_SECONDS` |
| kill switch | on | `RATE_LIMIT_ENABLED=false` |

- Over budget → `429` with `Retry-After` and `{"code":429,"data":{scope,limit,window_seconds}}`.
- Successful responses carry `X-RateLimit-Limit` / `X-RateLimit-Remaining`.
- `/health`, `/docs`, `/redoc`, `/openapi.json`, `/uploads/*` are never limited.
- A Redis outage **fails open** (logs `rate_limit_unavailable`) so a cache incident
  cannot lock everyone out of the product; permissions still fail closed.
- `X-Forwarded-For` (first hop) is honoured when present.

### Permission cache invalidation

Permissions are cached for 60 s under
`perm:{tenant_id}:{user_id}:v{tenant.permission_version}`. Every mutation that can
change a member's effective rights calls `bump_permission_version()`:

- role permission set edited (`PUT /roles/{id}/permissions`)
- a user's role changed (`PUT /users/{id}`)
- a user created or deleted

Without the bump a demoted user kept their old privileges until the TTL expired —
covered by `test_users_management.py::test_role_change_invalidates_cached_permissions`.

## Buyer shopping (portal)

Standalone pages (declared with `layout: false`, so they render their own header):

| Route | Page | File |
|---|---|---|
| `/portal` | 商城首页 / 我的订单 | `src/pages/portal/index.tsx` |
| `/portal/products/:id` | 商品详情（多 SKU、库存、店铺） | `src/pages/portal/product-detail` |
| `/portal/cart` | 购物车（勾选、改数量、结算） | `src/pages/portal/cart` |
| `/portal/addresses` | 收货地址簿 | `src/pages/portal/addresses` |
| `/portal/payment-result?orderId=` | 支付结果 + 模拟支付 | `src/pages/portal/payment-result` |

Backend (`app/api/v1/portal_shopping.py`, prefix `/portal`):

```text
GET    /portal/products/{product_id}     # 详情 + SKU 列表 + 店铺
GET    /portal/cart                      # 汇总（已选件数/金额/失效数）
POST   /portal/cart/items                # 加购（同 SKU 自动合并）
PUT    /portal/cart/items/{item_id}      # 改数量 / 勾选
DELETE /portal/cart/items/{item_id}
DELETE /portal/cart
POST   /portal/cart/checkout             # 仅结算「已勾选且在售」的行
GET    /portal/addresses
POST   /portal/addresses                 # 第一条自动成为默认
PUT    /portal/addresses/{address_id}
POST   /portal/addresses/{address_id}/default
DELETE /portal/addresses/{address_id}    # 删默认地址会自动提升下一条
```

Design notes:

- **Cart is one row per (tenant, buyer, sku)** — `uq_cart_tenant_buyer_sku`.
  Adding the same SKU merges quantities instead of creating duplicates.
- **Checkout delegates to `services.order.create_order`** so server-side pricing,
  stock locking (`stock -= qty`, `locked_stock += qty`) and seller splitting stay
  in one place. Only the checked-out lines leave the cart.
- **Every query is scoped to `tenant_id` + `user_id`**; foreign ids answer `404`
  (not `403`) so row existence is not leaked.
- Permissions: `cart:read`, `cart:manage`, `address:read`, `address:manage`,
  granted to the `customer` role only — back-office roles get `403` on cart APIs.
- Tables: `cart_items`, `addresses` (migration `cfe6cdb1d477`).
- Use `backend/scripts/autogen_migration.sh "message"` to create a migration: it
  autogenerates against a **clean database built from the migration history**, not
  against a legacy dev database (which produces destructive noise such as
  `drop_constraint` on unnamed constraints).

## IM: read receipts, images, moderation, multi-instance fan-out

### Endpoints

```text
POST /im/conversations/{id}/read         {seq}   -> read receipt, clears my unread
GET  /im/conversations/{id}/read-state            -> my/peer last_read_seq + unread counts
POST /im/conversations/{id}/messages     {type, content, attachment_id, client_msg_id}
POST /im/messages/{id}/report            {reason}  -> im:report
GET  /im/reports?status=pending                    -> im:moderate
POST /im/reports/{id}/handle             {action:accept|reject, note}
```

### Read receipts

- Stored on `conversation_members.last_read_seq`; **only moves forward**, so a
  delayed or replayed receipt cannot resurrect unread messages.
- Marking read clears the caller's unread counter; the peer reads the receipt from
  `read-state` (`peer_last_read_seq`).
- The web client posts a receipt for the newest visible message and shows
  `对方已读至 seq N`.

### Image messages

- `type="image"` requires `attachment_id`; the caption is optional.
- The attachment must exist in the same tenant, be an image (`category` or
  `mime_type`), and be **uploaded by the sender** (`attachments.uploader` now
  records the real username — previously it was hardcoded `admin`).
- `messages.payload` carries `{attachment_id, url, mime_type, size}`.

### Report & moderation

- `im_reports` is append-only: unique `(message_id, reporter_id)`, so repeat
  reports are idempotent; a user cannot report their own message.
- Accepting a report sets `messages.status='moderated'`. The message disappears
  from `GET .../messages` for ordinary users but stays visible to `im:moderate`
  holders — evidence is never deleted.
- Handling an already-handled report returns `400`.

### Multi-instance fan-out (Redis Pub/Sub)

```text
POST message -> persist (PostgreSQL, source of truth)
             -> publish to Redis channel `im:events`
             -> every replica receives it (including the publisher)
             -> each replica pushes to the sockets it owns
```

- `app/core/im_bus.py` owns publish/subscribe; the subscriber starts in the
  lifespan and logs `im_bus_subscribed`.
- Verified with two real replicas (:9000, :9001): a socket held by :9001 received
  a message published by :9000.
- Redis outage degrades to the existing polling
  (`GET .../messages?after_seq=`) — messages are already durable, so nothing is
  lost; only push latency suffers.
- Note: the REST send path now publishes too (previously only WebSocket-originated
  messages were broadcast, so a REST-sent message never reached the peer's socket).

## Finance: commission rules, 账期, payout review, settlement batches

### Commission rules (`commission:read` / `commission:manage`)

```text
GET    /admin/commission-rules
POST   /admin/commission-rules
PUT    /admin/commission-rules/{id}
DELETE /admin/commission-rules/{id}
POST   /admin/commission-rules/preview   {seller_id?, category_id?, subtotal_cents}
```

- Rates are **basis points** (`rate_bps`: 1000 = 10%) plus an optional
  `fixed_fee_cents`.
- Resolution: most specific scope wins → `priority` → newest id.
  `seller+category > seller > category > tenant default`.
- `effective_from` / `effective_to` bound a rule to an accounting period;
  `status='disabled'` rules are ignored.
- A tenant-wide default (10%) is seeded, so orders never depend on a hardcoded
  rate. Order creation calls `finance.resolve_commission_rule()` +
  `compute_commission()` instead of `subtotal * 0.10`.

### 账期 (settlement hold)

`tenants.settlement_hold_days` (default 7). A seller's ledger reports three
reconciling numbers:

| Field | Meaning |
|---|---|
| `available_cents` | withdrawable now: order completed **and** hold elapsed, minus money already paid out |
| `pending_cents` | earned but still inside the hold window |
| `balance_cents` | `available_cents + pending_cents` (always) |

Money already paid out is deducted from the most settleable bucket first, so the
three numbers reconcile even after partial payouts
(`test_ledger_buckets_reconcile_after_a_payout`).

### 提现审核 (payout review)

```text
POST /admin/sellers/{id}/payouts      # seller/admin requests a withdrawal -> pending
GET  /admin/payouts?status=
POST /admin/payouts/{id}/approve      # pending -> approved
POST /admin/payouts/{id}/reject       # pending -> rejected (+reason), no ledger movement
POST /admin/payouts/{id}/pay          # approved -> paid, writes the negative ledger entry
```

- Only **one** open request per seller (`409` otherwise).
- A rejected request is terminal and never touches the ledger.
- Paying before approval returns `400`.
- The ledger entry is written on **pay**, not on request, so a request is never
  mistaken for money that already left.

### 结算批次 (settlement batches)

```text
GET  /admin/settlement-batches
POST /admin/settlement-batches            {period_start, period_end, note}
POST /admin/settlement-batches/{id}/confirm   draft -> confirmed
POST /admin/settlement-batches/{id}/pay       confirmed -> paid (pays its payouts)
```

- A batch sweeps **approved and unbatched** payouts; creating one with nothing to
  sweep returns `400`.
- Draft batches cannot be paid; batches are tenant-scoped.

## SaaS billing (Phase 5)

### Model

```text
plans                 code, name, price_cents, period(monthly|yearly), trial_days,
                      quotas {metric: limit|null}, features [keys], status, sort
tenant_subscriptions  tenant_id UNIQUE, plan_id, status(trialing|active|past_due|cancelled),
                      current_period_start/end, trial_end, cancel_at_period_end
invoices              tenant_id, invoice_no UNIQUE, amount_cents, status(pending|paid|void),
                      period_start/end, due_at, paid_at
```

Seeded catalogue: `free`（0 / 50 商品 / 5 成员）, `pro`（¥990/月 / 5000 / 50，含 im+finance）,
`enterprise`（¥9990/年 / 不限 / 不限）. The **demo tenant is on `pro`** so quota checks never
block the seeded demo data.

### Enforcement

| Layer | Where | Effect |
|---|---|---|
| Tenant status | `context_from_payload` | `suspended` tenant → every API returns `403 租户不可用` |
| Quota | `billing.check_quota` at product & member creation | `403 已超出套餐配额：<metric> 上限 N` |
| Feature flags | `plan.features` returned by `/tenant/subscription` | UI can hide unsupported modules |

`quotas` semantics: a **missing key** or `null` means unlimited; `0` blocks the resource.

Usage is **computed live** from business tables (`products`, active `tenant_members`,
`orders_this_month`) — there is no denormalised counter that can drift.

### Endpoints

```text
GET  /platform/plans                 POST /platform/plans          PUT /platform/plans/{id}
GET  /platform/tenants-list          # tenants + plan + subscription + used/quotas/exceeded/days_left
GET  /platform/tenants/{id}/usage    POST /platform/tenants/{id}/subscription  {plan_id, trial}
POST /platform/tenants/{id}/renew    {days?}   -> extends the term + issues a pending invoice
PUT  /platform/tenants/{id}          # rename (status edit is rejected for demo)
POST /platform/tenants/{id}/suspend  |  /resume
GET  /platform/invoices?tenant_id=&status=   POST /platform/invoices/{id}/pay
GET  /tenant/subscription            # tenant-facing: own plan, quotas, usage, days_left
```

- New tenants created through `POST /platform/tenants` automatically start on `free`
  with a trial window.
- The demo tenant (`slug=demo`) cannot be suspended → `400`.
- Paying an already-paid invoice returns `400`.
- All console routes require `platform:tenant:read` / `platform:tenant:manage`; a
  tenant owner gets `403`.

## Audit trail

`audit_logs` is written by every mutation on the order / payment / settlement chain
and by privileged configuration changes.

### Guarantees

- **Same transaction.** `audit.record()` only stages a row on the caller's session;
  the caller's `commit()` persists it together with the business change. A rollback
  removes both, so an audited change can never commit without its trail entry.
- **Append only.** No update/delete helper exists.
- **Tenant scoped.** Reads are filtered by `tenant_id`; platform-wide reads require
  the `platform:tenant:read` permission (role name alone is not enough — the demo
  superuser holds the legacy `admin` role).
- **Correlatable.** Each row stores `actor_id`, `ip` (first `X-Forwarded-For` hop or
  socket peer) and `trace_id`. Every response carries `X-Trace-Id`; send
  `X-Request-Id` to force a value and match it against your gateway logs.

### Recorded actions

```text
order.created            order.paid            order.cancelled       order.confirmed
seller_order.shipped     seller_order.refunded
payout.requested         payout.approved       payout.rejected       payout.paid
settlement_batch.created settlement_batch.confirmed                  settlement_batch.paid
commission_rule.created  commission_rule.updated                    commission_rule.deleted
im.message.moderated     tenant.suspended      tenant.resumed        tenant.updated
role.permissions_updated
```

### API

```text
GET /api/v1/audit-logs?current=&pageSize=&action=&target_type=&target_id=&actor_id=&tenant_id=
GET /api/v1/audit-logs/actions
```

Both require `audit:read`. The console page is `/system/audit` (menu 审计日志),
gated by `access: 'canAuditRead'`, with an action/target filter and a drawer that
diffs `before` / `after`.

> `operator` and C-end customers have no `audit:read` → `403`; a tenant owner can
> read only its own tenant's rows.

## E2E regression (permissions & 403)

The template shipped a single mock-based `e2e/login.spec.ts`. Real RBAC needs the
real stack, so there is a second Playwright config:

```bash
# backend must be running on :9000
npm run e2e:regression          # 17 tests, ~1 min
```

`playwright.e2e.config.ts`:

| Setting | Value | Why |
|---|---|---|
| baseURL | `http://localhost:8000` (`E2E_PORT` override) | reuses the dev server; `mock/` defines no `/api/v1/*` handler, so calls hit FastAPI |
| testMatch | `*.e2e.spec.ts` | keeps the legacy mock spec separate |
| workers | 1 | one dev server, deterministic ordering |
| locale | `zh-CN` | matches the shipped menus |

| Spec | Covers |
|---|---|
| `permissions.e2e.spec.ts` | admin opens every guarded page; operator lacks audit/tenant menu entries and gets **403** on `/users/roles`, `/users/departments`, `/system/settings/payment`, `/system/audit`; customer blocked from the back office; anonymous redirected to login |
| `portal.e2e.spec.ts` | browse → detail → cart → checkout → mock payment, plus the address book |
| `seller.e2e.spec.ts` | shop owner sees the seller centre; a C-end buyer's seller API calls return 403; admin opens seller management |

Two Playwright gotchas encoded in `e2e/helpers/auth.ts`:

1. **CJK button labels.** antd inserts a space between two Chinese characters
   (`登 录`, `保 存`), so exact-name selectors miss. Match with `/登\s*录/` or target
   `button.ant-btn-primary`.
2. **`page.goto` aborts on a guard redirect.** A failing route `access` redirects
   client-side and the navigation rejects with `net::ERR_ABORTED` even though the
   403 page renders — navigate with `waitUntil: 'commit'` and swallow the abort.

> A real defect was found this way: `/users/roles` and `/users/departments` had no
> route-level `access`, so only the menu entry was hidden while a direct URL visit
> rendered the page for an operator without `role:manage`. Both routes now carry
> `access`, matching the API.

## 自定义域名（B6）

租户身份来自 **请求 Host**（`tenant_domains` 表是唯一事实源）；`?tenant=<slug>` 只是开发兜底。

### 绑定流程（平台端 `/overview` → 右侧「域名」）

1. 填域名（如 `shop.example.com`）→ 绑定后状态是 **待验证**；
2. 把抽屉里给出的 TXT 记录加到域名服务商：`_sxxs-verify.shop.example.com` = `sxxs-verify=<token>`；
3. DNS 生效后点 **验证** → **已生效**。只有 active 的域名才会把公开站点解析到该租户。

自有子域（配置了 `TENANT_BASE_DOMAIN` 时，新建租户自动带一条 `<slug>.<基域>`）创建即生效，不需要 TXT。

### 状态含义

| 状态 | 含义 | 会解析到租户吗 |
|---|---|---|
| `pending` | 已绑定、未验证 | 否 |
| `active` | 验证通过（或自有子域） | 是 |
| `failed` | 最近一次验证没查到 TXT | 否 |
| `disabled` | 手动停用 | 否 |

租户本身不是 `active` 时，它的域名即使 `active` 也不解析 —— 所以「先停租户、再解绑域名」是安全的。

### 环境变量

| 变量 | 说明 |
|---|---|
| `TENANT_BASE_DOMAIN` | 租户子域后缀；留空 = 不自动建子域 |
| `PLATFORM_HOST` | 平台控制台自己的域名，命中时不做租户解析 |
| `DOMAIN_VERIFY_PROVIDER` | `none`（默认，verify 直接 503）/ `dns`（需 dnspython）/ `static`（仅测试） |
| `TENANT_HOST_FALLBACK` | **线上必须 `false`**；本地开发 `true` 时未知 Host 兜底到 demo |

### 运维注意

- **`TENANT_HOST_FALLBACK=false` 是硬要求。** 开着它，任何未知域名都会被当成 demo 站：租户以为域名生效了，买家看到的却是别人的站。
- **证书由反代 / CDN 负责。** 应用只做 host→tenant 映射与 CORS 放行，不签发证书、不修改 DNS（只给出要加的 TXT 记录）。
- **跨域**：CORS 放行「平台主机 + 已生效的租户域名」，60 秒缓存，绑定/解绑时立即失效重建；库不可用时保持旧集合（不放行未知域名）。
- **登录态按域名隔离。** refresh cookie 不设 `Domain`（host-only），且 `/auth/refresh` 校验 token 里的租户与请求 Host 一致，不一致返回 401 且 **不消耗** 该 token。
- **`dns` 校验器需要 `dnspython`**；没装时 verify 返回 503 —— 故意不判成「验证失败」，免得把工程配置问题甩锅给客户。
