"""A2A client for communicating with sub-agents via JSON-RPC 2.0."""

import logging
import uuid
from typing import Optional

import httpx

logger = logging.getLogger("orchestrator.a2a_client")


class A2AClient:
    def __init__(self, base_url: str, agent_name: str, timeout: float = 45.0, internal_secret: str = ""):
        self.base_url = base_url
        self.agent_name = agent_name
        self.timeout = timeout
        self.internal_secret = internal_secret

    async def send_message(
        self, text: str, session_id: Optional[str] = None, user_context: str = ""
    ) -> dict:
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

        headers = {
            "Content-Type": "application/json",
            "X-Internal-Token": self.internal_secret,
        }
        if user_context:
            headers["X-User-Context"] = user_context

        logger.info(f"[A2A] → Sending to {self.agent_name} at {self.base_url}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/", json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()

            task = result.get("result", {})
            status = task.get("status", {}).get("state", "unknown")
            task_id = task.get("id", "")

            response_text = ""
            for artifact in task.get("artifacts", []):
                for part in artifact.get("parts", []):
                    if part.get("kind") == "text":
                        response_text += part.get("text", "")

            logger.info(f"[A2A] ← {self.agent_name}: status={status}")
            return {"status": status, "text": response_text, "task_id": task_id, "raw": result}

        except httpx.TimeoutException:
            logger.error(f"[A2A] ✗ Timeout calling {self.agent_name}")
            return {"status": "failed", "text": f"{self.agent_name} timed out. Please try again.", "task_id": "", "raw": {}}

        except httpx.HTTPStatusError as e:
            logger.error(f"[A2A] ✗ HTTP {e.response.status_code} from {self.agent_name}")
            if e.response.status_code == 403:
                return {"status": "failed", "text": f"{self.agent_name} rejected the request (auth failure).", "task_id": "", "raw": {}}
            return {"status": "failed", "text": f"Error from {self.agent_name}: HTTP {e.response.status_code}.", "task_id": "", "raw": {}}

        except Exception as e:
            logger.error(f"[A2A] ✗ Exception calling {self.agent_name}: {e}")
            return {"status": "failed", "text": f"Error communicating with {self.agent_name}: {str(e)}", "task_id": "", "raw": {}}
