"""附件内容审核管道。

设计要点：
1. **provider 可插拔**（null / mock / remote）：大模型只留接口，当前默认 `null`；
   测试用 `mock`，生产接大模型时把配置切到 `remote` 即可，代码零改动。
2. **异步不阻塞上传**：上传只落库 + 入队，worker 后台出结论。
3. **失败按场景分级**（failMode）—— 这是最容易出事的地方：
   IM 图片挂了要放行（聊天不能停），KYC 证件挂了必须拦（宁可让用户重传）。
4. **按 checksum 去重**：同一张图被多人转发只审一次；驳回结论永久缓存。
5. **每租户日配额**：审核是平台付钱，不能让单个租户烧穿。

已知取舍：缩略图送审需要 Pillow（当前项目未依赖），先用 `maxSendBytes` 截断，
后续加 Pillow 再补真正的缩略图生成。
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

import structlog
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.redis import redis_client
from app.models.attachment import Attachment
from app.models.moderation import ModerationCache, ModerationLog
from app.services import platform_setting as platform_setting_service

logger = structlog.get_logger(__name__)

APPROVED = "approved"
REJECTED = "rejected"
PENDING = "pending"
MANUAL = "manual"
FAILED = "failed"

CATEGORY = "moderation"

# 审核管道自己会遇到的、可预期的失败类型。故意不 catch Exception：
# 真正的 bug（NameError/AttributeError）应该冒出来，而不是被静默当成「审核异常」。
PROVIDER_ERRORS = (OSError, ValueError, RuntimeError, json.JSONDecodeError)
WORKER_ERRORS = (SQLAlchemyError, OSError, RuntimeError)

_queue: asyncio.Queue[int] | None = None
_worker: asyncio.Task | None = None
_stop: asyncio.Event | None = None


class ModerationError(RuntimeError):
    """provider 调用失败（网络/协议/配置），由调用方按 failMode 决定放行还是拦。"""


@dataclass
class ModerationVerdict:
    decision: str
    categories: list[str] = field(default_factory=list)
    confidence: float | None = None
    provider: str = "null"
    raw: dict = field(default_factory=dict)
    elapsed_ms: int = 0
    # 只有「针对内容本身」的结论才配进缓存。降级结论（服务异常/配额超限）
    # 不能缓存，否则一次抖动会永久污染该 checksum 的后续所有上传。
    cacheable: bool = True


class ModerationProvider(Protocol):
    name: str

    async def moderate(
        self, *, content: bytes, mime: str, kind: str, ctx: dict
    ) -> ModerationVerdict: ...


def _as_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def classify(mime_type: str, extension: str) -> str:
    major = mime_type.split("/", 1)[0]
    if major == "image":
        return "image"
    if major == "video":
        return "video"
    if mime_type.startswith(("application/pdf", "text/")):
        return "document"
    if mimetypes.guess_type(f"x{extension}")[0]:
        return "document"
    return "other"


class NullProvider:
    """默认实现：不调用任何外部服务。

    `auto_approve=True` 时直接放行（开发/演示），否则转人工队列。
    """

    name = "null"

    def __init__(self, auto_approve: bool = True) -> None:
        self.auto_approve = auto_approve

    async def moderate(
        self, *, content: bytes, mime: str, kind: str, ctx: dict
    ) -> ModerationVerdict:
        return ModerationVerdict(
            decision=APPROVED if self.auto_approve else MANUAL,
            categories=[],
            confidence=None,
            provider=self.name,
            raw={"note": "null provider"},
        )


class MockProvider:
    """开发 / E2E 用：按文件名给确定性结论，保证测试可复现。

    文件名含 `reject` → 驳回；含 `manual` → 人工；其余放行。
    """

    name = "mock"

    async def moderate(
        self, *, content: bytes, mime: str, kind: str, ctx: dict
    ) -> ModerationVerdict:
        filename = str(ctx.get("filename") or "").lower()
        if "reject" in filename:
            return ModerationVerdict(
                decision=REJECTED,
                categories=["mock_violation"],
                confidence=0.99,
                provider=self.name,
            )
        if "manual" in filename:
            return ModerationVerdict(decision=MANUAL, provider=self.name)
        return ModerationVerdict(decision=APPROVED, provider=self.name)


class RemoteProvider:
    """大模型审核的预留实现。当前不启用，配置齐全后把 provider 切成 remote 即可。

    用 urllib 而不是新增 httpx 依赖：这里只是一次同步 POST，放到线程里跑。
    """

    name = "remote"

    def __init__(self, config: dict) -> None:
        self.endpoint = str(config.get("endpoint") or "")
        self.api_key = str(config.get("apiKey") or "")
        self.timeout_ms = _as_int(config.get("timeoutMs"), 5000)

    def _post(self, payload: bytes) -> dict:
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_ms / 1000) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise ModerationError(f"审核服务不可用：{exc}") from exc

    async def moderate(
        self, *, content: bytes, mime: str, kind: str, ctx: dict
    ) -> ModerationVerdict:
        if not self.endpoint:
            raise ModerationError("moderation endpoint 未配置")
        payload = json.dumps(
            {"content_hex": content.hex(), "mime": mime, "kind": kind, "context": ctx}
        ).encode("utf-8")
        data = await asyncio.to_thread(self._post, payload)
        decision = str(data.get("decision") or APPROVED)
        if decision not in {APPROVED, REJECTED, MANUAL}:
            decision = MANUAL
        return ModerationVerdict(
            decision=decision,
            categories=list(data.get("categories") or []),
            confidence=data.get("confidence"),
            provider=self.name,
            raw={"keys": sorted(data.keys())},
        )


DEFAULT_CONFIG: dict = {
    "provider": "null",
    "enabled": True,
    "endpoint": "",
    "apiKey": "",
    "timeoutMs": 5000,
    "maxSendBytes": 8 * 1024 * 1024,
    "dailyQuota": 500,
    "autoApproveOnNull": True,
    "failMode": {"default": "manual", "kyc": "closed", "im": "open"},
}

KYC_MODULES = {"seller_kyc", "kyc", "dispute", "refund_evidence"}
IM_MODULES = {"im", "chat", "message"}


async def _config(db: AsyncSession) -> dict:
    row = await platform_setting_service.get_platform_setting(db, CATEGORY)
    merged = dict(DEFAULT_CONFIG)
    merged.update(row.config or {})
    if not isinstance(merged.get("failMode"), dict):
        merged["failMode"] = dict(DEFAULT_CONFIG["failMode"])
    return merged


def _build_provider(config: dict) -> ModerationProvider:
    name = str(config.get("provider") or "null").lower()
    if name == "mock":
        return MockProvider()
    if name == "remote":
        return RemoteProvider(config)
    return NullProvider(bool(config.get("autoApproveOnNull", True)))


def fail_mode_for(config: dict, source_module: str) -> str:
    modes = config.get("failMode") or {}
    key = (source_module or "").lower()
    if key in KYC_MODULES:
        return str(modes.get("kyc") or "closed")
    if key in IM_MODULES:
        return str(modes.get("im") or "open")
    return str(modes.get("default") or "manual")


async def _consume_quota(config: dict, tenant_id: int | None) -> bool:
    """每租户每日审核配额。Redis 不可用时放行 —— 审核不是安全边界，不能因此阻断上传。"""
    quota = _as_int(config.get("dailyQuota"), 0)
    if quota <= 0 or tenant_id is None:
        return True
    key = f"moderation:quota:{tenant_id}:{datetime.now(UTC).strftime('%Y%m%d')}"
    try:
        used = await redis_client.incr(key)
        if used == 1:
            await redis_client.expire(key, 86400)
        return _as_int(used, 0) <= quota
    except RedisError as exc:
        logger.warning("moderation_quota_unavailable", error=str(exc))
        return True


async def _cache_lookup(db: AsyncSession, checksum: str, kind: str) -> ModerationVerdict | None:
    if not checksum:
        return None
    row = (
        await db.scalars(
            select(ModerationCache).where(
                ModerationCache.checksum == checksum,
                ModerationCache.review_kind == kind,
            )
        )
    ).first()
    if row is None:
        return None
    if row.expires_at is not None and row.expires_at < datetime.now(UTC):
        return None
    return ModerationVerdict(
        decision=row.decision,
        categories=list(row.categories or []),
        provider=row.provider,
        raw={"cached": True},
    )


async def _cache_store(
    db: AsyncSession, checksum: str, kind: str, verdict: ModerationVerdict
) -> None:
    if not checksum:
        return
    # 驳回永久缓存：不给「改个名字再传」留口子
    expires = None if verdict.decision == REJECTED else datetime.now(UTC) + timedelta(days=30)
    existing = (
        await db.scalars(
            select(ModerationCache).where(
                ModerationCache.checksum == checksum,
                ModerationCache.review_kind == kind,
            )
        )
    ).first()
    if existing is None:
        db.add(
            ModerationCache(
                checksum=checksum,
                review_kind=kind,
                decision=verdict.decision,
                categories=verdict.categories,
                provider=verdict.provider,
                expires_at=expires,
            )
        )
    else:
        existing.decision = verdict.decision
        existing.categories = verdict.categories
        existing.provider = verdict.provider
        existing.expires_at = expires


REJECT_REASON_BY_CATEGORY = {
    "porn": "涉黄",
    "violence": "暴力",
    "ad_qr": "引流二维码",
    "watermark": "违规水印",
    "mock_violation": "内容不合规",
    "manual_reject": "人工判定不合规",
    "provider_error": "审核异常",
}


def reject_reason_text(categories: list[str]) -> str:
    for category in categories:
        if category in REJECT_REASON_BY_CATEGORY:
            return REJECT_REASON_BY_CATEGORY[category]
    return "内容不合规"


async def apply_verdict(
    db: AsyncSession,
    attachment: Attachment,
    verdict: ModerationVerdict,
    *,
    source: str = "auto",
    reviewer_id: int | None = None,
) -> None:
    """把结论写回附件 + 落审核日志 + 更新缓存。**唯一**允许改审核状态的入口。"""
    now = datetime.now(UTC)
    attachment.review_status = verdict.decision
    attachment.reviewed_at = now
    attachment.review_provider = verdict.provider
    attachment.reject_reason = (
        reject_reason_text(verdict.categories) if verdict.decision == REJECTED else None
    )
    db.add(
        ModerationLog(
            attachment_id=attachment.id,
            provider=verdict.provider,
            decision=verdict.decision,
            categories=verdict.categories,
            confidence=verdict.confidence,
            raw=verdict.raw,
            elapsed_ms=verdict.elapsed_ms,
            source=source,
            reviewer_id=reviewer_id,
        )
    )
    if source == "auto" and verdict.cacheable:
        await _cache_store(db, attachment.checksum, attachment.review_kind, verdict)


def _read_content(attachment: Attachment, max_bytes: int) -> bytes:
    path = Path(settings.upload_path) / (attachment.storage_key or "")
    if not attachment.storage_key or not path.exists():
        raise FileNotFoundError(attachment.storage_key or "")
    return path.read_bytes()[:max_bytes]


async def moderate_one(db: AsyncSession, attachment_id: int) -> None:
    attachment = await db.get(Attachment, attachment_id)
    if attachment is None or attachment.review_status != PENDING:
        return

    config = await _config(db)
    if not config.get("enabled", True):
        await apply_verdict(
            db, attachment, ModerationVerdict(decision=APPROVED, provider="disabled")
        )
        await db.commit()
        return

    kind = attachment.review_kind or classify(attachment.mime_type, attachment.extension)
    attachment.review_kind = kind

    cached = await _cache_lookup(db, attachment.checksum, kind)
    if cached is not None:
        await apply_verdict(db, attachment, cached, source="cache")
        await db.commit()
        return

    if not await _consume_quota(config, attachment.tenant_id):
        await apply_verdict(
            db,
            attachment,
            ModerationVerdict(
                decision=MANUAL,
                provider="quota",
                raw={"reason": "daily_quota_exceeded"},
                cacheable=False,
            ),
        )
        await db.commit()
        return

    started = time.monotonic()
    provider = _build_provider(config)
    try:
        content = _read_content(attachment, _as_int(config.get("maxSendBytes"), 8 * 1024 * 1024))
        verdict = await provider.moderate(
            content=content,
            mime=attachment.mime_type,
            kind=kind,
            ctx={"filename": attachment.original_name, "source_module": attachment.source_module},
        )
    except (ModerationError, FileNotFoundError, *PROVIDER_ERRORS) as exc:
        mode = fail_mode_for(config, attachment.source_module)
        decision = {"open": APPROVED, "closed": REJECTED}.get(mode, MANUAL)
        logger.warning(
            "moderation_failed",
            attachment_id=attachment.id,
            fail_mode=mode,
            error=str(exc),
        )
        verdict = ModerationVerdict(
            decision=decision,
            categories=["provider_error"],
            provider=getattr(provider, "name", "unknown"),
            raw={"error": str(exc)[:300], "fail_mode": mode},
            cacheable=False,
        )

    verdict.elapsed_ms = int((time.monotonic() - started) * 1000)
    await apply_verdict(db, attachment, verdict)
    await db.commit()


async def submit(db: AsyncSession, attachment: Attachment) -> None:
    """上传之后调用。有 worker 就入队，没有（脚本/测试）就地审完保证一致。"""
    attachment.review_kind = classify(attachment.mime_type, attachment.extension)
    attachment.review_status = PENDING
    await db.flush()
    if _queue is not None:
        _queue.put_nowait(attachment.id)
        return
    await moderate_one(db, attachment.id)


async def manual_review(
    db: AsyncSession,
    attachment: Attachment,
    decision: str,
    reviewer_id: int | None,
    categories: list[str] | None = None,
) -> None:
    """平台人工复核：唯一能从 manual/failed 走出来的人工通道。"""
    if decision not in {APPROVED, REJECTED}:
        raise ValueError(f"不支持的人工结论：{decision}")
    await apply_verdict(
        db,
        attachment,
        ModerationVerdict(
            decision=decision,
            categories=list(categories or (["manual_reject"] if decision == REJECTED else [])),
            provider="reviewer",
            raw={"reviewer_id": reviewer_id},
        ),
        source="reviewer",
        reviewer_id=reviewer_id,
    )
    await db.commit()


async def sweep_stale(db: AsyncSession, minutes: int = 10) -> int:
    """兜底：卡在 pending 超过 N 分钟的转人工，避免「入队了但没人消费」永远卡死。"""
    cutoff = datetime.now(UTC) - timedelta(minutes=minutes)
    rows = list(
        (
            await db.scalars(
                select(Attachment).where(
                    Attachment.review_status == PENDING,
                    Attachment.created_at < cutoff,
                )
            )
        ).all()
    )
    for row in rows:
        row.review_status = MANUAL
    if rows:
        await db.commit()
    return len(rows)


async def _worker_loop() -> None:
    assert _queue is not None and _stop is not None
    while not _stop.is_set():
        try:
            attachment_id = await asyncio.wait_for(_queue.get(), timeout=60)
        except TimeoutError:
            try:
                async with AsyncSessionLocal() as db:
                    await sweep_stale(db)
            except WORKER_ERRORS as exc:
                logger.warning("moderation_sweep_failed", error=str(exc))
            continue
        try:
            async with AsyncSessionLocal() as db:
                await moderate_one(db, attachment_id)
        except (*WORKER_ERRORS, ModerationError) as exc:
            logger.warning("moderation_worker_failed", error=str(exc))


def start() -> None:
    global _queue, _worker, _stop
    if _worker is not None and not _worker.done():
        return
    _queue = asyncio.Queue()
    _stop = asyncio.Event()
    _worker = asyncio.create_task(_worker_loop())
    logger.info("moderation_worker_started")


async def stop() -> None:
    global _queue, _worker, _stop
    if _stop is not None:
        _stop.set()
    if _worker is not None:
        _worker.cancel()
        try:
            await _worker
        except asyncio.CancelledError:
            pass
        except WORKER_ERRORS as exc:
            logger.warning("moderation_worker_stop_failed", error=str(exc))
    _queue = None
    _worker = None
    _stop = None
