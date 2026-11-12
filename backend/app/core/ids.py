"""全站唯一的公开 ID（对外的用户编号等）。

为什么不直接用自增主键：

* 自增 ID 会泄漏注册量、可被顺序枚举；
* 主键被大量外键引用，换主键代价极高。

所以对外发一个独立的随机串：由 secrets 生成、36 进制 20 位（约 103 bit），
理论上 36 的 20 次方约 1.3e31，任何真实业务量都碰不到上限；唯一性由数据库唯一索引兜底。
"""

from __future__ import annotations

import secrets
import string

ALPHABET = string.ascii_lowercase + string.digits
USER_PUBLIC_ID_LENGTH = 20


def new_public_id(prefix: str = "usr", length: int = USER_PUBLIC_ID_LENGTH) -> str:
    """生成 「前缀_随机 20 位」 形式的公开 ID。"""
    body = "".join(secrets.choice(ALPHABET) for _ in range(length))
    return f"{prefix}_{body}"
