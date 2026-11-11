from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.security import hash_password
from app.models.attachment import Attachment
from app.models.department import Department
from app.models.notification import Notification
from app.models.role import Role
from app.models.setting import SystemSetting
from app.models.tenant import Tenant
from app.models.user import User
from app.seed_auth import DEMO_TENANT_SLUG, seed_auth_data
from app.seed_billing import seed_billing_data
from app.seed_commerce import seed_commerce_data, seed_commission_rule
from app.services.setting import DEFAULT_SETTINGS

SEED_DEPARTMENTS = [
    "平台运营部",
    "内容运营部",
    "客户成功部",
    "数据分析部",
    "产品设计部",
]

SEED_ROLES = [
    {"code": "admin", "name": "管理员", "description": "拥有系统全部权限", "sort": 10},
    {"code": "operator", "name": "运营人员", "description": "负责日常运营与内容维护", "sort": 20},
    {"code": "viewer", "name": "只读用户", "description": "只读查看数据", "sort": 30},
]

SEED_USERS = [
    {
        "username": "admin",
        "nickname": "超级管理员",
        "email": "admin@example.com",
        "phone": "13800000001",
        "role": "admin",
        "status": "active",
        "department": "平台运营部",
        "birthday": date(1985, 6, 15),
        "gender": "male",
        "last_login_at": datetime.now(UTC) - timedelta(minutes=8),
    },
    {
        "username": "lisi",
        "nickname": "李思",
        "email": "lisi@example.com",
        "phone": "13800000002",
        "role": "operator",
        "status": "active",
        "department": "内容运营部",
        "birthday": date(1992, 3, 8),
        "gender": "female",
        "last_login_at": datetime.now(UTC) - timedelta(hours=2),
    },
    {
        "username": "wangwu",
        "nickname": "王五",
        "email": "wangwu@example.com",
        "phone": "13800000003",
        "role": "operator",
        "status": "active",
        "department": "客户成功部",
        "birthday": date(1988, 11, 21),
        "gender": "male",
        "last_login_at": datetime.now(UTC) - timedelta(days=1),
    },
    {
        "username": "zhaoliu",
        "nickname": "赵六",
        "email": "zhaoliu@example.com",
        "phone": "13800000004",
        "role": "viewer",
        "status": "disabled",
        "department": "数据分析部",
        "birthday": date(1995, 1, 30),
        "gender": "female",
        "last_login_at": datetime.now(UTC) - timedelta(days=12),
    },
    {
        "username": "chenqi",
        "nickname": "陈七",
        "email": "chenqi@example.com",
        "phone": "13800000005",
        "role": "viewer",
        "status": "active",
        "department": "产品设计部",
        "birthday": date(1990, 9, 12),
        "gender": "male",
        "last_login_at": datetime.now(UTC) - timedelta(hours=5),
    },
]


def _write_svg(name: str, label: str, color: str) -> None:
    path = settings.upload_path / name
    if path.exists():
        return
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{color}"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
  </defs>
  <rect width="960" height="540" fill="url(#bg)"/>
  <circle cx="760" cy="120" r="180" fill="#ffffff" opacity="0.08"/>
  <circle cx="180" cy="460" r="220" fill="#ffffff" opacity="0.06"/>
  <text x="64" y="280" fill="#ffffff" font-size="54" font-family="Arial, sans-serif" font-weight="700">{label}</text>
  <text x="66" y="330" fill="#ffffff" opacity="0.72" font-size="22" font-family="Arial, sans-serif">Ant Design Pro · Attachment Library</text>
