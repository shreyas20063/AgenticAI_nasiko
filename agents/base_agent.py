"""
Base Agent class. All specialized HR agents inherit from this.
Provides: LLM interaction, tool execution with guardrails, audit logging.
"""

from abc import ABC, abstractmethod
from typing import Optional, Any
from openai import AsyncOpenAI
from config import get_settings
from security.tool_guardrails import validate_tool_call, GuardrailResult
from security.prompt_guard import validate_user_input
from security.rbac import is_tool_allowed, Role
from tools.base_tool import BaseTool, ToolResult
import structlog
import json

logger = structlog.get_logger()
settings = get_settings()

# ============================================================
# Error Recovery: Retry + Circuit Breaker
# ============================================================

import asyncio
import time
from collections import defaultdict

class CircuitBreaker:
    """
    Circuit breaker pattern for LLM calls.
    States: CLOSED (normal), OPEN (failing, reject calls), HALF_OPEN (testing recovery).
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.success_count = 0

    def can_execute(self) -> bool:
        """Check if calls are allowed."""
        if self.state == self.CLOSED:
            return True
        if self.state == self.OPEN:
            # Check if recovery timeout has elapsed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = self.HALF_OPEN
                logger.info("circuit_breaker_half_open")
                return True
            return False
        # HALF_OPEN: allow one test call
        return True

    def record_success(self):
        """Record a successful call."""
        if self.state == self.HALF_OPEN:
            self.state = self.CLOSED
            self.failure_count = 0
            logger.info("circuit_breaker_closed")
        self.success_count += 1

    def record_failure(self):
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
            logger.warning(
                "circuit_breaker_opened",
                failures=self.failure_count,
                threshold=self.failure_threshold,
            )

    @property
    def is_open(self) -> bool:
        return self.state == self.OPEN


# Global circuit breaker for LLM calls
_llm_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRY_MAX_DELAY = 15.0  # seconds
RETRYABLE_ERRORS = (
    ConnectionError,
    TimeoutError,
    # openai specific errors
)

# ============================================================
# Token Budget Enforcement
# ============================================================

# Model context windows (conservative estimates leaving room for response)
MODEL_CONTEXT_LIMITS = {
    "gpt-4o-mini": 120000,
    "gpt-4o": 120000,
    "gpt-4": 8000,
    "gpt-3.5-turbo": 14000,
    "llama-3.3-70b-versatile": 28000,  # Groq Llama - 32k context, leave room
    "llama-3.1-70b-versatile": 28000,
    "llama-3.1-8b-instant": 28000,
    "mixtral-8x7b-32768": 28000,
}

# Reserve tokens for LLM response
RESPONSE_TOKEN_RESERVE = 4096


def _estimate_tokens(text: str) -> int:
    """
    Estimate token count for a string.
    Uses a fast heuristic: ~4 chars per token for English text.
    More accurate than nothing, faster than tiktoken for every call.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def _count_message_tokens(messages: list[dict]) -> int:
    """Estimate total tokens across all messages."""
    total = 0
    for msg in messages:
        # Each message has ~4 tokens of overhead (role, delimiters)
        total += 4
        content = msg.get("content", "")
        if isinstance(content, str):
            total += _estimate_tokens(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    total += _estimate_tokens(item["text"])
    return total


def _get_context_limit() -> int:
    """Get context window limit for the current model."""
    model = settings.llm_model
    # Check for partial matches (e.g., "llama-3.3" in model name)
    for model_key, limit in MODEL_CONTEXT_LIMITS.items():
        if model_key in model:
            return limit - RESPONSE_TOKEN_RESERVE
    # Default: assume 28k context - safe fallback
    return 28000 - RESPONSE_TOKEN_RESERVE


def _truncate_messages_to_budget(messages: list[dict], max_tokens: int) -> list[dict]:
    """
    Truncate messages to fit within token budget.
    Strategy:
    1. Always keep system message(s) (first 1-2 messages)
    2. Always keep the last user message
    3. Trim middle messages (conversation history) if needed
    4. If still over budget, truncate system message content
    """
    if not messages:
        return messages

    current_tokens = _count_message_tokens(messages)
    if current_tokens <= max_tokens:
        return messages

    logger.warning(
        "token_budget_exceeded",
        current=current_tokens,
        limit=max_tokens,
        message_count=len(messages),
    )

    # Separate system messages, middle messages, and last user message
    system_msgs = []
    middle_msgs = []
    last_msg = None

    for i, msg in enumerate(messages):
        if msg.get("role") == "system":
            system_msgs.append(msg)
        elif i == len(messages) - 1:
            last_msg = msg
        else:
            middle_msgs.append(msg)

    # Try removing middle messages one by one (oldest first)
    while middle_msgs and _count_message_tokens(system_msgs + middle_msgs + ([last_msg] if last_msg else [])) > max_tokens:
        removed = middle_msgs.pop(0)
        logger.debug("trimmed_message", role=removed.get("role"))

    result = system_msgs + middle_msgs + ([last_msg] if last_msg else [])

    # If still over budget, truncate system message content
    if _count_message_tokens(result) > max_tokens and system_msgs:
        for msg in result:
            if msg.get("role") == "system" and isinstance(msg.get("content"), str):
                excess = _count_message_tokens(result) - max_tokens
                chars_to_trim = excess * 4  # rough conversion back
                if chars_to_trim > 0 and len(msg["content"]) > chars_to_trim:
                    msg["content"] = msg["content"][:len(msg["content"]) - chars_to_trim] + "\n\n[Content truncated to fit context window]"

    final_tokens = _count_message_tokens(result)
    logger.info(
        "token_budget_enforced",
        original=current_tokens,
        final=final_tokens,
        messages_kept=len(result),
    )

    return result


class AgentContext:
    """Immutable context for the current agent invocation."""
    def __init__(
        self,
        tenant_id: str,
        user_id: str,
        user_role: Role,
        conversation_id: str = "",
        db_session: Any = None,
        request_id: str = "",
    ):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.user_role = user_role
        self.conversation_id = conversation_id
        self.db = db_session
        self.request_id = request_id or str(__import__('uuid').uuid4())
        self.conversation_history: list[dict] = []


class AgentResponse:
    """Structured response from an agent."""
    def __init__(self):
        self.message: str = ""
        self.actions_taken: list[dict] = []
        self.requires_approval: bool = False
        self.approval_action: Optional[dict] = None
        self.sources: list[dict] = []
        self.escalated: bool = False
        self.escalation_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "actions_taken": self.actions_taken,
            "requires_approval": self.requires_approval,
            "approval_action": self.approval_action,
            "sources": self.sources,
            "escalated": self.escalated,
            "escalation_reason": self.escalation_reason,
        }


