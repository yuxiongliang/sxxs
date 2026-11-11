# 注册用户 / 运营人员页面权限的高可用实现方案

## Context

当前系统已经具备：

- Ant Design Pro 6 前端，左侧菜单由 `config/routes.ts` 静态路由生成。
- `src/access.ts` 只有 `canAdmin` 一个权限开关。
- FastAPI 后端的用户、部门、角色、附件、通知、设置接口已经落地。
- `roles` 表目前只有角色字典（code/name/status），没有权限表、角色权限关系、用户多角色关系。
- 登录仍走 Ant Design Pro 的 Mock 登录；FastAPI 没有 JWT 鉴权，接口没有权限依赖。

目标：

- 注册用户登录后只看到注册用户可见的页面。
- 运营人员登录后只看到运营人员可见的页面。
- 管理员可以配置角色能看哪些页面、能执行哪些操作。
- 前端菜单隐藏只是体验，后端必须对每个接口做真实鉴权。
- 在 Redis/多副本部署下保持权限判断一致、可失效、可降级。

## Current Gaps

1. `src/access.ts` 只有 `canAdmin`，无法表达 `user:read`、`notification:send` 这类细粒度权限。
2. `config/routes.ts` 只有 `/admin` 配了 `access: 'canAdmin'`，其余页面没有访问控制。
3. `getInitialState` 只拉 `currentUser`，没有返回 `roles/permissions/menus`。
4. 后端 `roles` 表没有 `permissions`、`role_permissions`、`user_roles`，无法动态配置。
5. 后端所有 `/api/v1/*` 接口都没有 `Depends(require_permission(...))`，任何人可直接调用。
6. 登录仍是 Mock，没有真实的 access token / refresh token。
7. `PageTabs` 只做页签，不感知权限变化；角色被降权后旧页签仍可能停留。

## Recommended Architecture

采用 **RBAC + 权限码 + 静态路由 access + 后端强制校验 + Redis 版本化缓存**。

```text
浏览器
  ├─ Ant Design Pro 6
  │   ├─ getInitialState() -> GET /api/v1/auth/me
  │   ├─ access.ts: permission code -> boolean
  │   ├─ config/routes.ts: access: 'canUserRead' 等
  │   └─ PageTabs: 权限变化时清理无权页签
  │
  └─ FastAPI（无状态，多副本）
      ├─ JWT access token（短 TTL）
      ├─ refresh token（HttpOnly Cookie，轮换）
      ├─ require_permission('user:read') 依赖
      ├─ service 层数据范围校验
      ├─ Redis：权限快照 / token 版本 / 失效广播
      └─ PostgreSQL：users / roles / permissions /
                       role_permissions / user_roles / audit_logs
```

### 为什么采用静态路由 + 权限码，而不是完全动态路由

- Umi 的页面组件是构建期解析的；后端返回任意 `component: './xxx'` 不能保证构建产物里存在。
- 静态路由 + `access` 字段可以稳定地让 ProLayout 隐藏无权菜单，同时保留 403 兜底。
- 角色和权限可以在数据库中动态配置；新增页面仍然需要一次前端发布，这是可接受的长期维护成本。
- 如果确实需要后端完全动态菜单，增加 `componentRegistry` + `patchRoutes`，但这属于后续增强，不作为第一版。

## Permission Model

### 数据表

| 表 | 关键字段 | 说明 |
|---|---|---|
| `permissions` | id, code, name, module, action, description | 权限点字典，例如 `user:read` |
| `roles` | id, code, name, status, sort | 已有角色表 |
| `role_permissions` | role_id, permission_id | 角色-权限多对多 |
| `user_roles` | user_id, role_id | 用户-角色多对多 |
| `menus`（可选） | id, parent_id, path, name_key, icon, permission_code, sort, visible | 如果希望后端下发菜单树 |
| `audit_logs` | id, actor_id, action, target_type, target_id, before, after, ip, trace_id, created_at | 权限变更审计 |

