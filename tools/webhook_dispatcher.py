"""
Webhook Dispatcher for external system integrations.
Provides a pluggable layer to dispatch events to external systems
(Slack, Microsoft Teams, Workday, BambooHR, etc.) via webhooks.
"""

import httpx
import json
from typing import Optional
from config import get_settings
import structlog

logger = structlog.get_logger()
settings = get_settings()


class WebhookEvent:
    """Represents an event to dispatch to external systems."""
    def __init__(
        self,
        event_type: str,
        payload: dict,
        tenant_id: str,
        source: str = "hr-platform",
    ):
        self.event_type = event_type
        self.payload = payload
        self.tenant_id = tenant_id
        self.source = source


# Registered webhook endpoints per tenant
# In production, store in DB. For demo, configurable via env.
_webhook_registry: dict[str, list[dict]] = {}


def register_webhook(tenant_id: str, url: str, events: list[str], secret: str = ""):
    """Register a webhook endpoint for a tenant."""
    if tenant_id not in _webhook_registry:
        _webhook_registry[tenant_id] = []
    _webhook_registry[tenant_id].append({
        "url": url,
        "events": events,
        "secret": secret,
        "active": True,
    })
    logger.info("webhook_registered", tenant_id=tenant_id, url=url, events=events)


async def dispatch_event(event: WebhookEvent) -> list[dict]:
    """
    Dispatch an event to all registered webhooks for the tenant.
    Returns list of dispatch results.
    """
    results = []
    hooks = _webhook_registry.get(event.tenant_id, [])

    for hook in hooks:
        if not hook["active"]:
            continue
        if event.event_type not in hook["events"] and "*" not in hook["events"]:
            continue

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    hook["url"],
                    json={
                        "event_type": event.event_type,
                        "source": event.source,
                        "tenant_id": event.tenant_id,
                        "payload": event.payload,
                    },
                    headers={"X-Webhook-Secret": hook.get("secret", "")},
                )
                results.append({
                    "url": hook["url"],
                    "status": response.status_code,
                    "success": 200 <= response.status_code < 300,
                })
        except Exception as e:
            logger.warning("webhook_dispatch_failed", url=hook["url"], error=str(e))
            results.append({
                "url": hook["url"],
                "status": 0,
                "success": False,
                "error": str(e)[:200],
            })

    if results:
        logger.info(
            "webhook_event_dispatched",
            event_type=event.event_type,
            tenant_id=event.tenant_id,
            dispatched=len(results),
            success=sum(1 for r in results if r["success"]),
        )

    return results
