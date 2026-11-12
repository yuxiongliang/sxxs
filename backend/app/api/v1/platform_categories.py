"""平台端服务类目总览（只读）：每个租户的经营类目 + 商品数。

为什么只做只读：类目现在挂在租户自己身上（categories.tenant_id），平台侧没有
「平台类目字典」这类数据；凭空造一套会引出审批、同步、存量类目迁移一堆问题。
先把「各家都开了哪些类目、用了多少商品」看清，是低风险的第一步。

权限用 platform:tenant:read：这是跨租户的运营视图，不是配置改动。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_platform_permission
from app.core.response import ok
from app.models.catalog import Category, Product
from app.models.tenant import Tenant

router = APIRouter(prefix='/platform/categories', tags=['平台服务类目'])


@router.get('')
async def list_categories(
    tenant_id: int | None = Query(default=None, description='只看某个租户'),
    q: str | None = Query(default=None, max_length=64, description='按名称或 slug 搜索'),
    _context=Depends(require_platform_permission('platform:tenant:read')),
    db: AsyncSession = Depends(get_db),
):
    # 两个筛选条件都写成「无条件时 true()」，这样查询是一条完整的字面表达式：
    # 没有字符串拼接、没有动态 SQL，值全部走 SQLAlchemy 的绑定参数。
    # 搜索用 icontains + autoescape：用户输入里的 % 和 _ 被当字面量，不会变成通配符。
    rows = (
        await db.execute(
            select(Category, Tenant)
            .join(Tenant, Tenant.id == Category.tenant_id)
            .where(
                true() if tenant_id is None else Category.tenant_id == tenant_id,
                true()
                if not q
                else or_(
                    Category.name.icontains(q.strip(), autoescape=True),
                    Category.slug.icontains(q.strip(), autoescape=True),
                ),
            )
            .order_by(Category.tenant_id, Category.sort, Category.id)
        )
    ).all()

    # 商品数按 (tenant_id, category_id) 一次分组查完，避免 N+1
    counted = (
        await db.execute(
            select(Product.tenant_id, Product.category_id, func.count(Product.id)).group_by(
                Product.tenant_id, Product.category_id
            )
        )
    ).all()
    product_counts = {(tid, cid): total for tid, cid, total in counted}

    return ok(
        [
            {
                'id': category.id,
                'tenant_id': tenant.id,
                'tenant_name': tenant.display_name or tenant.name,
                'tenant_slug': tenant.slug,
                'name': category.name,
                'slug': category.slug,
                'parent_id': category.parent_id,
                'sort': category.sort,
                'status': category.status,
                'product_count': product_counts.get((tenant.id, category.id), 0),
            }
            for category, tenant in rows
        ]
    )
