from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment
from app.models.im import Conversation, ConversationMember, ImReport, Message
from app.models.seller import Seller, SellerMember, Shop
from app.schemas.im import ConversationCreate, MessageCreate
from app.services import audit as audit_service
from app.services.auth import AuthContext, context_from_payload


async def context_from_ticket(db: AsyncSession, payload: dict) -> AuthContext:
    return await context_from_payload(
        db,
        {
            "sub": str(payload.get("user_id", "")),
            "tenant_id": int(payload.get("tenant_id", 0)),
        },
    )


async def seller_owner_id(db: AsyncSession, conversation: Conversation | None) -> int | None:
    if conversation is None:
        return None
    seller = await db.get(Seller, conversation.seller_id)
    return seller.owner_user_id if seller is not None else None


async def _seller_ids(db: AsyncSession, tenant_id: int, user_id: int) -> list[int]:
    rows = (
        await db.execute(
            select(SellerMember.seller_id).where(
                SellerMember.tenant_id == tenant_id,
                SellerMember.user_id == user_id,
                SellerMember.status == "active",
            )
        )
    ).all()
    return [row[0] for row in rows]


async def _is_member(db: AsyncSession, conversation: Conversation, user_id: int) -> bool:
    if conversation.buyer_id == user_id:
        return True
    seller_ids = await _seller_ids(db, conversation.tenant_id, user_id)
    return conversation.seller_id in seller_ids


async def create_conversation(
    db: AsyncSession, context: AuthContext, payload: ConversationCreate
) -> Conversation:
    seller = await db.get(Seller, payload.seller_id)
    if seller is None or seller.tenant_id != context.tenant.id or seller.status != "active":
        raise HTTPException(status_code=400, detail="卖家不可用")
    shop = (
        await db.scalars(
            select(Shop).where(Shop.tenant_id == context.tenant.id, Shop.seller_id == seller.id)
        )
    ).first()
    conversation = (
        await db.scalars(
            select(Conversation).where(
                Conversation.tenant_id == context.tenant.id,
                Conversation.buyer_id == context.user.id,
                Conversation.seller_id == seller.id,
            )
        )
    ).first()
    if conversation is None:
        conversation = Conversation(
            tenant_id=context.tenant.id,
            buyer_id=context.user.id,
            seller_id=seller.id,
            shop_id=shop.id if shop else None,
            order_id=payload.order_id,
            type="buyer_seller",
            status="active",
        )
        db.add(conversation)
        await db.flush()
        db.add(
            ConversationMember(
                tenant_id=context.tenant.id,
                conversation_id=conversation.id,
                user_id=context.user.id,
                role="buyer",
            )
        )
        db.add(
            ConversationMember(
                tenant_id=context.tenant.id,
                conversation_id=conversation.id,
                user_id=seller.owner_user_id,
                role="seller",
            )
        )
        await db.commit()
        await db.refresh(conversation)
    return conversation


async def list_conversations(db: AsyncSession, context: AuthContext) -> list[Conversation]:
    seller_ids = await _seller_ids(db, context.tenant.id, context.user.id)
    conditions = [Conversation.buyer_id == context.user.id]
    if seller_ids:
        conditions.append(Conversation.seller_id.in_(seller_ids))
    return list(
        (
            await db.scalars(
                select(Conversation)
                .where(Conversation.tenant_id == context.tenant.id, or_(*conditions))
                .order_by(Conversation.id.desc())
            )
        ).all()
    )


async def list_messages(
    db: AsyncSession, context: AuthContext, conversation_id: int, after_seq: int = 0
) -> list[Message]:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    if not await _is_member(db, conversation, context.user.id):
        raise HTTPException(status_code=403, detail="无权查看该会话")
    return list(
        (
            await db.scalars(
                select(Message)
                .where(
                    Message.tenant_id == context.tenant.id,
                    Message.conversation_id == conversation.id,
                    Message.seq > after_seq,
                )
                .order_by(Message.seq.asc())
            )
        ).all()
    )


async def send_message(
    db: AsyncSession,
    context: AuthContext,
    conversation_id: int,
    payload: MessageCreate,
) -> Message:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    if not await _is_member(db, conversation, context.user.id):
        raise HTTPException(status_code=403, detail="无权发送该会话")
    existing = (
        await db.scalars(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.client_msg_id == payload.client_msg_id,
            )
        )
    ).first()
    if existing is not None:
        return existing
    next_seq = (
        await db.scalar(
            select(func.coalesce(func.max(Message.seq), 0)).where(
                Message.conversation_id == conversation.id
            )
        )
    ) or 0

    message_payload: dict | None = None
    if payload.type == "image":
        attachment = await db.get(Attachment, payload.attachment_id)
        if attachment is None or attachment.tenant_id != context.tenant.id:
            raise HTTPException(status_code=404, detail="附件不存在")
        if attachment.category != "image" and not attachment.mime_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="只能发送图片附件")
        if attachment.uploader != context.user.username:
            raise HTTPException(status_code=403, detail="不能发送他人的附件")
        message_payload = {
            "attachment_id": attachment.id,
            "url": attachment.url,
            "mime_type": attachment.mime_type,
            "size": attachment.size,
        }

    message = Message(
        tenant_id=context.tenant.id,
        conversation_id=conversation.id,
        sender_id=context.user.id,
        client_msg_id=payload.client_msg_id,
        seq=next_seq + 1,
        type=payload.type,
        content=payload.content,
        payload=message_payload,
        status="sent",
    )
    db.add(message)
    await db.flush()
    conversation.last_message_id = message.id
    conversation.last_message_at = datetime.now(UTC)
    if conversation.buyer_id == context.user.id:
        conversation.seller_unread_count += 1
    else:
        conversation.buyer_unread_count += 1
    await db.commit()
    await db.refresh(message)
    return message


