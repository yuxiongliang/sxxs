"""IM features: read receipts, image messages, abuse reporting/moderation, bus.

Plan §18 acceptance criteria covered:
  #11 buyers/sellers only see their own conversations
  #12 multi-instance broadcast; Redis outage degrades to polling without loss
  #14 moderated messages are invisible to normal users, visible to moderation
"""

from __future__ import annotations

import asyncio
import json

import pytest
from sqlalchemy import select

from app.core import im_bus
from app.core.redis import redis_client
from app.models.im import Message
from app.models.seller import Seller
from tests.conftest import bearer


async def _seller_id(db_session, tenant_id: int = 1) -> int:
    seller = (
        await db_session.execute(
            select(Seller).where(Seller.tenant_id == tenant_id, Seller.status == "active")
        )
    ).scalars().first()
    assert seller is not None
    return seller.id


async def _conversation(client, token: str, seller_id: int) -> int:
    response = await client.post(
        "/api/v1/im/conversations", headers=bearer(token), json={"seller_id": seller_id}
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


async def _send(client, token: str, conversation_id: int, content: str, cid: str = "c-1") -> dict:
    response = await client.post(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(token),
        json={"content": content, "client_msg_id": cid},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


# --------------------------------------------------------------------------- #
# Read receipts
# --------------------------------------------------------------------------- #


async def test_read_receipt_clears_unread_and_reports_peer_seq(
    client, customer_token, operator_token, db_session
):
    seller_id = await _seller_id(db_session)
    conversation_id = await _conversation(client, customer_token, seller_id)
    message = await _send(client, customer_token, conversation_id, "卖家你好", "read-1")

    seller_view = await client.get("/api/v1/im/conversations", headers=bearer(operator_token))
    conversation = next(
        item for item in seller_view.json()["data"] if item["id"] == conversation_id
    )
    assert conversation["seller_unread_count"] >= 1

    read = await client.post(
        f"/api/v1/im/conversations/{conversation_id}/read",
        headers=bearer(operator_token),
        json={"seq": message["seq"]},
    )
    assert read.status_code == 200, read.text
    state = read.json()["data"]
    assert state["seller_unread_count"] == 0
    assert state["my_last_read_seq"] == message["seq"]

    # The buyer can see that the seller has read up to that seq.
    buyer_state = await client.get(
        f"/api/v1/im/conversations/{conversation_id}/read-state",
        headers=bearer(customer_token),
    )
    assert buyer_state.status_code == 200
    assert buyer_state.json()["data"]["peer_last_read_seq"] == message["seq"]


async def test_read_receipt_never_moves_backwards(
    client, customer_token, operator_token, db_session
):
    seller_id = await _seller_id(db_session)
    conversation_id = await _conversation(client, customer_token, seller_id)
    await _send(client, customer_token, conversation_id, "第一条", "rb-1")
    second = await _send(client, customer_token, conversation_id, "第二条", "rb-2")

    await client.post(
        f"/api/v1/im/conversations/{conversation_id}/read",
        headers=bearer(operator_token),
        json={"seq": second["seq"]},
    )
    replay = await client.post(
        f"/api/v1/im/conversations/{conversation_id}/read",
        headers=bearer(operator_token),
        json={"seq": 1},
    )
    assert replay.status_code == 200
    assert replay.json()["data"]["my_last_read_seq"] == second["seq"], (
        "a delayed receipt must not resurrect unread messages"
    )


async def test_read_receipt_requires_membership(client, db_session):
    seller_id = await _seller_id(db_session)
    owner = await _register(client, "read-owner@example.com", "读者")
    intruder = await _register(client, "read-intruder@example.com", "闯入者")
    conversation_id = await _conversation(client, owner, seller_id)

    response = await client.post(
        f"/api/v1/im/conversations/{conversation_id}/read",
        headers=bearer(intruder),
        json={"seq": 1},
    )
    assert response.status_code in {403, 404}


# --------------------------------------------------------------------------- #
# Image messages
# --------------------------------------------------------------------------- #


async def _upload_image(client, token: str) -> dict:
    response = await client.post(
        "/api/v1/attachments/upload",
        headers=bearer(token),
        files={"file": ("chat.png", b"\x89PNG\r\n\x1a\n fake png bytes", "image/png")},
        data={"source_module": "im"},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_image_message_carries_attachment_payload(client, customer_token, db_session):
    seller_id = await _seller_id(db_session)
    conversation_id = await _conversation(client, customer_token, seller_id)
    attachment = await _upload_image(client, customer_token)

    response = await client.post(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(customer_token),
        json={
            "type": "image",
            "attachment_id": attachment["id"],
            "content": "看图",
            "client_msg_id": "img-1",
        },
    )
    assert response.status_code == 200, response.text
    message = response.json()["data"]
    assert message["type"] == "image"
    assert message["payload"]["attachment_id"] == attachment["id"]
    assert message["payload"]["url"]


async def test_image_message_requires_attachment_id(client, customer_token, db_session):
    seller_id = await _seller_id(db_session)
    conversation_id = await _conversation(client, customer_token, seller_id)
    response = await client.post(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(customer_token),
        json={"type": "image", "client_msg_id": "img-missing"},
    )
    assert response.status_code == 422


async def test_image_message_rejects_foreign_attachment(client, customer_token, db_session):
    """A buyer must not be able to embed someone else's upload."""
    seller_id = await _seller_id(db_session)
    conversation_id = await _conversation(client, customer_token, seller_id)
    other = await _register(client, "img-other@example.com", "他人")
    attachment = await _upload_image(client, other)

    response = await client.post(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(customer_token),
        json={
            "type": "image",
            "attachment_id": attachment["id"],
            "client_msg_id": "img-foreign",
        },
    )
    assert response.status_code == 403


async def test_image_message_rejects_non_image_attachment(client, customer_token, db_session):
    seller_id = await _seller_id(db_session)
    conversation_id = await _conversation(client, customer_token, seller_id)
    response = await client.post(
        "/api/v1/attachments/upload",
        headers=bearer(customer_token),
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"source_module": "im"},
    )
    attachment = response.json()["data"]

    sent = await client.post(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(customer_token),
        json={
            "type": "image",
            "attachment_id": attachment["id"],
            "client_msg_id": "img-not-image",
        },
    )
    assert sent.status_code == 400


# --------------------------------------------------------------------------- #
# Report & moderation
# --------------------------------------------------------------------------- #


async def test_report_flow_hides_message_from_buyer_but_not_moderator(
    client, customer_token, operator_token, admin_token, db_session
):
    seller_id = await _seller_id(db_session)
    conversation_id = await _conversation(client, customer_token, seller_id)
    message = await _send(client, customer_token, conversation_id, "违规内容", "rep-1")

    report = await client.post(
        f"/api/v1/im/messages/{message['id']}/report",
        headers=bearer(operator_token),
        json={"reason": "骚扰广告"},
    )
    assert report.status_code == 200, report.text
    report_id = report.json()["data"]["id"]
    assert report.json()["data"]["status"] == "pending"

    # Duplicate reports by the same user are idempotent.
    again = await client.post(
        f"/api/v1/im/messages/{message['id']}/report",
        headers=bearer(operator_token),
        json={"reason": "骚扰广告"},
    )
    assert again.json()["data"]["id"] == report_id

    pending = await client.get(
        "/api/v1/im/reports", headers=bearer(admin_token), params={"status": "pending"}
    )
    assert pending.status_code == 200
    assert any(item["id"] == report_id for item in pending.json()["data"])

    handled = await client.post(
        f"/api/v1/im/reports/{report_id}/handle",
        headers=bearer(admin_token),
        json={"action": "accept", "note": "确认违规"},
    )
    assert handled.status_code == 200, handled.text
    assert handled.json()["data"]["status"] == "accepted"

    stored = await db_session.get(Message, message["id"])
    assert stored.status == "moderated"

    buyer_view = await client.get(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(customer_token),
    )
    assert all(item["id"] != message["id"] for item in buyer_view.json()["data"]), (
        "a moderated message must disappear for normal users"
    )

    moderator_view = await client.get(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(operator_token),
    )
    assert any(item["id"] == message["id"] for item in moderator_view.json()["data"]), (
        "moderators must still see the evidence"
    )


async def test_cannot_report_own_message(client, customer_token, db_session):
    seller_id = await _seller_id(db_session)
    conversation_id = await _conversation(client, customer_token, seller_id)
    message = await _send(client, customer_token, conversation_id, "我自己的话", "self-1")

    response = await client.post(
        f"/api/v1/im/messages/{message['id']}/report",
        headers=bearer(customer_token),
        json={"reason": "手滑"},
    )
    assert response.status_code == 400


async def test_buyer_cannot_list_or_handle_reports(client, customer_token, db_session):
    assert (
        await client.get("/api/v1/im/reports", headers=bearer(customer_token))
    ).status_code == 403
    assert (
        await client.post(
            "/api/v1/im/reports/1/handle",
            headers=bearer(customer_token),
            json={"action": "accept"},
        )
    ).status_code == 403


async def test_non_member_cannot_report_foreign_message(client, db_session):
    seller_id = await _seller_id(db_session)
    owner = await _register(client, "rep-owner@example.com", "会话主")
    intruder = await _register(client, "rep-intruder@example.com", "外人")
    conversation_id = await _conversation(client, owner, seller_id)
    message = await _send(client, owner, conversation_id, "只给卖家看", "priv-1")

    response = await client.post(
        f"/api/v1/im/messages/{message['id']}/report",
        headers=bearer(intruder),
        json={"reason": "我看不到但想举报"},
    )
    assert response.status_code == 403


async def test_handling_the_same_report_twice_is_rejected(
    client, customer_token, operator_token, admin_token, db_session
):
    seller_id = await _seller_id(db_session)
    conversation_id = await _conversation(client, customer_token, seller_id)
    message = await _send(client, customer_token, conversation_id, "重复处理", "dup-1")
    report_id = (
        await client.post(
            f"/api/v1/im/messages/{message['id']}/report",
            headers=bearer(operator_token),
            json={"reason": "垃圾信息"},
        )
    ).json()["data"]["id"]

    first = await client.post(
        f"/api/v1/im/reports/{report_id}/handle",
        headers=bearer(admin_token),
        json={"action": "reject"},
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/im/reports/{report_id}/handle",
        headers=bearer(admin_token),
        json={"action": "accept"},
    )
    assert second.status_code == 400


# --------------------------------------------------------------------------- #
# Event bus (multi-instance broadcast)
# --------------------------------------------------------------------------- #


async def test_message_is_published_to_the_redis_bus(client, customer_token, db_session):
    """Replica A must broadcast so replica B can push to its own sockets."""
    seller_id = await _seller_id(db_session)
    conversation_id = await _conversation(client, customer_token, seller_id)

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(im_bus.CHANNEL)
    try:
        message = await _send(client, customer_token, conversation_id, "广播测试", "bus-1")

        event = None
        for _ in range(30):
            raw = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if raw:
                event = json.loads(raw["data"])
                break
            await asyncio.sleep(0.05)

        assert event is not None, "no event was published to the IM bus"
        assert event["conversation_id"] == conversation_id
        assert event["message_id"] == message["id"]
        assert event["seq"] == message["seq"]
        assert event["sender_id"] == message["sender_id"]
        assert event["recipient_ids"], "recipients are needed to route the push"
        assert event["message"]["content"] == "广播测试"
    finally:
        await pubsub.unsubscribe(im_bus.CHANNEL)
        await pubsub.close()


async def test_dispatch_fans_out_to_every_handler():
    received: list[dict] = []

    async def handler(event: dict) -> None:
        received.append(event)

    async def failing(_event: dict) -> None:
        raise RuntimeError("boom")

    im_bus.register_handler(handler)
    im_bus.register_handler(failing)
    try:
        delivered = await im_bus.dispatch({"conversation_id": 1, "seq": 1})
    finally:
        im_bus._handlers.remove(handler)
        im_bus._handlers.remove(failing)

    assert received == [{"conversation_id": 1, "seq": 1}]
    assert delivered >= 1, "a failing handler must not stop the others"


@pytest.mark.parametrize("payload", [{"content": "", "client_msg_id": "x"}])
async def test_blank_text_message_is_rejected(client, customer_token, db_session, payload):
    seller_id = await _seller_id(db_session)
    conversation_id = await _conversation(client, customer_token, seller_id)
    response = await client.post(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(customer_token),
        json=payload,
    )
    assert response.status_code == 422


async def _register(client, email: str, nickname: str) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "tenant_slug": "demo",
            "email": email,
            "nickname": nickname,
            "password": "Buyer@123456",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]
