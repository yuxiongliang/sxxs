"""域名所有权校验：TXT 记录的解析提供者（B6）。

与附件审核 provider 同一套路 —— 默认「不校验」，绝不在没有证据的情况下把域名判成 active。

* ``none``   —— 默认。新建域名停在 pending，等运维手动确认或把 provider 配成 dns。
* ``dns``    —— 真实 DNS 查询（需要 dnspython；没装就明确报错，不静默返回空）。
* ``static`` —— 测试注入：记录来自内存字典，测试不依赖真实 DNS。
"""

from __future__ import annotations

from typing import Protocol

from app.core.config import settings


class DomainVerifier(Protocol):
    async def txt_records(self, name: str) -> list[str]: ...


class NullVerifier:
    """不查 DNS：永远返回空列表，域名保持 pending。"""

    async def txt_records(self, name: str) -> list[str]:
        return []


class StaticVerifier:
    """测试用：TXT 记录直接放内存里。"""

    def __init__(self) -> None:
        self.records: dict[str, list[str]] = {}

    def set_records(self, name: str, values: list[str]) -> None:
        self.records[name] = list(values)

    async def txt_records(self, name: str) -> list[str]:
        return list(self.records.get(name, []))


class DnsVerifier:
    async def txt_records(self, name: str) -> list[str]:
        try:
            import dns.asyncresolver
            import dns.exception
        except ImportError as exc:
            raise RuntimeError(
                "DNS 校验需要 dnspython：在 backend 目录执行 uv add dnspython"
            ) from exc

        resolver = dns.asyncresolver.Resolver()
        try:
            answer = await resolver.resolve(name, "TXT")
        except dns.exception.DNSException:
            # NXDOMAIN / 超时 / SERVFAIL 都算「这次取不到」：不在解析失败时改状态，
            # 免得一次网络抖动就把已 active 的域名打回 pending。
            return []

        values: list[str] = []
        for record in answer:
            strings = getattr(record, "strings", None)
            if strings is not None:
                values.append(b"".join(strings).decode("utf-8", "replace"))
                continue
            values.append(record.to_text().strip('"'))
        return values


_verifiers: dict[str, DomainVerifier] = {}


def get_verifier() -> DomainVerifier:
    """按 settings.domain_verify_provider 取校验器（同进程内复用，测试可注入记录）。"""
    provider = (settings.domain_verify_provider or "none").strip().lower()
    cached = _verifiers.get(provider)
    if cached is not None:
        return cached

    if provider == "dns":
        verifier: DomainVerifier = DnsVerifier()
    elif provider == "static":
        verifier = StaticVerifier()
    else:
        verifier = NullVerifier()
    _verifiers[provider] = verifier
    return verifier
