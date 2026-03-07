"""A2A client for communicating with sub-agents via JSON-RPC 2.0.

Sends messages to Recruitment, Employee Services, and Analytics agents
over HTTP using the Google A2A protocol format.
"""

import logging
import uuid
from typing import Optional

import httpx

logger = logging.getLogger("orchestrator.a2a_client")


class A2AClient:
    """Async HTTP client for A2A JSON-RPC 2.0 communication with sub-agents."""

    def __init__(self, base_url: str, agent_name: str, timeout: float = 45.0):
        self.base_url = base_url
        self.agent_name = agent_name
        self.timeout = timeout

    async def send_message(
        self, text: str, session_id: Optional[str] = None
    ) -> dict:
        """Send an A2A message/send request to a sub-agent.

        Args:
            text: The message text to send (with role context injected).
            session_id: Optional session ID for conversation continuity.

        Returns:
            dict with keys: status, text, task_id, raw
        """
        request_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "message/send",
            "params": {
                "session_id": session_id,
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": text}],
                },
            },
        }

        logger.info(f"[A2A] \u2192 Sending to {self.agent_name} at {self.base_url}")
        logger.info(f"[A2A] \u2192 Message: {text[:150]}...")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()

            # Extract text from A2A response
            task = result.get("result", {})
            status = task.get("status", {}).get("state", "unknown")
            task_id = task.get("id", "")

            logger.info(
                f"[A2A] \u2190 Response from {self.agent_name}: "
                f"status={status}, task_id={task_id}"
            )

            # Collect all text parts from artifacts
            response_text = ""
            for artifact in task.get("artifacts", []):
                for part in artifact.get("parts", []):
                    if part.get("kind") == "text":
                        response_text += part.get("text", "")

            return {
                "status": status,
                "text": response_text,
                "task_id": task_id,
                "raw": result,
            }

        except httpx.TimeoutException:
            error_msg = (
                f"{self.agent_name} is temporarily unavailable (timed out after "
                f"{self.timeout}s). Please try again in a moment."
            )
            logger.error(f"[A2A] \u2717 Timeout calling {self.agent_name}")
            return {"status": "failed", "text": error_msg, "task_id": "", "raw": {}}

        except httpx.HTTPStatusError as e:
            error_msg = (
                f"Error from {self.agent_name}: HTTP {e.response.status_code}. "
                f"The agent may be experiencing issues."
            )
            logger.error(
                f"[A2A] \u2717 HTTP {e.response.status_code} from {self.agent_name}"
            )
            return {"status": "failed", "text": error_msg, "task_id": "", "raw": {}}

        except Exception as e:
            error_msg = f"Error communicating with {self.agent_name}: {str(e)}"
            logger.error(f"[A2A] \u2717 Exception calling {self.agent_name}: {e}")
            return {"status": "failed", "text": error_msg, "task_id": "", "raw": {}}
