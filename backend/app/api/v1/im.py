import json
import secrets

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_permission
from app.core import im_bus
from app.core.db import AsyncSessionLocal
from app.core.redis import redis_client
from app.core.response import ok
from app.models.im import Conversation
from app.schemas.common import ApiResponse
from app.schemas.im import (
    ConversationCreate,
    ConversationOut,
    MessageCreate,
    MessageOut,
    ReadReceiptRequest,
    ReadStateOut,
    ReportCreate,
    ReportHandleRequest,
    ReportOut,
)
from app.services import im as im_service
from app.services.auth import AuthContext

router = APIRouter(prefix="/im", tags=["IM 即时聊天"])


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[int, set[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        self.connections.get(user_id, set()).discard(websocket)

    async def send_to_users(self, user_ids: list[int], payload: dict) -> None:
        for user_id in user_ids:
            for connection in list(self.connections.get(user_id, set())):
                try:
                    await connection.send_json(payload)
                except (RuntimeError, WebSocketDisconnect):
                    self.disconnect(user_id, connection)


manager = ConnectionManager()


async def event_recipients(conversation: Conversation, sender_id: int) -> list[int]:
    """Buyer + seller owner are the two humans in a conversation."""
    async with AsyncSessionLocal() as db:
        seller_owner = await im_service.seller_owner_id(db, conversation)
    recipients = {conversation.buyer_id, sender_id}
    if seller_owner:
        recipients.add(seller_owner)
    return sorted(recipients)


async def _deliver_local(event: dict) -> None:
    """Push a bus event to the sockets held by *this* replica."""
    user_ids = event.get("recipient_ids") or []
    await manager.send_to_users(
        [int(item) for item in user_ids],
        {
            "type": "message",
            "conversation_id": event.get("conversation_id"),
            "message": event.get("message"),
        },
    )


im_bus.register_handler(_deliver_local)


async def publish_message(message, conversation: Conversation, sender_id: int) -> None:
    """Broadcast a persisted message to every replica over the event bus."""
    recipients = await event_recipients(conversation, sender_id)
    await im_bus.publish_message_event(
        {
            "conversation_id": message.conversation_id,
            "message_id": message.id,
            "seq": message.seq,
            "sender_id": sender_id,
            "recipient_ids": recipients,
            "message": MessageOut.model_validate(message).model_dump(mode="json"),
        }
    )


@router.post("/ws-ticket")
async def ws_ticket(
    context: AuthContext = Depends(require_permission("im:conversation:read")),
):
    ticket = secrets.token_urlsafe(24)
    await redis_client.setex(
        f"im:ws:{ticket}",
        60,
        json.dumps({"user_id": context.user.id, "tenant_id": context.tenant.id}),
    )
    return ok({"ticket": ticket, "expires_in": 60})


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket, ticket: str = Query(...)):
    raw = await redis_client.get(f"im:ws:{ticket}")
    if not raw:
        await websocket.close(code=1008)
        return
    try:
        payload = json.loads(raw)
        user_id = int(payload["user_id"])
        tenant_id = int(payload["tenant_id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        await websocket.close(code=1008)
        return
    await redis_client.delete(f"im:ws:{ticket}")
    async with AsyncSessionLocal() as db:
        context = await im_service.context_from_ticket(
            db, {"user_id": user_id, "tenant_id": tenant_id}
        )
        await manager.connect(context.user.id, websocket)
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") != "message":
                    continue
                message = await im_service.send_message(
                    db,
                    context,
                    int(data["conversation_id"]),
                    MessageCreate(
                        content=data.get("content", ""),
                        type=data.get("message_type", "text"),
                        attachment_id=data.get("attachment_id"),
                        client_msg_id=data["client_msg_id"],
                    ),
                )
                conversation = await db.get(Conversation, message.conversation_id)
                if conversation is not None:
                    await publish_message(message, conversation, context.user.id)
        except WebSocketDisconnect:
            manager.disconnect(context.user.id, websocket)


@router.post("/conversations", response_model=ApiResponse[ConversationOut])
async def create_conversation(
    payload: ConversationCreate,
    context: AuthContext = Depends(require_permission("im:conversation:read")),
    db: AsyncSession = Depends(get_db),
):
    conversation = await im_service.create_conversation(db, context, payload)
    return ok(ConversationOut.model_validate(conversation), "会话已创建")


@router.get("/conversations", response_model=ApiResponse[list[ConversationOut]])
async def list_conversations(
    context: AuthContext = Depends(require_permission("im:conversation:read")),
    db: AsyncSession = Depends(get_db),
):
    conversations = await im_service.list_conversations(db, context)
    return ok([ConversationOut.model_validate(item) for item in conversations])


@router.get(
    "/conversations/{conversation_id}/messages", response_model=ApiResponse[list[MessageOut]]
)
async def list_messages(
    conversation_id: int,
    after_seq: int = Query(0, ge=0),
    context: AuthContext = Depends(require_permission("im:conversation:read")),
    db: AsyncSession = Depends(get_db),
):
    messages = await im_service.list_messages_visible(db, context, conversation_id, after_seq)
    return ok([MessageOut.model_validate(item) for item in messages])


@router.post("/conversations/{conversation_id}/messages", response_model=ApiResponse[MessageOut])
async def send_message(
    conversation_id: int,
    payload: MessageCreate,
    context: AuthContext = Depends(require_permission("im:message:send")),
    db: AsyncSession = Depends(get_db),
):
    message = await im_service.send_message(db, context, conversation_id, payload)
    conversation = await db.get(Conversation, message.conversation_id)
    if conversation is not None:
        await publish_message(message, conversation, context.user.id)
    return ok(MessageOut.model_validate(message), "消息已发送")


@router.post(
    "/conversations/{conversation_id}/read", response_model=ApiResponse[ReadStateOut]
)
async def mark_conversation_read(
    conversation_id: int,
    payload: ReadReceiptRequest,
    context: AuthContext = Depends(require_permission("im:conversation:read")),
    db: AsyncSession = Depends(get_db),
):
    state = await im_service.mark_read(db, context, conversation_id, payload.seq)
    return ok(ReadStateOut.model_validate(state), "已读状态已更新")


@router.get(
    "/conversations/{conversation_id}/read-state", response_model=ApiResponse[ReadStateOut]
)
async def conversation_read_state(
    conversation_id: int,
    context: AuthContext = Depends(require_permission("im:conversation:read")),
    db: AsyncSession = Depends(get_db),
):
    state = await im_service.read_state(db, context, conversation_id)
    return ok(ReadStateOut.model_validate(state))


@router.post("/messages/{message_id}/report", response_model=ApiResponse[ReportOut])
async def report_message(
    message_id: int,
    payload: ReportCreate,
    context: AuthContext = Depends(require_permission("im:report")),
    db: AsyncSession = Depends(get_db),
):
    report = await im_service.report_message(db, context, message_id, payload.reason)
    return ok(ReportOut.model_validate(report), "举报已提交")


@router.get("/reports", response_model=ApiResponse[list[ReportOut]])
async def list_reports(
    status: str | None = Query(default=None),
    context: AuthContext = Depends(require_permission("im:moderate")),
    db: AsyncSession = Depends(get_db),
):
    reports = await im_service.list_reports(db, context, status)
    return ok([ReportOut.model_validate(item) for item in reports])


@router.post("/reports/{report_id}/handle", response_model=ApiResponse[ReportOut])
async def handle_report(
    report_id: int,
    payload: ReportHandleRequest,
    context: AuthContext = Depends(require_permission("im:moderate")),
    db: AsyncSession = Depends(get_db),
):
    report = await im_service.handle_report(
        db, context, report_id, payload.action, payload.note
    )
    return ok(
        ReportOut.model_validate(report),
        "举报已受理，消息已下架" if payload.action == "accept" else "举报已驳回",
    )