现有 `users.role` 单角色字符串保留兼容；迁移时把每个用户的 `role` 写入 `user_roles`，新逻辑以 `user_roles` 为准。这样以后一个用户可以有多个角色，不需要再次改表。

### 权限码建议

```text
profile:read          profile:update
dashboard:read
user:read             user:write
 department:read       department:manage
role:read             role:manage
setting:payment       setting:sms
setting:email         setting:storage
attachment:read       attachment:upload
attachment:delete     notification:read
notification:send     audit:read
```

### 角色-页面矩阵（建议初始值）

| 页面/能力 | registered | operator | admin |
|---|---|---|---|
| 欢迎页 / 个人中心 / 个人设置 | ✅ | ✅ | ✅ |
| Dashboard 分析/监控/工作台 | ❌ | ✅ | ✅ |
| 用户列表 | ❌ | 只读（可选） | ✅ |
| 部门管理 / 角色管理 | ❌ | ❌ | ✅ |
| 支付/短信/邮件/存储设置 | ❌ | ❌ | ✅ |
| 附件管理 | 仅自己的附件（可选） | ✅ | ✅ |
| 触达通知 | ❌ | 发送/查看 | ✅ |
| 审计日志 | ❌ | ❌ | ✅ |

> `registered` 的具体范围需要产品确认：是只允许个人中心，还是允许上传附件/提交工单。建议默认最小权限，只给 `profile:read/update`。

## Auth Flow

1. `POST /api/v1/auth/register`
   - 创建用户，默认角色 `registered`。
   - 建议 `status=pending` + 邮箱验证；管理员审核通过后改为 `active`。
2. `POST /api/v1/auth/login`
   - 校验 argon2 密码。
   - 返回 `access_token`（10-15 分钟）和 refresh token（HttpOnly + Secure + SameSite Cookie，7 天，轮换）。
3. `GET /api/v1/auth/me`
   - 返回：
     ```json
     {
       "user": { "id": 1, "username": "admin", "nickname": "管理员" },
       "roles": ["admin"],
       "permissions": ["user:read", "user:write", "role:manage"],
       "permission_version": 12,
       "menus": []
     }
     ```
4. `POST /api/v1/auth/refresh`
   - 轮换 refresh token；检测复用；失败则清空会话。
5. `POST /api/v1/auth/logout`
   - 撤销 refresh token，清理 Redis 会话。

JWT 只放 `sub`、`tenant_id`、`roles`、`permission_version`，不把全量权限塞进 token，避免角色变更后旧 token 仍携带旧权限。

## Frontend Implementation

### 1. `getInitialState`

`src/app.tsx` 改为：

- 调用 `/api/v1/auth/me`。
- 返回 `currentUser`、`roles`、`permissions`、`permissionVersion`、`menus`。
- 失败时按 401 跳登录；网络错误显示错误页，不默认放行。

### 2. `src/access.ts`

```ts
export default function access(initialState) {
  const permissions = new Set(initialState?.permissions ?? []);
  return {
    canDashboard: permissions.has('dashboard:read'),
    canUserRead: permissions.has('user:read'),
    canUserWrite: permissions.has('user:write'),
    canDepartmentManage: permissions.has('department:manage'),
    canRoleManage: permissions.has('role:manage'),
    canAttachmentRead: permissions.has('attachment:read'),
    canAttachmentUpload: permissions.has('attachment:upload'),
    canNotificationSend: permissions.has('notification:send'),
    canPaymentSetting: permissions.has('setting:payment'),
    canSmsSetting: permissions.has('setting:sms'),
    canEmailSetting: permissions.has('setting:email'),
    canStorageSetting: permissions.has('setting:storage'),
  };
}
```

### 3. 路由 access

在 `config/routes.ts` 为每个页面补：

```ts
{ path: '/users/list', name: 'list', access: 'canUserRead', ... }
{ path: '/users/departments', name: 'departments', access: 'canDepartmentManage', ... }
{ path: '/users/roles', name: 'roles', access: 'canRoleManage', ... }
{ path: '/system/settings/payment', name: 'payment', access: 'canPaymentSetting', ... }
```

