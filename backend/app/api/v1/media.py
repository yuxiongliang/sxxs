"""买家 / 卖家上传通道。

为什么单独一个入口：`/attachments/upload` 需要 `attachment:upload` 权限，
买家与卖家角色没有这个码；而且他们的上传必须强制打上**自己的** visibility，
不能由前端传。这里用 scope 白名单把「谁、传什么、可见范围」固化成规则。
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_context, get_db
from app.core.response import ok
from app.schemas.attachment import AttachmentOut
from app.schemas.common import ApiResponse
from app.services import attachment as attachment_service
from app.services.attachment import primary_role
from app.services.auth import AuthContext

router = APIRouter(prefix="/media", tags=["媒体上传"])

SCOPES: dict[str, dict] = {
    "avatar": {"visibility": "public", "module": "avatar", "allow": {"buyer", "seller", "admin"}},
    "im": {"visibility": "tenant", "module": "im", "allow": {"buyer", "seller", "admin"}},
    "product": {"visibility": "public", "module": "product", "allow": {"seller", "admin"}},
    "kyc": {"visibility": "tenant", "module": "seller_kyc", "allow": {"seller", "admin"}},
    "evidence": {"visibility": "tenant", "module": "dispute", "allow": {"buyer", "admin"}},
}


@router.post("/upload", response_model=ApiResponse[AttachmentOut])
async def upload_media(
    file: UploadFile = File(...),
    scope: str = Form(...),
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    rule = SCOPES.get(scope)
    if rule is None:
        raise HTTPException(status_code=400, detail=f"未知的上传场景：{scope}")
    role = primary_role(context.roles)
    if role not in rule["allow"]:
        raise HTTPException(status_code=403, detail="当前身份不允许该上传场景")

    record = await attachment_service.save_upload(
        db,
        file,
        source_module=rule["module"],
        tenant_id=context.tenant.id,
        uploader=context.user.username,
        uploader_user_id=context.user.id,
        uploader_role=role,
        visibility=rule["visibility"],
    )
    return ok(AttachmentOut.model_validate(record), "上传成功")
