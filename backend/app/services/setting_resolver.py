"""配置继承解析：租户配置与平台配置的**唯一**取值出口。

解析优先级（顺序不能变）：
  1. 租户显式自定义（source=override）              → 用租户配置
  2. 平台已启用该分类（platform.enabled=True）      → 用平台配置
  3. 平台未配置但租户有历史配置                      → **回落租户配置**
     （这一步是安全网：平台没填就切 inherit，不会让全站支付/邮件立刻挂）
  4. 代码默认值                                      → 兜底

密钥规则：
  * 租户响应**必须脱敏**（跟随系统时绝不返回平台私钥）
  * 平台响应不脱敏（平台管理员要能编辑自己的 key）
  * 后端内部（发邮件/调支付/调高德）取**未脱敏**的生效配置
"""

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.setting import SystemSetting
from app.services import platform_setting as platform_setting_service
from app.services.setting import DEFAULT_SETTINGS

INHERIT = "inherit"
OVERRIDE = "override"
FORCED_INHERIT = "forced_inherit"
TENANT_CHOOSABLE = {INHERIT, OVERRIDE}

# 平台只收 SaaS 订阅费，不代收租户业务款 —— 所以支付配置不允许「跟随系统」
INHERIT_FORBIDDEN = {"payment"}

# 各类配置里哪些字段是密钥（租户侧必须脱敏）
SECRET_PATHS: dict[str, tuple[str, ...]] = {
    "payment": (
        "alipay.privateKey",
        "alipay.publicKey",
        "wechat.apiV3Key",
        "wechat.privateKey",
    ),
    "sms": ("accessKeyId", "accessKeySecret"),
    "email": ("password",),
    "storage": ("oss.accessKeyId", "oss.accessKeySecret"),
    # 高德的 jsKey / securityCode 本来就下发给浏览器（有域名白名单限制），
    # 遮掉它们会让地图直接渲染不出来；只有服务端 REST 用的 webKey 必须遮。
    "amap": ("webKey",),
}

MASK = "******"


@dataclass
class ResolvedSetting:
    category: str
    source: str  # 租户选择的来源
    effective_source: str  # 实际生效的来源（inherit/override/default）
    enabled: bool
    config: dict  # 生效配置（按需脱敏）
    masked_fields: list[str] = field(default_factory=list)
    platform_active: bool = False
    platform_updated_at: datetime | None = None
    policy_locked: bool = False
    inherit_allowed: bool = True
    tenant_config: dict | None = None
    platform_config: dict | None = None


def _get_path(config: dict, path: str):
    current = config
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _set_path(config: dict, path: str, value) -> None:
    parts = path.split(".")
    current = config
    for part in parts[:-1]:
        node = current.get(part)
        if not isinstance(node, dict):
            return
        current = node
    if parts[-1] in current:
        current[parts[-1]] = value


def mask_secrets(category: str, config: dict) -> tuple[dict, list[str]]:
    """把密钥字段替换成占位符，并返回被遮罩的字段路径。"""
    masked = deepcopy(config or {})
    hit: list[str] = []
    for path in SECRET_PATHS.get(category, ()):
        value = _get_path(masked, path)
        if value:
            _set_path(masked, path, MASK)
            hit.append(path)
    return masked, hit


async def _tenant_row(db: AsyncSession, tenant_id: int, category: str) -> SystemSetting | None:
    return (
        await db.scalars(
            select(SystemSetting).where(
                SystemSetting.tenant_id == tenant_id,
                SystemSetting.category == category,
            )
        )
    ).first()


