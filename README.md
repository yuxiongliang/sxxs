# 赛霄玄思

> 多租户 C2C 商城管理后台 —— 前端、后端与数据库一体化交付。

---

## 项目简介

赛霄玄思是一套面向 **C2C 多卖家交易平台** 的运营管理后台。一个租户就是一个独立市场（同租户内可跨店下单），平台向租户收 SaaS 订阅费、向交易抽佣金并结算给卖家。

系统覆盖从注册开店、商品审核、下单支付、发货退款，到佣金结算、提现审核、SaaS 计费与审计留痕的完整链路，前端与后端在同一仓库内维护。

## 技术栈

版本以仓库内 `package.json` 与 `backend/pyproject.toml` 为准；具体第三方包名不再逐个列出，安装时以这两个清单文件为唯一依据。

### 前端

| 分层 | 选型 | 版本 |
| --- | --- | --- |
| 运行时 | Node.js | ≥ 22 |
| 框架 | Umi Max | 4.7.27 |
| 视图 | React | 19.3.1 |
| 组件库 | 企业级 React 组件库 | 6.6.7 |
| 高级组件 | ProComponents | 3.1.14 |
| 服务端状态 | TanStack React Query | 5.104.5 |
| 图表 | 图表可视化库 | 2.6.8 |
| 样式 | Tailwind CSS v4 + CSS-in-JS | 4.3.3 / 4.1.0 |
| 语言 | TypeScript | 7.0.2 |
| 构建 | Utoo Pack（Turbopack 内核） | 1.5.x |
| 规范 | Biome | 2.6.3 |
| 测试 | Vitest / Playwright | 5.0.5 / 1.64.1 |

### 后端

| 分层 | 选型 | 版本 |
| --- | --- | --- |
| 运行时 | Python | ≥ 3.12 |
| Web 框架 | FastAPI | 0.162 |
| ASGI | Uvicorn | 0.41 |
| ORM | SQLAlchemy（async） | 2.1 |
| 校验 | Pydantic / pydantic-settings | 2.14 / 2.16 |
| 迁移 | Alembic | 1.20 |
| 驱动 | asyncpg | 0.32 |
| 缓存/消息 | Redis | 6.x |
| 认证 | PyJWT + pwdlib[argon2] | 2.15 / 0.3 |
| 日志 | structlog | 26.1 |
| 测试 | pytest + pytest-asyncio + httpx | — |

### 数据与基础设施

| 项 | 说明 |
| --- | --- |
| 数据库 | PostgreSQL 18（默认 `127.0.0.1:5433`），**38 张表**，**6 个 Alembic 迁移** |
| 缓存 / 发号 | Redis（刷新令牌、权限快照、限流计数、IM 事件总线） |
| 反向代理 | Nginx（生产环境统一同源：前端静态资源 + `/api/v1` + `/_AMapService`） |

## 系统架构

```text
┌──────────────────────────────────────────────────────────────┐
│                        浏览器（同源）                          │
│  管理后台 / 买家商城 / 店主工作台    同一套前端，按权限与开店状态切换  │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTPS
┌───────────────────────────▼──────────────────────────────────┐
│                       FastAPI 应用                            │
│                                                              │
│  api/v1         路由层：参数校验、权限依赖、统一响应封装            │
│    │                                                         │
│  services       业务层：认证、权限、订单、财务、计费、IM、审计       │
│    │                                                         │
│  dao            数据访问层：单表 CRUD                          │
│    │                                                         │
│  models / schemas   ORM 实体 与 出入参 DTO                      │
│                                                              │
│  横切：限流中间件 · 请求上下文(trace_id/IP) · 全局异常处理          │
└───────┬───────────────────────────────┬──────────────────────┘
        │                               │
   ┌────▼─────┐                  ┌──────▼──────┐        ┌──────────────┐
   │PostgreSQL│                  │    Redis    │        │ 高德地图 API  │
   │  38 张表  │                  │ 缓存/总线/限流│        │ 逆地理/静态图  │
   └──────────┘                  └─────────────┘        └──────────────┘
```

### 请求链路

1. 浏览器发起请求（开发环境经 Umi 代理转发到 `127.0.0.1:9000`）
2. 限流中间件按「客户端 IP + 作用域」计数（认证接口独立阈值）
3. 请求上下文中间件注入 `trace_id` 与客户端 IP，供审计落库
4. 路由层通过 `require_permission` 校验权限码，解析出租户上下文
5. 业务层完成校验与编排，DAO 落库，审计与业务**同事务**提交
6. 统一响应封套返回 `{code, message, data}`，响应头回写 `X-Trace-Id`

### 多租户与权限模型

```text
Tenant（租户/市场）
  └─ TenantMember（全局用户在某租户内的成员身份）
       └─ MemberRole ── Role ── RolePermission ── Permission（权限码）
```

- **全局用户 + 租户成员**：同一邮箱可在多个租户成为成员，互不影响。
- **权限码**按 `模块:动作` 命名（如 `order:manage`、`platform:tenant:manage`），前端 `access.ts` 与后端 `require_permission` 共用同一套码。
- **平台级权限**独立于租户角色：`platform:tenant:read/manage` 只授予平台管理员，避免租户主越权开通租户。
- **数据隔离**：所有业务查询强制携带 `tenant_id`，跨租户访问返回 404 而非 403（不泄露资源是否存在）。
- **权限缓存**：按 `perm:{tenant}:{user}:v{permission_version}` 缓存；改角色、改成员角色、删用户都会递增版本使缓存失效。

