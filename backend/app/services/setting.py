import copy
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao import setting as setting_dao
from app.models.setting import SystemSetting
from app.schemas.setting import SettingTestResult, SettingUpdate

ALLOWED_CATEGORIES = {"payment", "sms", "email", "storage", "amap"}

DEFAULT_SETTINGS: dict[str, dict] = {
    "payment": {
        "enabled": True,
        "config": {
            "alipay": {
                "enabled": True,
                "environment": "sandbox",
                "appId": "2021000000000000",
                "merchantId": "2088000000000000",
                "privateKey": "",
                "publicKey": "",
                "notifyUrl": "http://127.0.0.1:9000/api/v1/payments/alipay/notify",
                "returnUrl": "http://localhost:8000/payment/result",
            },
            "wechat": {
                "enabled": True,
                "environment": "sandbox",
                "appId": "wx0000000000000000",
                "mchId": "1600000000",
                "apiV3Key": "",
                "serialNo": "",
                "privateKey": "",
                "notifyUrl": "http://127.0.0.1:9000/api/v1/payments/wechat/notify",
            },
        },
    },
    "sms": {
        "enabled": True,
        "config": {
            "provider": "aliyun",
            "accessKeyId": "",
            "accessKeySecret": "",
            "region": "cn-hangzhou",
            "signName": "Ant Design Pro",
            "templateCode": "SMS_000000001",
            "dailyLimit": 1000,
        },
    },
    "email": {
        "enabled": True,
        "config": {
            "provider": "qq",
            "host": "smtp.qq.com",
            "port": 465,
            "ssl": True,
            "username": "",
            "password": "",
            "fromName": "Ant Design Pro",
            "fromAddress": "",
            "dailyLimit": 500,
        },
    },
    "storage": {
        "enabled": True,
        "config": {
            "driver": "local",
            "local": {
                "uploadDir": "./uploads",
                "publicBaseUrl": "http://127.0.0.1:9000/uploads",
            },
            "oss": {
                "endpoint": "oss-cn-hangzhou.aliyuncs.com",
                "bucket": "",
                "accessKeyId": "",
                "accessKeySecret": "",
                "domain": "",
                "prefix": "uploads/",
            },
        },
    },
}


def _ensure_category(category: str) -> None:
    if category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=404, detail="未知的设置分类")


async def get_setting(db: AsyncSession, category: str, tenant_id: int) -> SystemSetting:
    _ensure_category(category)
    setting = await setting_dao.get_setting(db, category, tenant_id)
    if setting is None:
        default = DEFAULT_SETTINGS[category]
        setting = await setting_dao.upsert_setting(
            db, tenant_id, category, default["enabled"], copy.deepcopy(default["config"])
        )
        await db.commit()
        await db.refresh(setting)
    return setting


async def save_setting(
    db: AsyncSession, category: str, payload: SettingUpdate, tenant_id: int
) -> SystemSetting:
    _ensure_category(category)
    setting = await setting_dao.upsert_setting(
        db, tenant_id, category, payload.enabled, payload.config
    )
    await db.commit()
    await db.refresh(setting)
    return setting


async def test_setting(
    db: AsyncSession, category: str, config: dict | None, tenant_id: int
) -> SettingTestResult:
    _ensure_category(category)
    setting = await get_setting(db, category, tenant_id)
    current = config if config is not None else setting.config

    if category == "amap":
        from app.services import amap as amap_service  # 局部导入，避免循环依赖

        web_key = str(current.get("webKey") or "").strip()
        if not web_key:
            return SettingTestResult(
                success=False,
                message="缺少 Web服务 key（不是 JS API key，两者不能混用）",
            )
        try:
            candidates = await amap_service.geocode(web_key, "北京市朝阳区阜通东大街6号")
        except amap_service.AmapError as exc:
            return SettingTestResult(
                success=False,
                message=str(exc),
                detail={"infocode": exc.infocode, "info": exc.info},
            )
        if not candidates:
            return SettingTestResult(
                success=False,
                message="key 可用，但目标地址没有解析出坐标",
            )
        return SettingTestResult(
            success=True,
            message="高德 Web 服务连通，key 可用",
            detail={
                "geocode": candidates[0].get("formatted_address"),
                "location": candidates[0].get("location"),
            },
        )

    if category == "payment":
        alipay = current.get("alipay", {})
        wechat = current.get("wechat", {})
        missing = []
        if not alipay.get("appId"):
            missing.append("支付宝 AppID")
        if not wechat.get("appId"):
            missing.append("微信 AppID")
        if missing:
            return SettingTestResult(
                success=False,
                message=f"缺少必要参数：{'、'.join(missing)}",
            )
        return SettingTestResult(
            success=True,
            message="支付参数校验通过（演示环境，未发起真实支付网关请求）",
            detail={"environment": alipay.get("environment", "sandbox")},
            qr_code="https://qr.alipay.com/ant-design-pro-demo",
        )

    if category == "sms":
        required = ["accessKeyId", "accessKeySecret", "signName", "templateCode"]
        missing = [key for key in required if not current.get(key)]
        if missing:
            return SettingTestResult(
                success=False,
                message=f"缺少必要参数：{'、'.join(missing)}",
            )
        return SettingTestResult(
            success=True,
            message="阿里云短信参数校验通过（演示环境，未调用短信 API）",
            detail={"region": current.get("region"), "provider": "aliyun"},
        )

    if category == "email":
        required = ["host", "username", "password", "fromAddress"]
        missing = [key for key in required if not current.get(key)]
        if missing:
            return SettingTestResult(
                success=False,
                message=f"缺少必要参数：{'、'.join(missing)}",
            )
        return SettingTestResult(
            success=True,
            message="SMTP 参数校验通过（演示环境，未建立真实 SMTP 连接）",
            detail={
                "host": current.get("host"),
                "port": current.get("port"),
                "ssl": current.get("ssl"),
            },
        )

    if category == "storage":
        driver = current.get("driver", "local")
        if driver == "local":
            upload_dir = current.get("local", {}).get("uploadDir", "./uploads")
            path = Path(upload_dir).expanduser().resolve()
            try:
                path.mkdir(parents=True, exist_ok=True)
                probe = path / ".write-test"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
            except OSError as exc:
                return SettingTestResult(success=False, message=f"本地目录不可写：{exc}")
            return SettingTestResult(
                success=True,
                message="本地存储目录可写",
                detail={"path": str(path)},
            )
        oss = current.get("oss", {})
        required = ["endpoint", "bucket", "accessKeyId", "accessKeySecret"]
        missing = [key for key in required if not oss.get(key)]
        if missing:
            return SettingTestResult(
                success=False,
                message=f"缺少必要参数：{'、'.join(missing)}",
            )
        return SettingTestResult(
            success=True,
            message="OSS 参数格式校验通过（演示环境，未发起真实 OSS 请求）",
            detail={"endpoint": oss.get("endpoint"), "bucket": oss.get("bucket")},
        )

    raise HTTPException(status_code=400, detail="无法测试该设置")


# 高德地图（AMap）配置。单独追加而不是插进上面的大 dict，减少冲突面。
# jsKey / securityCode 给前端交互地图用；webKey 只给后端调 REST，永不下发。
DEFAULT_SETTINGS["amap"] = {
    "enabled": True,
    "config": {
        "enabled": True,
        "jsKey": "",
        "securityCode": "",
        "webKey": "",
        "defaultCenter": "116.397428,39.90923",
        "defaultZoom": 11,
        "useProxy": True,
    },
}
