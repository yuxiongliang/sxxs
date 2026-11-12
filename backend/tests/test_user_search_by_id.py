"""按用户编号（public_id）精确搜索。"""

from __future__ import annotations

from tests.conftest import bearer


async def test_search_users_by_public_id(client, admin_token):
    created = await client.post(
        "/api/v1/users",
        headers=bearer(admin_token),
        json={
            "username": "search_by_pid",
            "nickname": "编号搜索",
            "email": "search_by_pid@example.com",
            "role": "viewer",
            "status": "active",
            "password": "SearchPid@123456",
        },
    )
    public_id = created.json()["data"]["public_id"]

    hit = await client.get(
        "/api/v1/users", headers=bearer(admin_token), params={"public_id": public_id}
    )
    assert hit.status_code == 200, hit.text
    rows = hit.json()["data"]["list"]
    assert len(rows) == 1
    assert rows[0]["public_id"] == public_id

    # 编号是精确匹配：随便改一个字符就不该命中
    miss = await client.get(
        "/api/v1/users",
        headers=bearer(admin_token),
        params={"public_id": public_id[:-1] + ("0" if public_id[-1] != "0" else "1")},
    )
    assert miss.json()["data"]["list"] == []

    # 关键词框里粘贴编号也能搜到（走 ilike）
    keyword = await client.get(
        "/api/v1/users", headers=bearer(admin_token), params={"keyword": public_id}
    )
    codes = [row["public_id"] for row in keyword.json()["data"]["list"]]
    assert public_id in codes