ProLayout 会自动隐藏无权菜单；直接输入 URL 时由路由 access 拦截并跳 403。

### 4. 按钮级权限

- 用户新增/编辑/删除：`<Access accessible={access.canUserWrite}>`。
- 角色管理：`canRoleManage`。
- 通知发送：`canNotificationSend`。
- 附件上传/删除：`canAttachmentUpload` / `canAttachmentDelete`。

### 5. PageTabs

- 角色/权限变化后，关闭当前用户已无权的页签。
- 监听 `permissions`/`permissionVersion` 变化；对每个 tab 的 path 做 access 判断，无权则移除。
- 不要仅靠隐藏页签做安全控制，后端仍然是最终裁决。

## Backend Enforcement

### 1. 统一依赖

```python
def require_permission(code: str):
    async def dependency(user=Depends(get_current_user), db=Depends(get_db)):
        if not await permission_service.user_has_permission(db, user.id, code):
            raise HTTPException(status_code=403, detail="无权限")
        return user
    return dependency
```

每个路由显式声明：

```python
@router.get("", dependencies=[Depends(require_permission("user:read"))])
```

写操作使用 `user:write`、`role:manage`、`setting:payment` 等。

### 2. 数据范围

页面级 RBAC 之外，业务数据还需要 data scope：

- `role.data_scope`: `all` / `department` / `self`。
- 用户只能查询自己部门或自己的数据时，DAO 自动追加 `department_id` / `created_by` 条件。
- 附件、通知、用户列表都适用。
- 更高要求可加 ABAC/ReBAC（资源级 ACL），但第一版不建议过度设计。

### 3. 审计

- 角色权限变更、用户角色变更、管理员跨部门操作写 `audit_logs`。
- 记录 `actor_id`、`trace_id`、`before/after`。

## High Availability Design

### 1. 无状态 API

- FastAPI 不保存会话；access token 自校验，refresh token 存 Redis/数据库。
- 多副本前面放 Nginx/ALB，任意副本可处理任意请求。
- 健康检查：`/health`（进程存活）、`/ready`（Postgres/Redis 可用）。

### 2. 权限缓存

Redis key 设计：

```text
perm:user:{user_id}:v{permission_version} -> set<permission_code>
perm:role:{role_id}:v{permission_version} -> set<permission_code>
perm:version:{tenant_id} -> int
```

- TTL 5-15 分钟，防止永久脏数据。
- 角色/权限变更：数据库提交后 `INCR perm:version:{tenant_id}`，删除旧 key，Pub/Sub 通知所有副本清本地缓存。
- 缓存未命中时查 PostgreSQL；使用 Redis 锁/单飞避免缓存击穿。
- Redis 故障：直接回源 PostgreSQL，并打开 circuit breaker；权限判断 **fail closed**，不能因为缓存挂了就默认放行。
- 多副本本地缓存：L1 内存 30-60 秒 + L2 Redis；Pub/Sub 失效；TTL 兜底。

### 3. 数据层

- PostgreSQL 主库 + 只读副本；权限写走主库。
- 角色/权限表数据量小，可全量缓存；用户权限按用户缓存。
- `user_roles`、`role_permissions` 加唯一约束与索引。
- 迁移用 Alembic；上线先加表/字段，再双写/回填，最后切换读路径。

### 4. 降级策略

| 故障 | 行为 |
|---|---|
| Redis 不可用 | 权限回源 PostgreSQL；不 fail open；接口延迟升高但正确 |
| PostgreSQL 不可用 | 受保护接口返回 503；前端显示服务不可用，不缓存授权结果 |
| 权限缓存过期 | 回源 DB，期间请求短暂变慢 |
| 角色变更广播失败 | TTL 到期后自动纠正；同时记录告警 |
| 前端 `/auth/me` 失败 | 显示错误/重试；不沿用旧权限放行 |

### 5. Token 与会话高可用