</svg>"""
    path.write_text(svg, encoding="utf-8")


async def seed_demo_data() -> None:
    async with AsyncSessionLocal() as db:
        # The demo tenant must exist *before* any tenant-scoped demo row is
        # inserted, otherwise a cold start on an empty database fails with a
        # foreign-key violation on ``departments.tenant_id``.
        await seed_auth_data(db)
        tenant_id = (
            await db.execute(select(Tenant.id).where(Tenant.slug == DEMO_TENANT_SLUG))
        ).scalar_one()

        department_count = (await db.execute(select(func.count(Department.id)))).scalar_one()
        if department_count == 0:
            db.add_all(
                [
                    Department(tenant_id=tenant_id, name=name, status="active", sort=index * 10)
                    for index, name in enumerate(SEED_DEPARTMENTS)
                ]
            )

        role_count = (await db.execute(select(func.count(Role.id)))).scalar_one()
        if role_count == 0:
            db.add_all([Role(status="active", **item) for item in SEED_ROLES])

        await db.flush()

        user_count = (await db.execute(select(func.count(User.id)))).scalar_one()
        if user_count == 0:
            departments = list((await db.scalars(select(Department))).all())
            department_map = {item.name: item.id for item in departments}
            for item in SEED_USERS:
                payload = dict(item)
                department_name = payload.pop("department")
                payload["department"] = department_name
                payload["department_id"] = department_map.get(department_name)
                payload["password_hash"] = hash_password(
                    "ant.design" if payload["username"] == "admin" else "Antd@123456"
                )
                db.add(User(**payload))

        setting_count = (await db.execute(select(func.count(SystemSetting.id)))).scalar_one()
        if setting_count == 0:
            for category, default in DEFAULT_SETTINGS.items():
                db.add(
                    SystemSetting(
                        tenant_id=tenant_id,
                        category=category,
                        enabled=default["enabled"],
                        config=default["config"],
                    )
                )

        attachment_count = (await db.execute(select(func.count(Attachment.id)))).scalar_one()
        if attachment_count == 0:
            _write_svg("brand-banner.svg", "Brand Banner", "#1677ff")
            _write_svg("product-shot.svg", "Product Shot", "#0ea5e9")
            _write_svg("team-avatar.svg", "Team Avatar", "#8b5cf6")
            notes_path = settings.upload_path / "ontology-notes.md"
            if not notes_path.exists():
                notes_path.write_text(
                    "# Ontology notes\n\nDemo attachment for the Ant Design Pro admin console.\n",
                    encoding="utf-8",
                )
            spec_path = settings.upload_path / "api-spec.json"
            if not spec_path.exists():
                spec_path.write_text(
                    '{"title":"Demo API","version":"1.0.0"}',
                    encoding="utf-8",
                )
            base = f"{settings.public_base_url.rstrip('/')}/uploads"
            db.add_all(
                [
                    Attachment(
                        tenant_id=tenant_id,
                        name="brand-banner.svg",
                        original_name="brand-banner.svg",
                        mime_type="image/svg+xml",
                        size=(settings.upload_path / "brand-banner.svg").stat().st_size,
                        extension=".svg",
                        category="image",
                        storage="local",
                        storage_key="brand-banner.svg",
                        url=f"{base}/brand-banner.svg",
                        uploader="admin",
                        source_module="品牌中心",
                        checksum="seed-brand",
                    ),
                    Attachment(
                        tenant_id=tenant_id,
                        name="product-shot.svg",
                        original_name="product-shot.svg",
                        mime_type="image/svg+xml",
                        size=(settings.upload_path / "product-shot.svg").stat().st_size,
                        extension=".svg",
                        category="image",
                        storage="local",
                        storage_key="product-shot.svg",
                        url=f"{base}/product-shot.svg",
                        uploader="李思",
                        source_module="商品管理",
                        checksum="seed-product",
                    ),
                    Attachment(
                        tenant_id=tenant_id,
                        name="team-avatar.svg",
                        original_name="team-avatar.svg",
                        mime_type="image/svg+xml",
                        size=(settings.upload_path / "team-avatar.svg").stat().st_size,
                        extension=".svg",
                        category="image",
                        storage="local",
                        storage_key="team-avatar.svg",
                        url=f"{base}/team-avatar.svg",
                        uploader="王五",
                        source_module="用户管理",
                        checksum="seed-avatar",
                    ),
                    Attachment(
                        tenant_id=tenant_id,
                        name="ontology-notes.md",
                        original_name="ontology-notes.md",
                        mime_type="text/markdown",
                        size=(settings.upload_path / "ontology-notes.md").stat().st_size,
                        extension=".md",
                        category="document",
                        storage="local",
                        storage_key="ontology-notes.md",
                        url=f"{base}/ontology-notes.md",
                        uploader="admin",
                        source_module="本体管理",
                        checksum="seed-notes",
                    ),
                    Attachment(
                        tenant_id=tenant_id,
                        name="api-spec.json",
                        original_name="api-spec.json",
                        mime_type="application/json",
                        size=(settings.upload_path / "api-spec.json").stat().st_size,
                        extension=".json",
                        category="document",
                        storage="local",
                        storage_key="api-spec.json",
                        url=f"{base}/api-spec.json",
                        uploader="admin",
                        source_module="开放平台",
                        checksum="seed-spec",
                    ),
                    Attachment(
                        tenant_id=tenant_id,
                        name="demo-video.mp4",
                        original_name="demo-video.mp4",
                        mime_type="video/mp4",
                        size=1024 * 1024 * 2,
                        extension=".mp4",
                        category="video",
                        storage="remote",
                        storage_key="",
                        url="https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
                        uploader="李思",
                        source_module="内容运营",
                        checksum="seed-video",
                    ),
                ]
            )

        notification_count = (await db.execute(select(func.count(Notification.id)))).scalar_one()
        if notification_count == 0:
            now = datetime.now(UTC)
            db.add_all(
                [
                    Notification(
                        tenant_id=tenant_id,
                        title="新版本上线通知",
                        channel="inbox",
                        template="SYSTEM_RELEASE",
                        audience="all",
                        content="Ant Design Pro 管理端已升级到 v6。",
                        status="success",
                        sent_at=now - timedelta(hours=2),
                        total=1280,
                        success_count=1280,
                    ),
                    Notification(
                        tenant_id=tenant_id,
                        title="本周运营周报",
                        channel="email",
                        template="WEEKLY_REPORT",
                        audience="role:operator",
                        content="本周运营数据已生成，请查收附件。",
                        status="success",
                        sent_at=now - timedelta(days=1),
                        total=36,
                        success_count=36,
                    ),
                    Notification(
                        tenant_id=tenant_id,
                        title="验证码服务异常告警",
                        channel="sms",
                        template="SMS_ALERT",
                        audience="role:admin",
                        content="短信通道出现短暂波动，请检查配置。",
                        status="failed",
                        sent_at=now - timedelta(days=2),
                        total=12,
                        success_count=0,
                        failed_count=12,
                        error_message="短信渠道未启用",
                    ),
                    Notification(
                        tenant_id=tenant_id,
                        title="双十一活动预热",
                        channel="inbox",
                        template="CAMPAIGN",
                        audience="all",
                        content="活动将于本周五开启。",
                        status="pending",
                        scheduled_at=now + timedelta(hours=6),
                        total=1280,
                    ),
                ]
            )

        await db.flush()
        await seed_auth_data(db)
        await seed_commerce_data(db)
        await seed_commission_rule(db)
        await seed_billing_data(db)
