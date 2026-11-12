from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.permission import MemberRole, Permission, RolePermission
from app.models.role import Role
from app.models.tenant import Tenant, TenantMember
from app.models.user import User

DEMO_TENANT_SLUG = "demo"

# Only these seeded accounts belong to the demo tenant by default. Backfilling
# membership for *every* row in ``users`` (the previous behaviour) silently made
# users of other tenants -- including their ``tenant_owner`` -- members of the
# demo tenant with full rights on every restart.
DEMO_TENANT_USERNAMES = frozenset({"admin", "lisi", "wangwu", "zhaoliu", "chenqi"})

PERMISSIONS = [
    ("profile:read", "查看个人资料", "profile", "read"),
    ("profile:update", "修改个人资料", "profile", "update"),
    ("dashboard:read", "查看 Dashboard", "dashboard", "read"),
    ("setting:amap", "配置高德地图", "setting", "amap"),
    ("amap:read", "使用地图服务", "amap", "read"),
    ("user:read", "查看用户", "user", "read"),
    ("user:write", "管理用户", "user", "write"),
    ("department:read", "查看部门", "department", "read"),
    ("department:manage", "管理部门", "department", "manage"),
    ("role:read", "查看角色", "role", "read"),
    ("role:manage", "管理角色", "role", "manage"),
    ("seller:apply", "申请成为卖家", "seller", "apply"),
    ("seller:read", "查看卖家", "seller", "read"),
    ("seller:manage", "管理卖家", "seller", "manage"),
    ("seller:kyc", "审核卖家", "seller", "kyc"),
    ("product:read", "查看商品", "product", "read"),
    ("product:manage", "管理商品", "product", "manage"),
    ("product:moderate", "审核商品", "product", "moderate"),
    ("order:read:self", "查看自己的订单", "order", "read_self"),
    ("order:read:seller", "查看卖家订单", "order", "read_seller"),
    ("order:read:tenant", "查看租户订单", "order", "read_tenant"),
    ("order:read:all", "查看全部订单", "order", "read_all"),
    ("order:create", "创建订单", "order", "create"),
    ("order:manage", "管理订单", "order", "manage"),
    ("order:refund", "订单退款", "order", "refund"),
    ("order:export", "导出订单", "order", "export"),
    ("payment:read", "查看支付", "payment", "read"),
    ("payment:manage", "管理支付", "payment", "manage"),
    ("payout:read", "查看结算", "payout", "read"),
    ("payout:manage", "管理结算", "payout", "manage"),
    ("commission:read", "查看佣金", "commission", "read"),
    ("commission:manage", "管理佣金", "commission", "manage"),
    ("dispute:read", "查看纠纷", "dispute", "read"),
    ("dispute:manage", "处理纠纷", "dispute", "manage"),
    ("review:read", "查看评价", "review", "read"),
    ("review:moderate", "审核评价", "review", "moderate"),
    ("im:conversation:read", "查看会话", "im", "conversation_read"),
    ("im:message:send", "发送消息", "im", "message_send"),
    ("im:moderate", "审核会话", "im", "moderate"),
    ("im:support", "客服会话", "im", "support"),
    ("attachment:read", "查看附件", "attachment", "read"),
    ("attachment:upload", "上传附件", "attachment", "upload"),
    ("attachment:delete", "删除附件", "attachment", "delete"),
    ("notification:read", "查看通知", "notification", "read"),
    ("notification:send", "发送通知", "notification", "send"),
    ("setting:payment", "支付设置", "setting", "payment"),
    ("setting:sms", "短信设置", "setting", "sms"),
    ("setting:email", "邮件设置", "setting", "email"),
    ("setting:storage", "存储设置", "setting", "storage"),
    ("audit:read", "查看审计", "audit", "read"),
    # Platform-scoped permissions are intentionally *not* granted to any tenant
    # role. Only platform_admin (and the legacy demo `admin`) may cross tenants.
    ("im:report", "举报违规消息", "im", "report"),
    ("cart:read", "查看购物车", "cart", "read"),
    ("cart:manage", "管理购物车", "cart", "manage"),
    ("address:read", "查看收货地址", "address", "read"),
    ("address:manage", "管理收货地址", "address", "manage"),
    ("tenant:brand:manage", "维护站点品牌", "tenant", "brand_manage"),
    ("platform:tenant:read", "查看平台租户", "platform", "read"),
    ("platform:tenant:manage", "开通/管理平台租户", "platform", "manage"),
    ("platform:setting:read", "查看平台配置", "platform", "setting_read"),
    ("platform:setting:manage", "管理平台配置", "platform", "setting_manage"),
    ("platform:audit:read", "查看跨租户审计", "platform", "audit_read"),
    ("platform:notification:manage", "管理通知模板", "platform", "notification_manage"),
    ("platform:attachment:view", "查看全站附件", "platform", "attachment_view"),
    ("platform:attachment:review", "审核附件内容", "platform", "attachment_review"),
    ("platform:attachment:takedown", "强制下架附件", "platform", "attachment_takedown"),
]