class BaseAgent(ABC):
    """
    Base class for all HR agents.
    Enforces:
    - System/user prompt separation
    - Tool call guardrails
    - PII-safe logging
    - Scoped tool access
    """

    name: str = "base_agent"
    description: str = "Base HR agent"
    system_prompt: str = ""
    available_tools: dict[str, BaseTool] = {}

    # Shared singleton OpenAI client across all agents (connection pooling)
    _shared_client: AsyncOpenAI = None

    @classmethod
    def _get_shared_client(cls) -> AsyncOpenAI:
        """Get or create the shared AsyncOpenAI client."""
        if cls._shared_client is None:
            cls._shared_client = AsyncOpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
            )
        return cls._shared_client

    def __init__(self):
        self._client = self._get_shared_client()

    @abstractmethod
    async def process(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Process user input and return a response."""
        pass

    async def _call_llm(
        self,
        messages: list[dict],
        tools: list[dict] = None,
        temperature: float = None,
    ) -> dict:
        """
        Call the LLM with strict system/user separation.
        System prompt is ALWAYS first and immutable.
        Enforces token budget before sending.
        Includes retry with exponential backoff and circuit breaker.
        """
        # Check circuit breaker
        if not _llm_circuit_breaker.can_execute():
            logger.error("circuit_breaker_open_rejecting_call", agent=self.name)
            raise RuntimeError(
                "LLM service is temporarily unavailable. Please try again in a moment."
            )

        # Enforce token budget
        max_input_tokens = _get_context_limit()
        messages = _truncate_messages_to_budget(messages, max_input_tokens)

        kwargs = {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": temperature or settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # Retry with exponential backoff
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.chat.completions.create(**kwargs)
                _llm_circuit_breaker.record_success()
                return response

            except Exception as e:
                last_error = e
                _llm_circuit_breaker.record_failure()

                # Don't retry on non-retryable errors (auth, validation, etc.)
                error_str = str(e).lower()
                if any(x in error_str for x in ["401", "403", "invalid_api_key", "authentication"]):
                    logger.error("llm_auth_error", agent=self.name, error=str(e))
                    raise

                if attempt < MAX_RETRIES - 1:
                    delay = min(
                        RETRY_BASE_DELAY * (2 ** attempt),
                        RETRY_MAX_DELAY,
                    )
                    logger.warning(
                        "llm_call_retry",
                        agent=self.name,
                        attempt=attempt + 1,
                        max_retries=MAX_RETRIES,
                        delay=delay,
                        error=str(e)[:200],
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "llm_call_failed_all_retries",
                        agent=self.name,
                        attempts=MAX_RETRIES,
                        error=str(e)[:200],
                    )

        raise last_error

    async def _execute_tool(
        self,
        tool_name: str,
        parameters: dict,
        context: AgentContext,
    ) -> tuple[ToolResult, GuardrailResult]:
        """
        Execute a tool with full guardrail validation.
        Returns both the tool result and the guardrail check result.
        """
        # Guardrail check
        guardrail = validate_tool_call(
            agent_name=self.name,
            tool_name=tool_name,
            parameters=parameters,
            user_role=context.user_role,
            tenant_id=context.tenant_id,
        )

        if not guardrail.allowed:
            logger.warning(
                "tool_call_denied",
                agent=self.name,
                tool=tool_name,
                reason=guardrail.denial_reason,
            )
            return ToolResult(
                success=False,
                error=guardrail.denial_reason,
                tool_name=tool_name,
            ), guardrail

        if guardrail.requires_approval:
            logger.info("tool_call_needs_approval", agent=self.name, tool=tool_name)
            return ToolResult(
                success=False,
                error="Requires human approval",
                tool_name=tool_name,
            ), guardrail

        # Execute if allowed
        tool = self.available_tools.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not available",
                tool_name=tool_name,
            ), guardrail

        tool_context = {
            "tenant_id": context.tenant_id,
            "user_id": context.user_id,
            "user_role": context.user_role.value,
            "db": context.db,
        }

        result = await tool.execute(parameters, tool_context)
        return result, guardrail

    def _build_tool_schemas(self) -> list[dict]:
        """Build OpenAI function-calling tool schemas."""
        schemas = []
        for tool in self.available_tools.values():
            schema = tool.get_schema()
            schemas.append({
                "type": "function",
                "function": schema,
            })
        return schemas

    async def _process_with_tools(
        self,
        user_input: str,
        context: AgentContext,
        extra_context: str = "",
    ) -> AgentResponse:
        """
        Full agent loop: LLM call -> tool calls -> final response.
        Handles multi-turn tool calling with guardrails.
        """
        response = AgentResponse()

        # Validate user input for injection
        is_safe, sanitized, warning = validate_user_input(user_input)
        if not is_safe:
            response.message = f"I cannot process this request. {warning}"
            return response

        messages = [
            {"role": "system", "content": self.system_prompt},
        ]

        if extra_context:
            messages.append({"role": "system", "content": extra_context})

        # Inject conversation history for multi-turn awareness
        if hasattr(context, 'conversation_history') and context.conversation_history:
            for hist_msg in context.conversation_history[-6:]:  # Last 6 messages
                role = hist_msg.get("role", "user")
                content = hist_msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content[:1000]})

        messages.append({"role": "user", "content": sanitized})

        tool_schemas = self._build_tool_schemas() if self.available_tools else None

        # Agent loop (max 5 iterations to prevent infinite loops)
        for iteration in range(5):
            llm_response = await self._call_llm(messages, tools=tool_schemas)
            choice = llm_response.choices[0]

            if choice.finish_reason == "tool_calls":
                # Process each tool call
                tool_calls = choice.message.tool_calls
                messages.append(choice.message)

                for tc in tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        logger.warning("tool_call_json_parse_failed", tool=fn_name, raw=tc.function.arguments[:200])
                        fn_args = {}

                    tool_result, guardrail = await self._execute_tool(
                        fn_name, fn_args, context
                    )

                    if guardrail.requires_approval:
                        response.requires_approval = True
                        response.approval_action = {
                            "tool": fn_name,
                            "parameters": fn_args,
                            "reason": guardrail.warnings,
                        }
                        response.message = (
                            f"I'd like to {fn_name} but this requires your approval. "
                            f"Details: {json.dumps(fn_args, indent=2)}"
                        )
                        return response

                    response.actions_taken.append({
                        "tool": fn_name,
                        "parameters": fn_args,
                        "success": tool_result.success,
                        "result": tool_result.data if tool_result.success else tool_result.error,
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_result.data if tool_result.success else {"error": tool_result.error}),
                    })

            else:
                # Final text response
                response.message = choice.message.content or ""
                break

        return response
