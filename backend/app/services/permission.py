"""Permission cache invalidation.

``AuthContext.permissions`` is cached in Redis under
``perm:{tenant_id}:{user_id}:v{permission_version}`` for 60 seconds. Bumping the
tenant's ``permission_version`` makes every existing key unreachable, which is the
cheapest correct way to invalidate the whole tenant's cached authorisation.

Anything that can change the *effective* permissions of a member must call
``bump_permission_version``: editing a role's permission set, changing a user's
role, and removing a membership. Otherwise a demoted user keeps their old rights
until the TTL expires.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant


async def bump_permission_version(db: AsyncSession, tenant_id: int) -> None:
    """Invalidate every cached permission set in ``tenant_id``."""
    tenant = await db.get(Tenant, tenant_id)
    if tenant is not None:
        tenant.permission_version += 1