ROLE_DEFINITIONS = [
    ("admin", "管理员", "兼容旧版管理员角色", 0),
    ("platform_admin", "平台管理员", "平台级管理员", 1),
    ("platform_support", "平台客服", "平台级只读客服", 2),
    ("tenant_owner", "市场所有者", "租户市场所有者", 10),
    ("tenant_admin", "市场管理员", "租户市场管理员", 11),
    ("operator", "运营人员", "市场运营人员", 12),
    ("viewer", "只读人员", "市场只读人员", 13),
    ("seller_owner", "卖家所有者", "C2C 卖家所有者", 20),
    ("seller_staff", "卖家员工", "C2C 卖家员工", 21),
    ("customer", "买家", "C2C 注册买家", 30),
]

ROLE_PERMISSIONS = {
    "admin": [code for code, *_ in PERMISSIONS],
    # 平台管理员只持有 platform:* 权限。租户业务权限一个都不给：
    # 它登录的是独立平台端，拿的是 aud=platform 的 token，本就进不了租户接口。
    "platform_admin": [code for code, *_ in PERMISSIONS if code.startswith("platform:")],
    "platform_support": [
        "dashboard:read",
        "user:read",
        "seller:read",
        "product:read",
        "order:read:all",
        "audit:read",
        "platform:tenant:read",
    ],
    "tenant_owner": [
        "tenant:brand:manage",
        "dashboard:read",
        "user:read",
        "user:write",
        "department:read",
        "department:manage",
        "role:read",
        "role:manage",
        "seller:read",
        "seller:manage",
        "seller:kyc",
        "product:read",
        "product:manage",
        "product:moderate",
        "order:read:tenant",
        "order:manage",
        "order:refund",
        "order:export",
        "payment:read",
        "payment:manage",
        "payout:read",
        "payout:manage",
        "commission:read",
        "commission:manage",
        "dispute:read",
        "dispute:manage",
        "review:read",
        "review:moderate",
        "im:conversation:read",
        "im:moderate",
        "im:support",
        "attachment:read",
        "attachment:upload",
        "attachment:delete",
        "notification:read",
        "notification:send",
        "setting:payment",
        "setting:sms",
        "setting:email",
        "setting:storage",
        "audit:read",
    ],
    "tenant_admin": [
        "dashboard:read",
        "user:read",
        "user:write",
        "department:read",
        "department:manage",
        "role:read",
        "role:manage",
        "seller:read",
        "seller:manage",
        "seller:kyc",
        "product:read",
        "product:manage",
        "product:moderate",
        "order:read:tenant",
        "order:manage",
        "order:refund",
        "order:export",
        "payment:read",
        "payout:read",
        "payout:manage",
        "commission:read",
        "commission:manage",
        "dispute:read",
        "dispute:manage",
        "review:read",
        "review:moderate",
        "im:conversation:read",
        "im:moderate",
        "im:support",
        "attachment:read",
        "attachment:upload",
        "attachment:delete",
        "notification:read",
        "notification:send",
        "setting:payment",
        "setting:sms",
        "setting:email",
        "setting:storage",
        "audit:read",
    ],
    "operator": [
        "dashboard:read",
        "user:read",
        "seller:read",
        "seller:manage",
        "seller:kyc",
        "product:read",
        "product:moderate",
        "order:read:tenant",
        "order:manage",
        "order:refund",
        "dispute:read",
        "dispute:manage",
        "review:read",
        "review:moderate",
        "im:conversation:read",
        "im:moderate",
        "im:report",
        "attachment:read",
        "attachment:upload",
        "notification:read",
        "notification:send",
    ],
    "viewer": [
        "dashboard:read",
        "user:read",
        "seller:read",
        "product:read",
        "order:read:tenant",
        "dispute:read",
        "review:read",
    ],
    "seller_owner": [
        "seller:read",
        "seller:manage",
        "product:read",
        "product:manage",
        "order:read:seller",
        "order:manage",
        "payout:read",
        "commission:read",
        "dispute:read",
        "review:read",
        "im:conversation:read",
        "im:message:send",
        "attachment:read",
        "attachment:upload",
        "attachment:delete",
        "notification:read",
    ],
    "seller_staff": [
        "seller:read",
        "product:read",
        "order:read:seller",
        "im:conversation:read",
        "im:message:send",
        "attachment:read",
        "attachment:upload",
        "notification:read",
    ],
    "customer": [
        "im:report",
        "cart:read",
        "cart:manage",
        "address:read",
        "address:manage",
        "profile:read",
        "profile:update",
        # 注意：C 端买家**不得**持有 dashboard:read —— 经营看板会聚合同租户的
        # GMV、订单、提现、商品排行，属于租户内部经营数据（计划 §18 #4）。
        "product:read",
        "order:read:self",
        "order:create",
        "im:conversation:read",
        "im:message:send",
        "attachment:upload",
        "seller:apply",
    ],
}


