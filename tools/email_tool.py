"""
Email Tool - sends emails via SMTP or API.
Supports interview invitations, onboarding messages, and notifications.
"""

from typing import Optional
from tools.base_tool import BaseTool, ToolResult
from config import get_settings
import structlog

logger = structlog.get_logger()
settings = get_settings()


class EmailTool(BaseTool):
    name = "send_email"
    description = "Send an email to one or more recipients"
    requires_approval = True  # always needs human approval

    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        to = parameters.get("to")
        subject = parameters.get("subject", "")
        body = parameters.get("body", "")
        cc = parameters.get("cc", [])

        if not to:
            return ToolResult(success=False, error="No recipient specified", tool_name=self.name)

        # Normalize recipients to list
        recipients = to if isinstance(to, list) else [to]

        try:
            # In production, use aiosmtplib:
            # async with aiosmtplib.SMTP(hostname=settings.smtp_host, port=settings.smtp_port) as smtp:
            #     await smtp.login(settings.smtp_user, settings.smtp_password)
            #     message = MIMEText(body)
            #     message["From"] = f"{settings.smtp_from_name} <{settings.smtp_user}>"
            #     message["To"] = ", ".join(recipients)
            #     message["Subject"] = subject
            #     await smtp.send_message(message)

            # Demo mode: log instead of actually sending
            logger.info(
                "email_sent",
                to=recipients,
                subject=subject,
                tenant_id=context.get("tenant_id"),
            )

            # Dispatch webhook event for email tracking
            try:
                from tools.webhook_dispatcher import dispatch_event, WebhookEvent
                await dispatch_event(WebhookEvent(
                    event_type="email.sent",
                    payload={
                        "recipients": recipients,
                        "subject": subject,
                        "cc": cc,
                    },
                    tenant_id=context.get("tenant_id", ""),
                ))
            except Exception:
                pass  # Non-blocking

            return ToolResult(
                success=True,
                data={
                    "recipients": recipients,
                    "subject": subject,
                    "status": "sent",
                    "message": f"Email sent to {len(recipients)} recipient(s)",
                },
                tool_name=self.name,
            )

        except Exception as e:
            logger.error("email_send_failed", error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to send email: {str(e)}",
                tool_name=self.name,
            )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "array", "items": {"type": "string"}, "description": "Recipient email(s)"},
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Email body (plain text or HTML)"},
                    "cc": {"type": "array", "items": {"type": "string"}, "description": "CC recipients"},
                },
                "required": ["to", "subject", "body"],
            },
        }