## 功能模块

| 模块 | 能力 |
| --- | --- |
| 认证与 RBAC | JWT 登录/刷新/登出、argon2 口令、权限码依赖、前端菜单与路由双层门禁 |
| 多租户 | 租户开通、成员与角色、跨租户隔离、租户停用即全接口 fail-closed |
| 卖家中心 | 买家自助申请开店 → 平台审核 → 商品上架、发货、申请结算（同一套买家入口内） |
| 商品 | 分类、SKU、库存占用/释放、主图上传、上架审核 |
| 订单履约 | 按卖家拆单、服务端算价、支付/取消/发货/退款/确认收货、库存回滚 |
| 即时通讯 | WebSocket 实时消息、已读回执、图片消息、举报与违规下架、Redis Pub/Sub 多实例广播 |
| 财务 | 可配置佣金规则（卖家/分类/账期/优先级）、三桶余额、提现审核状态机、结算批次 |
| SaaS 计费 | 套餐、订阅、账单、用量配额、功能开关、自动续费与欠费降级定时任务 |
| 审计 | 23+ 类动作全链路留痕，业务与审计同事务，支持差异快照与 trace 关联 |
| 经营看板 | 今日/环比 KPI、GMV 趋势、订单状态分布、热销商品、套餐用量 |
| 地图 | 高德 JS API 2.0 交互地图 + 后端 Web 服务（逆地理/静态地图），安全密钥走服务端代理 |
| 系统设置 | 支付 / 短信 / 邮件 / 存储 / 高德地图 五类配置与连通性测试 |

## 目录结构

```text
.
├── src/                     前端源码
│   ├── pages/               页面：dashboard / commerce / im / platform / portal / system ...
│   ├── services/            按域拆分的接口层（auth / commerce / im / platform / system / amap）
│   ├── components/          公共组件（PageTabs / AttachmentUpload / AMapView ...）
│   ├── access.ts            权限与套餐功能门禁
│   └── app.tsx              运行时配置：登录态、请求、布局、菜单过滤
├── config/                  Umi 配置：路由、主题、代理、构建
├── backend/                 FastAPI 后端
│   ├── app/api/v1/          路由层
│   ├── app/services/        业务层
│   ├── app/dao/             数据访问层
│   ├── app/models/          ORM 实体（38 张表）
│   ├── app/schemas/         出入参 DTO
│   ├── migrations/          Alembic 迁移（6 个版本）
│   ├── tests/               19 个测试模块
│   └── scripts/             运维脚本（建租户、生成迁移）
├── docs/                    运维手册与技术说明
├── plans/                   架构与阶段性方案
└── e2e/                     Playwright 端到端用例
```

## 快速开始

### 前置依赖

- Node.js ≥ 22、npm 10+
- Python ≥ 3.12 与 [uv](https://docs.astral.sh/uv/)
- PostgreSQL 18（默认端口 5433）、Redis 7

### 后端

```bash
cd backend
cp .env.example .env          # 按需修改数据库/Redis 连接与 JWT 密钥
uv sync --group dev
uv run alembic upgrade head   # 建表（迁移为主权，不依赖 create_all）
uv run uvicorn app.main:app --host 127.0.0.1 --port 9000
```

启动后请**立即修改**默认演示账号口令，或在 `.env` 中覆盖种子口令。

- OpenAPI 文档：http://127.0.0.1:9000/docs
- 健康检查：http://127.0.0.1:9000/health

### 前端

```bash
npm install
npm start        # http://localhost:8000，开发代理把 /api/v1 转到后端
```

生产构建：

```bash
npm run build
API_BASE_URL=http://127.0.0.1:9000 npm run build && npx max preview --port 8002
```

## 质量门禁

| 门禁 | 命令 | 当前状态 |
| --- | --- | --- |
| 后端测试 | `cd backend && uv run pytest tests/` | **261 通过 / 1 跳过** |
| 后端静态检查 | `uvx ruff check app tests migrations` | 通过 |
| 后端类型检查 | `uvx pyright app tests` | 0 errors |
| 前端类型检查 | `npm run tsc` | 通过 |
| 前端规范 | `npm run biome:lint` | 0 errors |
| 纯逻辑单测 | `npm run test:node` | 16 通过 |
| 端到端 | `npm run e2e:regression` | 需同时启动前后端与服务依赖 |
| CI | `.github/workflows/admin-console.yml` | 后端（Postgres+Redis 服务）+ 前端双 Job |

## 相关文档

- 运维与接口速查：[docs/admin-console.md](./docs/admin-console.md)
- 架构与阶段性方案：[plans/](./plans)
- 接口契约：运行后端后访问 `/docs`（OpenAPI）

## 说明

本项目界面层构建在开源中后台组件体系之上，相关第三方代码的版权与许可声明保留在 [LICENSE](./LICENSE) 中，请勿删除。外层业务代码（多租户、交易、财务、计费、IM、审计等）为本项目自有实现。