async def resolve(
    db: AsyncSession,
    tenant_id: int,
    category: str,
    *,
    mask_secrets_in_response: bool = True,
) -> ResolvedSetting:
    """解析某租户某分类的生效配置。**所有读取配置的地方都必须走这里。**"""
    if category not in DEFAULT_SETTINGS:
        raise HTTPException(status_code=404, detail="未知的设置分类")

    tenant_row = await _tenant_row(db, tenant_id, category)
    platform_row = await platform_setting_service.get_platform_setting(db, category)

    tenant_config = dict(tenant_row.config or {}) if tenant_row else None
    platform_config = dict(platform_row.config or {})
    policy_locked = bool(platform_row.policy_locked)

    source = (tenant_row.source if tenant_row else INHERIT) or INHERIT
    if policy_locked:
        source = FORCED_INHERIT
    if category in INHERIT_FORBIDDEN:
        # 支付必须自填：平台不代收，跟随系统会让钱进错账户
        source = OVERRIDE

    if source == OVERRIDE and tenant_config is not None:
        effective, effective_source, enabled = (
            tenant_config,
            OVERRIDE,
            bool(tenant_row.enabled) if tenant_row else True,
        )
    elif platform_row.enabled:
        effective, effective_source, enabled = (
            platform_config,
            INHERIT,
            True,
        )
    elif tenant_config:
        # 安全网：平台未启用时回落租户自己的历史配置。
        # 标成 tenant_fallback 而不是 override —— 否则 UI 无法解释
        # 「我明明选了跟随系统，怎么用的是自己的配置」。
        effective, effective_source, enabled = (
            tenant_config,
            "tenant_fallback",
            bool(tenant_row.enabled) if tenant_row else True,
        )
    else:
        default = DEFAULT_SETTINGS[category]
        effective, effective_source, enabled = (
            deepcopy(default["config"]),
            "default",
            bool(default["enabled"]),
        )

    masked_fields: list[str] = []
    response_config = deepcopy(effective)
    if mask_secrets_in_response and effective_source == INHERIT:
        response_config, masked_fields = mask_secrets(category, response_config)

    return ResolvedSetting(
        category=category,
        source=source,
        effective_source=effective_source,
        enabled=enabled,
        config=response_config,
        masked_fields=masked_fields,
        platform_active=bool(platform_row.enabled),
        platform_updated_at=platform_row.updated_at,
        policy_locked=policy_locked,
        inherit_allowed=category not in INHERIT_FORBIDDEN and not policy_locked,
        tenant_config=tenant_config,
        platform_config=platform_config,
    )


async def resolve_for_runtime(db: AsyncSession, tenant_id: int, category: str) -> dict:
    """后端内部使用：要的是**未脱敏**的真实生效配置。"""
    resolved = await resolve(db, tenant_id, category, mask_secrets_in_response=False)
    return resolved.config


async def set_source(
    db: AsyncSession,
    tenant_id: int,
    category: str,
    *,
    source: str,
    enabled: bool,
    config: dict | None,
    user_id: int | None,
) -> SystemSetting:
    """租户切换来源 / 保存自定义配置。"""
    if category not in DEFAULT_SETTINGS:
        raise HTTPException(status_code=404, detail="未知的设置分类")
    if source not in TENANT_CHOOSABLE:
        raise HTTPException(status_code=400, detail="来源只能是 inherit 或 override")
    if source == INHERIT and category in INHERIT_FORBIDDEN:
        raise HTTPException(
            status_code=400,
            detail="该配置不支持跟随系统，请填写自己的账号",
        )

    platform_row = await platform_setting_service.get_platform_setting(db, category)
    if platform_row.policy_locked and source == OVERRIDE:
        raise HTTPException(status_code=403, detail="平台已锁定该配置，不允许自定义")

    row = await _tenant_row(db, tenant_id, category)
    if row is None:
        row = SystemSetting(
            tenant_id=tenant_id,
            category=category,
            enabled=enabled,
            config=config or {},
            source=source,
            updated_by=user_id,
        )
        db.add(row)
    else:
        row.source = source
        row.enabled = enabled
        if config is not None:
            # 只切换来源时保留原有配置（避免被脱敏占位符覆盖）
            row.config = config
        row.updated_by = user_id
    await db.commit()
    await db.refresh(row)
    return row
