from fastapi import APIRouter

from app.api.v1 import (
    amap,
    attachments,
    audit,
    auth,
    billing,
    commerce,
    dashboard,
    departments,
    finance_admin,
    im,
    media,
    notifications,
    platform,
    platform_auth,
    platform_moderation,
    platform_notification_templates,
    platform_settings,
    portal_shopping,
    public,
    roles,
    seller,
    settings,
    tenant_brand,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(amap.router)
api_router.include_router(commerce.router)
api_router.include_router(dashboard.router)
api_router.include_router(finance_admin.router)
api_router.include_router(billing.router)
api_router.include_router(billing.tenant_router)
api_router.include_router(audit.router)
api_router.include_router(portal_shopping.router)
api_router.include_router(im.router)
api_router.include_router(seller.router)
api_router.include_router(platform_auth.router)
api_router.include_router(platform.router)
api_router.include_router(platform_settings.router)
api_router.include_router(platform_moderation.router)
api_router.include_router(platform_notification_templates.router)
api_router.include_router(media.router)
api_router.include_router(public.router)
api_router.include_router(departments.router)
api_router.include_router(roles.router)
api_router.include_router(settings.router)
api_router.include_router(tenant_brand.router)
api_router.include_router(attachments.router)
api_router.include_router(notifications.router)
