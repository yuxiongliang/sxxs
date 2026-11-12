"""平台端域名管理（B6）：给租户绑定 / 验证 / 解绑域名。

为什么只给平台运营（platform:tenant:manage）：host 是整站的入口，改错一个 host 就是
把一整条流量导到别处；租户自己改自己的域名风险太高。

自有子域（kind=subdomain）创建即 active；客户自带域名必须 pending → TXT 验证 → active。
返回值里带上要添加的 DNS 记录，运营直接复制给客户，不用再解释格式。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_platform_permission
from app.core.cors import invalidate_host_cache
from app.core.response import ok
from app.models.tenant import Tenant, TenantDomain
from app.schemas.platform import TenantDomainCreate
from app.services import tenant_domains

router = APIRouter(prefix='/platform/tenants', tags=['平台域名'])


def _status_for(exc: tenant_domains.TenantDomainError) -> int:
    """业务错误 → HTTP 状态码，集中一处，免得每个端点各写一遍。"""
    if isinstance(exc, tenant_domains.DomainConflictError):
        return 409
    if isinstance(exc, tenant_domains.DomainNotFoundError):
        return 404
    if isinstance(exc, tenant_domains.VerifierUnavailableError):
        return 503
    return 400


def _payload(domain: TenantDomain) -> dict:
    payload = {
        "id": domain.id,
        "tenant_id": domain.tenant_id,
        "host": domain.host,
        "kind": domain.kind,
        "status": domain.status,
        "is_primary": domain.is_primary,
        "verified_at": domain.verified_at,
    }
    if domain.verify_token:
        payload["dns_record"] = {
            "type": "TXT",
            "name": tenant_domains.verification_record_name(domain.host),
            "value": tenant_domains.verification_value(domain.verify_token),
        }
    return payload


async def _tenant_or_404(db: AsyncSession, tenant_id: int) -> Tenant:
    tenant = (await db.scalars(select(Tenant).where(Tenant.id == tenant_id))).first()
    if tenant is None:
        raise HTTPException(status_code=404, detail='租户不存在')
    return tenant


@router.get('/{tenant_id}/domains')
async def list_tenant_domains(
    tenant_id: int,
    _context=Depends(require_platform_permission('platform:tenant:read')),
    db: AsyncSession = Depends(get_db),
):
    tenant = await _tenant_or_404(db, tenant_id)
    domains = await tenant_domains.list_domains(db, tenant.id)
    return ok([_payload(domain) for domain in domains])


@router.post('/{tenant_id}/domains')
async def create_tenant_domain(
    tenant_id: int,
    payload: TenantDomainCreate,
    _context=Depends(require_platform_permission('platform:tenant:manage')),
    db: AsyncSession = Depends(get_db),
):
    tenant = await _tenant_or_404(db, tenant_id)
    try:
        domain = await tenant_domains.add_domain(db, tenant, payload.host, payload.kind)
    except tenant_domains.TenantDomainError as exc:
        raise HTTPException(status_code=_status_for(exc), detail=str(exc)) from exc
    await db.commit()
    await db.refresh(domain)
    invalidate_host_cache()
    return ok(_payload(domain), '域名已绑定')


@router.post('/{tenant_id}/domains/{domain_id}/verify')
async def verify_tenant_domain(
    tenant_id: int,
    domain_id: int,
    _context=Depends(require_platform_permission('platform:tenant:manage')),
    db: AsyncSession = Depends(get_db),
):
    await _tenant_or_404(db, tenant_id)
    try:
        domain = await tenant_domains.get_domain(db, tenant_id, domain_id)
        domain = await tenant_domains.verify_domain(db, domain)
    except tenant_domains.TenantDomainError as exc:
        raise HTTPException(status_code=_status_for(exc), detail=str(exc)) from exc
    except RuntimeError as exc:  # dnspython 未安装等运行期问题
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(domain)
    invalidate_host_cache()
    return ok(_payload(domain))


@router.delete('/{tenant_id}/domains/{domain_id}')
async def delete_tenant_domain(
    tenant_id: int,
    domain_id: int,
    _context=Depends(require_platform_permission('platform:tenant:manage')),
    db: AsyncSession = Depends(get_db),
):
    try:
        await tenant_domains.delete_domain(db, tenant_id, domain_id)
    except tenant_domains.TenantDomainError as exc:
        raise HTTPException(status_code=_status_for(exc), detail=str(exc)) from exc
    await db.commit()
    invalidate_host_cache()
    return ok(None, '域名已解绑')