- access token 无状态，短期有效；刷新 token 存 Redis，Redis 用 Sentinel/Cluster。
- 刷新 token 轮换 + 复用检测；登出/改密/角色变更时撤销。
- JWT 签名密钥支持轮换（kid），旧 key 保留一个 TTL。

## Migration Plan

### Phase 0：模型与契约

- 新增 `permissions`、`role_permissions`、`user_roles`、`audit_logs` 表。
- 预置权限码与三个角色：registered/operator/admin。
- 现有 `users.role` 回填到 `user_roles`。

### Phase 1：后端鉴权

- 实现 `/auth/register`、`/auth/login`、`/auth/refresh`、`/auth/logout`、`/auth/me`。
- 实现 `get_current_user` 与 `require_permission`。
- 给现有全部 `/api/v1/*` 路由加权限依赖。
- 加审计日志。

### Phase 2：前端接入

- `getInitialState` 改为真实 `/auth/me`。
- `access.ts` 改为权限码集合。
- 路由补 `access`，按钮补 `<Access>`。
- 登录页接真实 login；401 refresh；403 页面。

### Phase 3：角色权限管理 UI

- 角色管理页增加权限树/复选框。
- 用户管理支持多角色分配。
- 权限变更后刷新缓存/页签。

### Phase 4：高可用

- Redis 权限缓存、版本号、Pub/Sub、L1 缓存。
- 多副本部署、健康检查、限流、审计告警。

## Verification

### 功能

- `registered` 登录：菜单只有欢迎/个人中心/个人设置；直接访问 `/users/list` 返回 403。
- `operator` 登录：能看到 dashboard/附件/通知，看不到用户管理、部门/角色、系统设置。
- `admin` 登录：全部菜单可见。
- 按钮级：operator 看不到“新增用户/删除角色/支付设置保存”。
- 修改角色权限后，已登录用户刷新或下一次 `/auth/me` 后菜单变化；旧 access token 的权限版本失效。

### 安全

- 不带 token 调 `/api/v1/users` 返回 401。
- 带 operator token 调 `/api/v1/roles` 返回 403。
- 前端隐藏按钮但直接调接口仍被后端拒绝。

### 高可用

- 停掉一个 FastAPI 副本，请求由其他副本正常处理。
- 停掉 Redis，权限回源 PostgreSQL，接口仍正确但延迟上升。
- 角色权限变更后，多副本在 TTL/广播后行为一致。
- 数据库故障时受保护接口返回 503，不返回 200。

## 商品/订单场景：同一个后台还是分离

### 结论

**后端建议同一套领域服务 + 同一个数据库；前端建议管理端和用户端分离。**

```text
                    ┌─ Admin Web（Ant Design Pro 6）
浏览器 ─ API 网关 ──┤
                    └─ Portal Web（Next.js / Vite / H5，独立部署）
                              │
                              ▼
                    FastAPI 领域服务（同一套）
                    ├─ /api/v1/admin/*
                    └─ /api/v1/portal/*
                              │
                              ▼
                    PostgreSQL（users/products/orders/...）
```

- **不要**把商品、订单数据复制成“后台一套、用户端一套”，否则库存、订单状态、支付回调会不一致。
- **不要**让注册用户直接使用现在的 Ant Design Pro 管理端。Pro 是重后台，包体、交互、移动端体验和攻击面都不适合 C 端。
- 如果近期只是内部试用，可以先在 Pro 里加一个 `/portal` 路由组 + 独立 layout 过渡；但只要注册用户是真实 C 端，建议从第一天就拆出独立 Portal 前端。

### 为什么前端分离

1. **安全边界**：管理端有用户管理、角色、系统设置；用户端不应加载这些页面的代码和菜单。
2. **体验**：商品浏览、下单、支付、订单跟踪更适合移动端/H5，ProLayout 不适合。
3. **发布节奏**：运营后台和商城前台可以独立发布、独立扩容。
4. **Token 受众隔离**：admin token 与 portal token 使用不同 audience，防止用户端 token 调管理接口。

