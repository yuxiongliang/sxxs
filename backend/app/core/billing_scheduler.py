"""Periodic SaaS billing lifecycle runner.

Runs ``billing.run_billing_cycle`` inside the app process so expired trials and
paid terms are invoiced (and unpaid tenants downgraded) without an external
cron. Every replica may run it: the cycle is idempotent because billing a term
moves ``current_period_end`` into the future.

Set ``BILLING_SCHEDULER_ENABLED=false`` when a release pipeline drives the
cycle instead (for example a Kubernetes CronJob calling
``POST /api/v1/platform/billing/run-cycle``).
"""

from __future__ import annotations

import asyncio

import structlog

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.services import billing as billing_service

logger = structlog.get_logger(__name__)

_task: asyncio.Task[None] | None = None


async def run_once() -> dict[str, int]:
    """Run one billing cycle against a fresh session (safe to call directly)."""
    async with AsyncSessionLocal() as session:
        summary = await billing_service.run_billing_cycle(session)
    logger.info("billing_cycle_finished", **summary)
    return summary


async def _loop() -> None:
    interval = max(60, settings.billing_scheduler_interval_seconds)
    while True:
        try:
            await run_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("billing_cycle_failed", error=str(exc))
        await asyncio.sleep(interval)


def start() -> None:
    """Start the background loop (idempotent, no-op when disabled)."""
    global _task
    if not settings.billing_scheduler_enabled:
        logger.info("billing_scheduler_disabled")
        return
    if _task is not None and not _task.done():
        return
    _task = asyncio.create_task(_loop())
    logger.info(
        "billing_scheduler_started",
        interval_seconds=settings.billing_scheduler_interval_seconds,
        grace_days=settings.billing_grace_days,
    )


async def stop() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001 - shutdown must not raise
        logger.warning("billing_scheduler_shutdown_failed", error=str(exc))
    _task = None
