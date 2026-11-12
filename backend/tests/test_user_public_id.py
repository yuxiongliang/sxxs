"""用户公开编号 public_id：随机 20 位、全站唯一、与自增主键解耦。"""

from __future__ import annotations

import re

from tests.conftest import bearer

PATTERN = re.compile(r"^usr_[a-z0-9]{20}$")


async def _create_user(client, admin_token, suffix: str):
    return await client.post(
        "/api/v1/users",
        headers=bearer(admin_token),
        json={
            "username": f"pid_user_{suffix}",
            "nickname": f"编号用户{suffix}",
            "email": f"pid_{suffix}@example.com",
            "role": "viewer",
            "status": "active",
            "password": "PublicId@123456",
        },
    )


async def test_public_id_is_random_and_globally_unique(client, admin_token):
    first = await _create_user(client, admin_token, "a")
    second = await _create_user(client, admin_token, "b")
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    first_id = first.json()["data"]["public_id"]
    second_id = second.json()["data"]["public_id"]
    assert PATTERN.match(first_id), first_id
    assert PATTERN.match(second_id), second_id
    assert first_id != second_id, "两个用户不能拿到同一个编号"


async def test_users_list_exposes_public_id(client, admin_token):
    response = await client.get("/api/v1/users?pageSize=100", headers=bearer(admin_token))
    assert response.status_code == 200, response.text
    rows = response.json()["data"]["list"]
    assert rows
    ids = [row["public_id"] for row in rows]
    assert all(PATTERN.match(item) for item in ids), ids[:3]
    assert len(set(ids)) == len(ids), "列表里出现重复编号"