# 高德地图：除 admin/platform_admin（自动拿到全部权限）外，管理端角色都需要这两项。
for _amap_role in ("tenant_owner", "tenant_admin", "operator", "viewer"):
    for _amap_code in ("setting:amap", "amap:read"):
        if _amap_role in ROLE_PERMISSIONS and _amap_code not in ROLE_PERMISSIONS[_amap_role]:
            ROLE_PERMISSIONS[_amap_role].append(_amap_code)

# 绝不允许存在的授权：即使老库已经写入过，启动时也要清掉。
# 与 `_prune_foreign_tenant_owners()` 同一思路 —— 只针对已知的越权组合，
# 不做「与代码不一致就删」的粗暴归一化，以免抹掉运营在 UI 上自定义的授权。
FORBIDDEN_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "customer": {"dashboard:read"},
}


async def _prune_forbidden_role_permissions(db: AsyncSession) -> int:
    """删除历史库里已经写脏的越权授权，返回清理条数。"""
    removed = 0
    for role_code, permission_codes in FORBIDDEN_ROLE_PERMISSIONS.items():
        role = (await db.scalars(select(Role).where(Role.code == role_code))).first()
        if role is None:
            continue
        for permission_code in sorted(permission_codes):
            permission = (
                await db.scalars(select(Permission).where(Permission.code == permission_code))
            ).first()
            if permission is None:
                continue
            stale = (
                await db.scalars(
                    select(RolePermission).where(
                        RolePermission.role_id == role.id,
                        RolePermission.permission_id == permission.id,
                    )
                )
            ).first()
            if stale is not None:
                await db.delete(stale)
                removed += 1
    if removed:
        await db.flush()
    return removed


# 平台管理员账号：不绑定任何租户，只用于「赛霄玄思 SaaS 管理平台」。
PLATFORM_ADMIN_USERNAME = "root"
PLATFORM_ADMIN_PASSWORD = "Sxxs@Platform2026"
PLATFORM_ADMIN_EMAIL = "root@saixiao.local"