### 后端如何保证“注册用户只看自己的数据”

页面级权限只解决“能不能进我的订单页”，数据隔离必须由后端做四层防御：

1. **身份来源**：`current_user.id` 只从 JWT 解析，绝不信任前端传的 `user_id`。
2. **路由权限**：`require_permission("order:read:self")`。
3. **服务层 data scope**：
   - `registered` 角色：`data_scope = self`
   - `operator` 角色：`data_scope = department` 或 `all`
   - `admin` 角色：`data_scope = all`
4. **DAO 强制过滤**：

```python
async def list_my_orders(db, user_id: int, current, page_size):
    stmt = select(Order).where(Order.user_id == user_id)
    ...

async def list_all_orders(db, current, page_size):
    stmt = select(Order)
    ...
```

用户端只允许调用 `list_my_orders`；管理端才有 `list_all_orders`。不要让同一套查询同时接受“self/all”两个分支而不做权限判断。

### 权限码建议

```text
product:read            product:manage
order:read:self         order:read:all
order:create            order:manage
order:refund            order:export
```

- `registered`：`product:read`、`order:read:self`、`order:create`。
- `operator`：`product:read`、`order:read:all`、`order:manage`、`order:refund`（是否可退款按业务定）。
- `admin`：全部。

### API 命名空间

```text
/api/v1/admin/products      # 管理端商品 CRUD
/api/v1/admin/orders        # 管理端订单列表/详情/发货/退款
/api/v1/portal/products     # 用户端商品浏览
/api/v1/portal/orders       # 当前用户订单（服务端强制 user_id）
/api/v1/portal/orders/{id}  # 校验 order.user_id == current_user.id
```

`/portal` 路由使用独立的 `get_portal_user` 依赖和 `portal` token audience；`/admin` 路由使用 `get_admin_user`。两边共享领域 service，但入口和权限依赖不同。

### 高可用注意点

- 商品列表可以走 CDN/只读副本缓存；**订单列表和订单详情绝不能放共享 CDN 缓存**。
- Redis 缓存订单相关数据时 key 必须包含 `user_id`/`tenant_id`，例如 `portal:orders:{user_id}:{page}`。
- `orders` 表建 `(user_id, created_at)`、`(tenant_id, status, created_at)` 索引；管理端列表和用户端列表分开查询。
- 支付回调、库存扣减、订单状态变更走同一个领域服务，不要管理端和用户端各写一套。
- 管理端/用户端前端独立部署，后端多副本无状态；数据库和 Redis 共享。

### 推荐落地顺序

1. 先做统一认证与 `user_roles`/`data_scope`，注册用户默认 `registered`。
2. 商品先做管理端 CRUD + 用户端只读列表。
3. 订单先做用户端“我的订单” + 管理端订单列表；所有查询强制 `user_id`/`data_scope`。
4. 用户端前端从 Pro 中拆出独立 Portal；管理端继续用 Pro 6。
5. 最后再加退款、对账、导出、审计和缓存优化。

### 什么时候可以共用一个前端

只有在以下条件同时满足时可以暂时共用：

- 注册用户数量很少，且都是内部/测试用户；
- 不需要移动端体验；
- 不需要独立发布；
- 能接受 Pro 管理端包体和菜单结构。

即使共用，也必须使用独立 layout、独立路由组、独立 API 命名空间和独立权限依赖，不能和 admin 路由混在一起。

## Open Questions

1. 一个用户是单角色还是多角色？建议直接上 `user_roles` 多角色，避免二次迁移。
2. `registered` 默认能看到哪些页面？建议最小权限：欢迎页、个人中心、个人设置。
3. 是否需要部门/租户级数据权限？如果只做页面级，第一版可以不做 data_scope；如果要按部门隔离数据，需在用户/附件/通知查询中加数据范围。
4. 注册后是自动激活，还是管理员审核/邮箱验证后激活？
5. 部署目标是单机 Docker Compose，还是多副本 Kubernetes/云托管？高可用缓存和 Redis 拓扑按这个决定。