async def _member_row(
    db: AsyncSession, conversation_id: int, user_id: int
) -> ConversationMember | None:
    return (
        await db.scalars(
            select(ConversationMember).where(
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.user_id == user_id,
            )
        )
    ).first()


def _is_moderator(context: AuthContext) -> bool:
    return "platform_admin" in context.roles or "im:moderate" in context.permissions


async def list_messages_visible(
    db: AsyncSession,
    context: AuthContext,
    conversation_id: int,
    after_seq: int = 0,
) -> list[Message]:
    """List messages, hiding moderated ones unless the caller may moderate."""
    messages = await list_messages(db, context, conversation_id, after_seq)
    if _is_moderator(context):
        return messages
    return [item for item in messages if item.status != "moderated"]


async def mark_read(
    db: AsyncSession, context: AuthContext, conversation_id: int, seq: int
) -> dict:
    """Record a read receipt and clear the caller's unread counter.

    ``last_read_seq`` only ever moves forward: a delayed or replayed receipt for
    an older sequence must not resurrect unread messages.
    """
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    if not await _is_member(db, conversation, context.user.id):
        raise HTTPException(status_code=403, detail="无权操作该会话")

    member = await _member_row(db, conversation.id, context.user.id)
    if member is None:
        member = ConversationMember(
            tenant_id=context.tenant.id,
            conversation_id=conversation.id,
            user_id=context.user.id,
            role="buyer" if conversation.buyer_id == context.user.id else "seller",
        )
        db.add(member)
        await db.flush()

    member.last_read_seq = max(member.last_read_seq, seq)

    if conversation.buyer_id == context.user.id:
        conversation.buyer_unread_count = 0
    else:
        conversation.seller_unread_count = 0

    await db.commit()
    await db.refresh(conversation)
    return await read_state(db, context, conversation.id)


async def read_state(db: AsyncSession, context: AuthContext, conversation_id: int) -> dict:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    if not await _is_member(db, conversation, context.user.id):
        raise HTTPException(status_code=403, detail="无权查看该会话")

    mine = await _member_row(db, conversation.id, context.user.id)
    peers = list(
        (
            await db.scalars(
                select(ConversationMember).where(
                    ConversationMember.conversation_id == conversation.id,
                    ConversationMember.user_id != context.user.id,
                )
            )
        ).all()
    )
    peer_seq = max((row.last_read_seq for row in peers), default=0)
    return {
        "conversation_id": conversation.id,
        "my_last_read_seq": mine.last_read_seq if mine else 0,
        "peer_last_read_seq": peer_seq,
        "buyer_unread_count": conversation.buyer_unread_count,
        "seller_unread_count": conversation.seller_unread_count,
    }


async def report_message(
    db: AsyncSession, context: AuthContext, message_id: int, reason: str
) -> ImReport:
    message = await db.get(Message, message_id)
    if message is None or message.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="消息不存在")
    conversation = await db.get(Conversation, message.conversation_id)
    if conversation is None or not await _is_member(db, conversation, context.user.id):
        raise HTTPException(status_code=403, detail="无权举报该消息")
    if message.sender_id == context.user.id:
        raise HTTPException(status_code=400, detail="不能举报自己发送的消息")

    existing = (
        await db.scalars(
            select(ImReport).where(
                ImReport.message_id == message.id,
                ImReport.reporter_id == context.user.id,
            )
        )
    ).first()
    if existing is not None:
        return existing

    report = ImReport(
        tenant_id=context.tenant.id,
        conversation_id=conversation.id,
        message_id=message.id,
        reporter_id=context.user.id,
        reason=reason,
        status="pending",
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def list_reports(
    db: AsyncSession, context: AuthContext, status: str | None = None
) -> list[ImReport]:
    stmt = select(ImReport).where(ImReport.tenant_id == context.tenant.id)
    if status:
        stmt = stmt.where(ImReport.status == status)
    return list((await db.scalars(stmt.order_by(ImReport.id.desc()))).all())


async def handle_report(
    db: AsyncSession, context: AuthContext, report_id: int, action: str, note: str = ""
) -> ImReport:
    report = await db.get(ImReport, report_id)
    if report is None or report.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="举报不存在")
    if report.status != "pending":
        raise HTTPException(status_code=400, detail="该举报已处理")

    report.status = "accepted" if action == "accept" else "rejected"
    report.handled_by = context.user.id
    report.handled_at = datetime.now(UTC)
    report.note = note

    if action == "accept":
        message = await db.get(Message, report.message_id)
        if message is not None:
            message.status = "moderated"
            await audit_service.record(
                db,
                action=audit_service.ACTION_IM_MESSAGE_MODERATED,
                tenant_id=context.tenant.id,
                actor_id=context.user.id,
                target_type="im_message",
                target_id=message.id,
                before={"status": "sent"},
                after={"status": "moderated", "report_id": report.id, "note": note},
            )

    await db.commit()
    await db.refresh(report)
    return report