async def seed_auth_data(db: AsyncSession) -> None:
    tenant = (await db.scalars(select(Tenant).where(Tenant.slug == DEMO_TENANT_SLUG))).first()
    if tenant is None:
        tenant = Tenant(name="Demo C2C Marketplace", slug=DEMO_TENANT_SLUG, status="active")
        db.add(tenant)
        await db.flush()

    roles = {}
    for code, name, description, sort in ROLE_DEFINITIONS:
        role = (await db.scalars(select(Role).where(Role.code == code))).first()
        if role is None:
            role = Role(code=code, name=name, description=description, status="active", sort=sort)
            db.add(role)
            await db.flush()
        roles[code] = role

    permissions = {}
    for code, name, module, action in PERMISSIONS:
        permission = (await db.scalars(select(Permission).where(Permission.code == code))).first()
        if permission is None:
            permission = Permission(code=code, name=name, module=module, action=action)
            db.add(permission)
            await db.flush()
        permissions[code] = permission

    existing_role_permissions: set[tuple[int, int]] = {
        (row[0], row[1])
        for row in (
            await db.execute(select(RolePermission.role_id, RolePermission.permission_id))
        ).all()
    }
    for role_code, permission_codes in ROLE_PERMISSIONS.items():
        role = roles[role_code]
        for permission_code in permission_codes:
            permission = permissions[permission_code]
            key = (role.id, permission.id)
            if key not in existing_role_permissions:
                db.add(RolePermission(role_id=role.id, permission_id=permission.id))
                existing_role_permissions.add(key)

    await _prune_forbidden_role_permissions(db)

    users = list(
        (
            await db.scalars(select(User).where(User.username.in_(sorted(DEMO_TENANT_USERNAMES))))
        ).all()
    )
    for user in users:
        member = (
            await db.scalars(
                select(TenantMember).where(
                    TenantMember.tenant_id == tenant.id,
                    TenantMember.user_id == user.id,
                )
            )
        ).first()
        if member is None:
            member = TenantMember(tenant_id=tenant.id, user_id=user.id, status=user.status)
            db.add(member)
            await db.flush()
        role_code = user.role if user.role in roles else "viewer"
        member_role = (
            await db.scalars(
                select(MemberRole).where(
                    MemberRole.member_id == member.id,
                    MemberRole.role_id == roles[role_code].id,
                )
            )
        ).first()
        if member_role is None:
            db.add(MemberRole(member_id=member.id, role_id=roles[role_code].id))
        if user.password_hash is None:
            user.password_hash = hash_password(
                "ant.design" if user.username == "admin" else "Antd@123456"
            )

    await _prune_foreign_tenant_owners(db, tenant)

    await db.commit()


async def seed_platform_admin(db: AsyncSession) -> None:
    """创建平台管理员账号。

    必须在 demo 用户创建 *之后* 调用：`seed_demo_data()` 用
    `if user_count == 0` 来判断是否要建 demo 用户，若平台账号先插进去，
    计数就不为 0，demo 用户会被整块跳过（admin 登录直接 401）。

    平台账号刻意不创建 TenantMember：平台身份与租户身份完全解耦。
    """
    platform_user = (
        await db.scalars(select(User).where(User.username == PLATFORM_ADMIN_USERNAME))
    ).first()
    if platform_user is None:
        platform_user = User(
            username=PLATFORM_ADMIN_USERNAME,
            nickname="平台管理员",
            email=PLATFORM_ADMIN_EMAIL,
            role="platform_admin",
            status="active",
            is_platform_admin=True,
            password_hash=hash_password(PLATFORM_ADMIN_PASSWORD),
        )
        db.add(platform_user)
        await db.flush()
        return
    # 已存在则确保它仍是可用的平台账号（幂等重跑）
    platform_user.is_platform_admin = True
    platform_user.status = "active"
    if platform_user.password_hash is None:
        platform_user.password_hash = hash_password(PLATFORM_ADMIN_PASSWORD)


async def _prune_foreign_tenant_owners(db: AsyncSession, demo_tenant: Tenant) -> None:
    """Drop demo-tenant memberships wrongly granted to other tenants' owners.

    A ``tenant_owner`` account is created together with the tenant it owns, so it
    must never hold a membership in the demo tenant. Older seed runs backfilled a
    membership for *every* row in ``users`` and did exactly that; the bad rows are
    removed here so the isolation invariant holds again after an upgrade.
    """
    foreign_owners = list(
        (
            await db.scalars(
                select(User).where(
                    User.role == "tenant_owner",
                    User.username.notin_(sorted(DEMO_TENANT_USERNAMES)),
                )
            )
        ).all()
    )
    if not foreign_owners:
        return
    owner_ids = [user.id for user in foreign_owners]
    members = list(
        (
            await db.scalars(
                select(TenantMember).where(
                    TenantMember.tenant_id == demo_tenant.id,
                    TenantMember.user_id.in_(owner_ids),
                )
            )
        ).all()
    )
    for member in members:
        for link in (
            await db.scalars(select(MemberRole).where(MemberRole.member_id == member.id))
        ).all():
            await db.delete(link)
        await db.delete(member)
    if members:
        await db.flush()
