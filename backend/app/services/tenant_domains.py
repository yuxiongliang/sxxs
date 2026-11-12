"""Host → 租户（B6 自定义域名）。

解析顺序（先命中先赢）：

1. 请求 Host 命中 tenant_domains 里 status=active 的域名，且租户本身也是 active；
2. 兜底：?tenant=<slug>，再退到默认 demo 租户 —— 只在 settings.tenant_host_fallback
   打开时生效。

兜底为什么必须能关：线上把「不认识的域名」静默当成 demo 站，会让租户以为域名已经
生效，而买家实际看到的是别人的站点。这类错误必须 404 暴露，不能猜。

Host 只决定「读哪个租户的公开站点」，绝不参与授权判定 —— 授权只看 JWT
（app/api/deps.py）。Host 头是可以伪造的。
"""

from __future__ import annotations

import ipaddress
import secrets
from datetime import UTC, datetime

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.tenant import Tenant, TenantDomain
from app.services import domain_verifier
from app.services.public_catalog import DEFAULT_TENANT_SLUG, resolve_tenant

MAX_HOST_LENGTH = 253
VERIFY_RECORD_PREFIX = '_sxxs-verify'
VERIFY_VALUE_PREFIX = 'sxxs-verify='
DOMAIN_KINDS = frozenset({'subdomain', 'custom'})
LOCAL_HOSTS = frozenset({'localhost', '127.0.0.1', '0.0.0.0', '::1'})


class TenantDomainError(Exception):
    """域名操作的业务错误；映射成 HTTP 状态码是 API 层的事。"""


class InvalidHostError(TenantDomainError):
    pass


class ReservedHostError(TenantDomainError):
    pass


class DomainConflictError(TenantDomainError):
    pass


class DomainNotFoundError(TenantDomainError):
    pass


def normalize_host(value: str | None) -> str:
    """把 Host 头或用户输入规整成可比较的形式。

    * 去掉端口与路径；小写；去掉结尾的点（demo.example.com. 是合法 FQDN）；
    * 非 ASCII 域名转 punycode —— 否则「例え.jp」和 xn-- 形式会被当成两个域名。
    """
    host = (value or '').strip().lower()
    if not host:
        return ''
    if host.startswith('['):  # IPv6 字面量：[::1]:8000
        return host[1 : host.index(']')] if ']' in host else host
    host = host.split('/', 1)[0].rsplit(':', 1)[0].rstrip('.')
    if not host:
        return ''
    try:
        return host.encode('idna').decode('ascii')
    except UnicodeError as exc:
        raise InvalidHostError('域名格式不合法') from exc


def normalize_request_host(value: str | None) -> str:
    """请求路径专用：Host 头畸形时返回空串，让调用方走兜底/404，而不是抛 500。"""
    try:
        return normalize_host(value)
    except InvalidHostError:
        return ''


def is_reserved_host(host: str) -> bool:
    """基础设施自己的 host 不允许绑给租户。"""
    if not host or host in LOCAL_HOSTS:
        return True
    if settings.platform_host and host == normalize_host(settings.platform_host):
        return True
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def verification_record_name(host: str) -> str:
    """TXT 记录挂在 _sxxs-verify.<host>：不占用对方主域的其他记录。"""
    return f'{VERIFY_RECORD_PREFIX}.{host}'


def verification_value(token: str) -> str:
    return f'{VERIFY_VALUE_PREFIX}{token}'


async def tenant_by_host(db: AsyncSession, host: str) -> Tenant | None:
    """按 Host 找租户：域名 active 且租户 active 才算命中。"""
    if not host:
        return None
    return (
        await db.scalars(
            select(Tenant)
            .join(TenantDomain, TenantDomain.tenant_id == Tenant.id)
            .where(
                TenantDomain.host == host,
                TenantDomain.status == 'active',
                Tenant.status == 'active',
            )
        )
    ).first()


