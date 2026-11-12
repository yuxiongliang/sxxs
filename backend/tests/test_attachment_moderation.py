"""附件审核 + 三权分离（审核结论 / 强制下架 / 租户软删）。

覆盖的风险点：
* 上传后自动进审核管道，默认 null provider 放行；
* mock provider 按文件名给确定性结论（E2E 可复现）；
* 驳回后「上传者本人 + 管理员」仍可见，其他人不可见（取证与隐私的平衡）；
* 租户软删后业务不可见，但平台审核仍能看到；
* 平台强制下架后对所有人隐藏；
* failMode：KYC 场景审核失败必须拦（closed），IM 场景必须放行（open）；
* 签名 URL 可兑换、被篡改则拒绝；
* 同一 checksum 只审一次（去重）。
"""

from __future__ import annotations

import base64

from tests.conftest import bearer

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _file(name: str = "photo.png", payload: bytes = PNG_1PX):
    return {"file": (name, payload, "image/png")}


async def _set_moderation(client, platform_token, config: dict) -> None:
    response = await client.put(
        "/api/v1/platform/settings/moderation",
        headers=bearer(platform_token),
        json={"enabled": True, "config": config},
    )
    assert response.status_code == 200, response.text


async def _upload(client, token, *, name="photo.png", payload=None):
    return await client.post(
        "/api/v1/attachments/upload",
        headers=bearer(token),
        files=_file(name, payload or PNG_1PX),
        data={"source_module": "manual"},
    )


async def test_upload_is_moderated_and_approved_by_default(client, admin_token):
    response = await _upload(client, admin_token)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["review_status"] == "approved"
    assert data["visibility"] == "tenant"
    assert data["uploader_role"] == "admin"


async def test_mock_provider_rejects_by_filename(client, admin_token, platform_token):
    await _set_moderation(client, platform_token, {"provider": "mock"})

    rejected = await _upload(client, admin_token, name="reject_me.png")
    assert rejected.status_code == 200, rejected.text
    rejected_data = rejected.json()["data"]
    assert rejected_data["review_status"] == "rejected"
    assert rejected_data["reject_reason"]

    # 不同内容 → 不同 checksum，避免命中「按内容去重」的缓存（这是设计行为）
    approved = await _upload(client, admin_token, name="ok.png", payload=PNG_1PX + b"\x01")
    assert approved.json()["data"]["review_status"] == "approved"


async def test_fail_mode_closed_for_kyc_and_open_for_im(client, operator_token, platform_token):
    # remote provider 但 endpoint 为空 → 必然抛错，正好用来验证 failMode 分级
    await _set_moderation(client, platform_token, {"provider": "remote", "endpoint": ""})

    kyc = await client.post(
        "/api/v1/media/upload",
        headers=bearer(operator_token),
        files=_file("id-card.png", PNG_1PX + b"\x03"),
        data={"scope": "kyc"},
    )
    assert kyc.status_code == 200, kyc.text
    assert kyc.json()["data"]["review_status"] == "rejected"

    im = await client.post(
        "/api/v1/media/upload",
        headers=bearer(operator_token),
        files=_file("chat.png", PNG_1PX + b"\x02"),
        data={"scope": "im"},
    )
    assert im.status_code == 200, im.text
    assert im.json()["data"]["review_status"] == "approved"


async def test_rejected_attachment_stays_visible_to_admin_but_not_others(
    client, admin_token, customer_token, platform_token
):
    await _set_moderation(client, platform_token, {"provider": "mock"})
    created = await _upload(client, admin_token, name="reject_secret.png")
    attachment_id = created.json()["data"]["id"]

    # 租户管理员（有 attachment:read）仍能列出并下载（取证）
    listing = await client.get("/api/v1/attachments", headers=bearer(admin_token))
    ids = [item["id"] for item in listing.json()["data"]["list"]]
    assert attachment_id in ids

    download = await client.get(
        f"/api/v1/attachments/{attachment_id}/download", headers=bearer(admin_token)
    )
    assert download.status_code == 200

    # 买家没有 attachment:read，直接打接口应被权限挡住
    other = await client.get(
        f"/api/v1/attachments/{attachment_id}/download", headers=bearer(customer_token)
    )
    assert other.status_code in (403, 404)


async def test_takedown_hides_from_tenant_but_platform_still_sees(
    client, admin_token, platform_token
):
    created = await _upload(client, admin_token, name="takedown.png")
    attachment_id = created.json()["data"]["id"]

    taken = await client.post(
        f"/api/v1/platform/moderation/{attachment_id}/takedown",
        headers=bearer(platform_token),
    )
    assert taken.status_code == 200, taken.text
    assert taken.json()["data"]["admin_hidden"] is True

    download = await client.get(
        f"/api/v1/attachments/{attachment_id}/download", headers=bearer(admin_token)
    )
    assert download.status_code == 404

    platform_view = await client.get(
        f"/api/v1/platform/moderation/{attachment_id}/download",
        headers=bearer(platform_token),
    )
    assert platform_view.status_code == 200


async def test_soft_delete_keeps_record_for_platform(client, admin_token, platform_token):
    created = await _upload(client, admin_token, name="soft.png")
    attachment_id = created.json()["data"]["id"]

    deleted = await client.delete(
        f"/api/v1/attachments/{attachment_id}", headers=bearer(admin_token)
    )
    assert deleted.status_code == 200, deleted.text

    listing = await client.get("/api/v1/attachments", headers=bearer(admin_token))
    assert attachment_id not in [item["id"] for item in listing.json()["data"]["list"]]

    recycle = await client.get("/api/v1/attachments?recycle=true", headers=bearer(admin_token))
    assert attachment_id in [item["id"] for item in recycle.json()["data"]["list"]]

    platform_queue = await client.get(
        "/api/v1/platform/moderation/queue?review_status=approved",
        headers=bearer(platform_token),
    )
    assert attachment_id in [item["id"] for item in platform_queue.json()["data"]["list"]]


async def test_signed_url_roundtrip_and_tamper(client, admin_token):
    created = await _upload(client, admin_token, name="signed.png")
    attachment_id = created.json()["data"]["id"]

    signed = await client.post(
        f"/api/v1/attachments/{attachment_id}/signed-url", headers=bearer(admin_token)
    )
    assert signed.status_code == 200, signed.text
    url = signed.json()["data"]["url"]

    ok = await client.get(url)
    assert ok.status_code == 200

    tampered = await client.get(url[:-3] + "abc")
    assert tampered.status_code == 404


async def test_moderation_logs_and_platform_stats(client, admin_token, platform_token):
    created = await _upload(client, admin_token, name="logged.png")
    attachment_id = created.json()["data"]["id"]

    logs = await client.get(
        f"/api/v1/platform/moderation/{attachment_id}/logs",
        headers=bearer(platform_token),
    )
    assert logs.status_code == 200, logs.text
    entries = logs.json()["data"]
    assert entries, "审核必须留下日志，否则无法排障/申诉"
    assert any(entry["decision"] == "approved" for entry in entries)

    stats = await client.get("/api/v1/platform/moderation/stats", headers=bearer(platform_token))
    assert stats.status_code == 200, stats.text
    assert stats.json()["data"]["approved"] >= 1
