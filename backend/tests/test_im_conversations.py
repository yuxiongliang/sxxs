"""IM conversation isolation, ordering and idempotency.

Plan §18 acceptance criteria covered:
  #11 buyers/sellers only see their own conversations; cross access -> 403/404
  #13 a duplicated client_msg_id must not create a second message
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.seller import Seller
from tests.conftest import bearer


async def _seller_id(db_session, tenant_id: int = 1) -> int:
    seller = (
        await db_session.execute(
            select(Seller).where(Seller.tenant_id == tenant_id, Seller.status == "active")
        )
    ).scalars().first()
    assert seller is not None, "seed data must contain an active seller"
    return seller.id


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


async def _new_conversation(client, token: str, seller_id: int) -> int:
    response = await client.post(
        "/api/v1/im/conversations",
        headers=bearer(token),
        json={"seller_id": seller_id},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


async def test_customer_can_start_a_conversation(client, customer_token, db_session):
    seller_id = await _seller_id(db_session)
    conversation_id = await _new_conversation(client, customer_token, seller_id)

    listed = await client.get("/api/v1/im/conversations", headers=bearer(customer_token))
    assert listed.status_code == 200
    assert any(item["id"] == conversation_id for item in listed.json()["data"])


async def test_message_seq_is_monotonic(client, customer_token, db_session):
    seller_id = await _seller_id(db_session)
    conversation_id = await _new_conversation(client, customer_token, seller_id)

    for index in range(3):
        response = await client.post(
            f"/api/v1/im/conversations/{conversation_id}/messages",
            headers=bearer(customer_token),
            json={"content": f"第 {index} 条", "client_msg_id": f"c-{index}"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["seq"] == index + 1

    messages = await client.get(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(customer_token),
    )
    seqs = [item["seq"] for item in messages.json()["data"]]
    assert seqs == [1, 2, 3]


async def test_duplicate_client_msg_id_is_idempotent(client, customer_token, db_session):
    """Acceptance #13: retrying the same client_msg_id must not duplicate."""
    seller_id = await _seller_id(db_session)
    conversation_id = await _new_conversation(client, customer_token, seller_id)

    payload = {"content": "重试消息", "client_msg_id": "retry-1"}
    first = await client.post(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(customer_token),
        json=payload,
    )
    second = await client.post(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(customer_token),
        json=payload,
    )
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["data"]["id"] == second.json()["data"]["id"]

    messages = await client.get(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(customer_token),
    )
    assert len(messages.json()["data"]) == 1


async def test_after_seq_returns_only_the_gap(client, customer_token, db_session):
    seller_id = await _seller_id(db_session)
    conversation_id = await _new_conversation(client, customer_token, seller_id)
    for index in range(4):
        await client.post(
            f"/api/v1/im/conversations/{conversation_id}/messages",
            headers=bearer(customer_token),
            json={"content": f"m{index}", "client_msg_id": f"seq-{index}"},
        )

    response = await client.get(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        params={"after_seq": 2},
        headers=bearer(customer_token),
    )
    assert response.status_code == 200
    assert [item["seq"] for item in response.json()["data"]] == [3, 4]


async def test_other_buyer_cannot_read_the_conversation(client, customer_token, db_session):
    """Acceptance #11: buyer B must not read buyer A's conversation."""
    seller_id = await _seller_id(db_session)
    conversation_id = await _new_conversation(client, customer_token, seller_id)
    await client.post(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(customer_token),
        json={"content": "私密消息", "client_msg_id": "secret-1"},
    )

    intruder = await _register(client, "im-intruder@example.com", "入侵者")

    read = await client.get(
        f"/api/v1/im/conversations/{conversation_id}/messages", headers=bearer(intruder)
    )
    assert read.status_code in {403, 404}

    write = await client.post(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(intruder),
        json={"content": "我要插话", "client_msg_id": "intrude-1"},
    )
    assert write.status_code in {403, 404}

    listed = await client.get("/api/v1/im/conversations", headers=bearer(intruder))
    assert listed.status_code == 200
    assert all(item["id"] != conversation_id for item in listed.json()["data"])


async def test_seller_sees_buyer_message_unread_count(
    client, customer_token, operator_token, db_session
):
    seller_id = await _seller_id(db_session)
    conversation_id = await _new_conversation(client, customer_token, seller_id)
    await client.post(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(customer_token),
        json={"content": "卖家你好", "client_msg_id": "hello-1"},
    )

    seller_view = await client.get("/api/v1/im/conversations", headers=bearer(operator_token))
    assert seller_view.status_code == 200
    conversation = next(
        (item for item in seller_view.json()["data"] if item["id"] == conversation_id), None
    )
    assert conversation is not None, "the seller must see conversations addressed to them"
    assert conversation["seller_unread_count"] >= 1


async def test_conversation_for_unknown_seller_is_rejected(client, customer_token):
    response = await client.post(
        "/api/v1/im/conversations", headers=bearer(customer_token), json={"seller_id": 999_999}
    )
    assert response.status_code in {400, 404}


async def test_ws_ticket_is_issued_for_authenticated_member(client, customer_token):
    response = await client.post("/api/v1/im/ws-ticket", headers=bearer(customer_token))
    assert response.status_code == 200, response.text
    assert response.json()["data"].get("ticket")


@pytest.mark.parametrize("content", ["", " "])
async def test_empty_message_is_rejected(client, customer_token, db_session, content):
    seller_id = await _seller_id(db_session)
    conversation_id = await _new_conversation(client, customer_token, seller_id)
    response = await client.post(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(customer_token),
        json={"content": content, "client_msg_id": "blank-1"},
    )
    assert response.status_code == 422