async def resolve_public_tenant(
    db: AsyncSession, request: Request, slug_hint: str | None = None
) -> Tenant:
    """公开接口的租户解析：Host 优先，兜底可关；解析不出来一律 404（不泄露存在性）。"""
    tenant = await tenant_by_host(db, normalize_request_host(request.headers.get('host')))
    if tenant is not None:
        return tenant
    if not settings.tenant_host_fallback:
        raise HTTPException(status_code=404, detail='站点不存在或已停用')
    slug = (slug_hint or '').strip() or DEFAULT_TENANT_SLUG
    return await resolve_tenant(db, slug)


def _validate_host(host: str, tenant: Tenant, kind: str) -> str:
    if not host:
        raise InvalidHostError('域名不能为空')
    if len(host) > MAX_HOST_LENGTH:
        raise InvalidHostError('域名过长')
    if is_reserved_host(host):
        raise ReservedHostError('该域名属于基础设施，不能绑定给租户')
    if '.' not in host:
        raise InvalidHostError('需要完整域名（含后缀）')
    if kind == 'subdomain':
        base = normalize_host(settings.tenant_base_domain)
        if not base:
            raise InvalidHostError('未配置 tenant_base_domain，无法创建子域')
        if host != f'{tenant.slug}.{base}':
            raise InvalidHostError('子域只允许形如 <slug>.<租户基域>')
    return host


async def add_domain(
    db: AsyncSession, tenant: Tenant, host: str, kind: str = 'custom'
) -> TenantDomain:
    """新增域名。子域创建即 active；自定义域名停在 pending 等 TXT 验证。"""
    if kind not in DOMAIN_KINDS:
        raise InvalidHostError('域名类型不合法')
    normalized = _validate_host(normalize_host(host), tenant, kind)
    existing = (
        await db.scalars(select(TenantDomain).where(TenantDomain.host == normalized))
    ).first()
    if existing is not None:
        raise DomainConflictError('该域名已被占用')

    is_subdomain = kind == 'subdomain'
    domain = TenantDomain(
        tenant_id=tenant.id,
        host=normalized,
        kind=kind,
        status='active' if is_subdomain else 'pending',
        verify_token=None if is_subdomain else secrets.token_urlsafe(24),
        verified_at=datetime.now(UTC) if is_subdomain else None,
    )
    db.add(domain)
    await db.flush()
    return domain


async def verify_domain(db: AsyncSession, domain: TenantDomain) -> TenantDomain:
    """按 TXT 记录判定所有权：只有唯一凭证命中才转 active，否则记 failed。"""
    if domain.status == 'active':
        return domain
    expected = verification_value(domain.verify_token or '')
    records = await domain_verifier.get_verifier().txt_records(
        verification_record_name(domain.host)
    )
    if domain.verify_token and expected in records:
        domain.status = 'active'
        domain.verified_at = datetime.now(UTC)
    else:
        domain.status = 'failed'
    await db.flush()
    return domain


async def list_domains(db: AsyncSession, tenant_id: int) -> list[TenantDomain]:
    return list(
        (
            await db.scalars(
                select(TenantDomain)
                .where(TenantDomain.tenant_id == tenant_id)
                .order_by(TenantDomain.id)
            )
        ).all()
    )


async def get_domain(db: AsyncSession, tenant_id: int, domain_id: int) -> TenantDomain:
    domain = (
        await db.scalars(
            select(TenantDomain).where(
                TenantDomain.id == domain_id, TenantDomain.tenant_id == tenant_id
            )
        )
    ).first()
    if domain is None:
        raise DomainNotFoundError('域名不存在')
    return domain


async def delete_domain(db: AsyncSession, tenant_id: int, domain_id: int) -> None:
    domain = await get_domain(db, tenant_id, domain_id)
    await db.delete(domain)
    await db.flush()


async def ensure_tenant_subdomain(db: AsyncSession, tenant: Tenant) -> TenantDomain | None:
    """给租户补一条 {slug}.{tenant_base_domain} 子域（幂等）。未配置基域时返回 None。"""
    base = normalize_host(settings.tenant_base_domain)
    if not base:
        return None
    host = f'{tenant.slug}.{base}'
    existing = (
        await db.scalars(select(TenantDomain).where(TenantDomain.host == host))
    ).first()
    if existing is not None:
        return existing
    return await add_domain(db, tenant, host, kind='subdomain')
