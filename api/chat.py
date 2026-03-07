"""
Main Chat API - the primary interaction endpoint.
Users send messages, the orchestrator routes to agents, returns responses.
Conversation messages are persisted to DB for multi-turn context.
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models.user import User, Role
from models.conversation import ConversationMessage
from schemas.common import ChatRequest, ChatResponse
from api.deps import get_current_user
from orchestrator.coordinator import process_message
from agents.base_agent import AgentContext
from security.rbac import Permission, has_permission
from security.tenant_isolation import TenantContext
import uuid
import json

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# Sliding window size for conversation context
CONTEXT_WINDOW_SIZE = 10


async def _get_conversation_history(
    db: AsyncSession, conversation_id: str, tenant_id: str, limit: int = CONTEXT_WINDOW_SIZE
) -> list[dict]:
    """Retrieve recent conversation messages from DB as a sliding window."""
    result = await db.execute(
        select(ConversationMessage)
        .where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.tenant_id == tenant_id,
        )
        .order_by(ConversationMessage.created_at.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    # Reverse to chronological order (include agent_used for context-aware routing)
    return [
        {"role": m.role, "content": m.content, "agent_used": m.agent_used}
        for m in reversed(messages)
    ]


async def _save_message(
    db: AsyncSession,
    tenant_id: str,
    conversation_id: str,
    user_id: str,
    role: str,
    content: str,
    agent_used: str = None,
    intent_detected: str = None,
    turn_number: int = 0,
):
    """Persist a message to the conversation_messages table."""
    msg = ConversationMessage(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        user_id=user_id,
        role=role,
        content=content[:10000],  # truncate very long messages
        agent_used=agent_used,
        intent_detected=intent_detected,
        turn_number=turn_number,
    )
    db.add(msg)
    await db.flush()


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Main chat endpoint. Send a message, get an AI-powered HR response.
    The orchestrator detects intent and routes to specialized agents.
    Messages are persisted for multi-turn conversation memory.
    """
    if not has_permission(user.role, Permission.USE_CHAT):
        raise HTTPException(status_code=403, detail="Chat access not permitted for your role")

    # Conversation management
    conversation_id = request.conversation_id or str(uuid.uuid4())

    # Get turn number
    count_result = await db.execute(
        select(func.count(ConversationMessage.id))
        .where(ConversationMessage.conversation_id == conversation_id)
    )
    turn_number = (count_result.scalar() or 0) + 1

    # Save user message to DB
    await _save_message(
        db, user.tenant_id, conversation_id, user.id,
        role="user", content=request.message, turn_number=turn_number,
    )

    # Load sliding window of recent conversation context
    conversation_history = await _get_conversation_history(db, conversation_id, user.tenant_id)

    # Build agent context
    context = AgentContext(
        tenant_id=user.tenant_id,
        user_id=user.id,
        user_role=user.role,
        conversation_id=conversation_id,
        db_session=db,
    )

    # Process through orchestrator
    response = await process_message(
        user_input=request.message,
        context=context,
        conversation_history=conversation_history,
    )

    # Save assistant response to DB — find the source with agent routing info
    agent_name = None
    intent_name = None
    for src in (response.sources or []):
        if "agent" in src:
            agent_name = src["agent"]
            intent_name = src.get("intent")
            break
    await _save_message(
        db, user.tenant_id, conversation_id, user.id,
        role="assistant", content=response.message,
        agent_used=agent_name, intent_detected=intent_name,
        turn_number=turn_number + 1,
    )

    return ChatResponse(
        message=response.message,
        conversation_id=conversation_id,
        agent_used=agent_name,
        actions_taken=response.actions_taken,
        requires_approval=response.requires_approval,
        approval_action=response.approval_action,
        sources=response.sources,
    )


@router.get("/history/{conversation_id}")
async def get_conversation_history(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get conversation history from DB. Users can only see their own conversations."""
    query = (
        select(ConversationMessage)
        .where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.tenant_id == user.tenant_id,
        )
    )
    # Non-admin users can only view their own conversation history
    if user.role not in (Role.HR_ADMIN, Role.SUPER_ADMIN):
        query = query.where(ConversationMessage.user_id == user.id)

    result = await db.execute(query.order_by(ConversationMessage.created_at.asc()))
    messages = result.scalars().all()
    return {
        "conversation_id": conversation_id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "agent_used": m.agent_used,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.post("/approve/{conversation_id}")
async def approve_action(
    conversation_id: str,
    action_id: str = None,
    approved: bool = True,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve or deny a pending agent action.
    If approved, re-executes the tool that was waiting for approval.
    """
    if not has_permission(user.role, Permission.APPROVE_AGENT_ACTIONS):
        raise HTTPException(status_code=403, detail="You don't have approval permissions")

    from security.audit import log_agent_action

    if not approved:
        # Log denial and return
        await log_agent_action(
            db, tenant_id=user.tenant_id, user_id=user.id,
            user_role=user.role.value, agent_name="approval_system",
            action="action_denied", input_text=f"conv={conversation_id}",
            output_text="User denied the action", status="denied",
        )
        return {
            "conversation_id": conversation_id,
            "approved": False,
            "message": "Action denied. No changes were made.",
            "result": None,
        }

    # Find the most recent assistant message with an approval_action in this conversation
    result = await db.execute(
        select(ConversationMessage)
        .where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.tenant_id == user.tenant_id,
            ConversationMessage.role == "assistant",
        )
        .order_by(ConversationMessage.created_at.desc())
        .limit(1)
    )
    last_msg = result.scalar_one_or_none()

    # Try to re-execute the pending tool
    # We look for the approval_action stored in the response metadata
    # The approval_action contains: tool name, parameters, and context
    tool_result_data = None
    tool_name = action_id or "unknown"
    execution_message = "Action approved and executed."

    # Load all available tools and execute the pending action
    try:
        from tools.calendar_tool import ScheduleInterviewTool, CalendarTool
        from tools.email_tool import EmailTool
        from tools.candidate_tools import UpdateCandidateStatusTool
        from tools.helpdesk_tools import CreateTicketTool, SubmitLeaveRequestTool, UpdateTicketStatusTool
        from tools.onboarding_tools import CreateOnboardingPlanTool, UpdateTaskStatusTool, AssignTaskTool
        from tools.compliance_tools import ExportEmployeeDataTool, AnonymizeDataTool, GetAuditLogsTool

        tool_map = {
            "schedule_interview": ScheduleInterviewTool(),
            "create_calendar_event": CalendarTool(),
            "send_email": EmailTool(),
            "update_candidate_status": UpdateCandidateStatusTool(),
            "create_ticket": CreateTicketTool(),
            "submit_leave_request": SubmitLeaveRequestTool(),
            "update_ticket_status": UpdateTicketStatusTool(),
            "create_onboarding_plan": CreateOnboardingPlanTool(),
            "update_task_status": UpdateTaskStatusTool(),
            "assign_task": AssignTaskTool(),
            "export_data": ExportEmployeeDataTool(),
            "anonymize_data": AnonymizeDataTool(),
            "get_audit_logs": GetAuditLogsTool(),
        }

        tool_context = {
            "tenant_id": user.tenant_id,
            "user_id": user.id,
            "user_role": user.role.value,
            "db": db,
            "approval_override": True,
        }

        if action_id and action_id in tool_map:
            tool = tool_map[action_id]
            # Try to retrieve stored parameters from the last message metadata
            stored_params = {}
            if last_msg and last_msg.metadata:
                try:
                    meta = last_msg.metadata if isinstance(last_msg.metadata, dict) else json.loads(last_msg.metadata)
                    stored_params = meta.get("approval_params", {})
                except Exception:
                    pass

            # Execute the tool with stored or empty parameters
            tool_result = await tool.execute(stored_params, tool_context)
            tool_result_data = {
                "tool": action_id,
                "status": "executed",
                "success": tool_result.success,
                "data": tool_result.data,
            }
            if tool_result.success:
                execution_message = f"Action '{action_id}' approved and executed successfully."
                if tool_result.data:
                    execution_message += f" Result: {json.dumps(tool_result.data, default=str)[:500]}"
            else:
                execution_message = f"Action '{action_id}' approved but execution failed: {tool_result.error}"
            tool_name = action_id
        else:
            # No matching tool — still mark as approved
            tool_result_data = {"tool": action_id, "status": "approved"}
            execution_message = f"Action '{action_id or 'unknown'}' has been approved."
            tool_name = action_id or "unknown"

        # Log approval
        await log_agent_action(
            db, tenant_id=user.tenant_id, user_id=user.id,
            user_role=user.role.value, agent_name="approval_system",
            action="action_approved", input_text=f"conv={conversation_id}, tool={tool_name}",
            output_text=execution_message, status="success",
        )

        # Save approval response as a message in conversation
        count_result = await db.execute(
            select(func.count(ConversationMessage.id))
            .where(ConversationMessage.conversation_id == conversation_id)
        )
        turn = (count_result.scalar() or 0) + 1

        await _save_message(
            db, user.tenant_id, conversation_id, user.id,
            role="assistant", content=execution_message,
            agent_used="approval_system", turn_number=turn,
        )

    except Exception as e:
        execution_message = f"Action approved but execution encountered an error: {str(e)}"

    return {
        "conversation_id": conversation_id,
        "approved": True,
        "message": execution_message,
        "result": tool_result_data,
    }


@router.websocket("/ws/{token}")
async def chat_websocket(
    websocket: WebSocket,
    token: str,
):
    """
    WebSocket endpoint for streaming chat responses.
    Client connects with JWT token in URL path.

    Protocol:
    - Client sends: {"message": "...", "conversation_id": "..."}
    - Server sends: {"type": "start", "conversation_id": "..."}
    - Server sends: {"type": "chunk", "content": "..."} (for streaming)
    - Server sends: {"type": "complete", "message": "...", "agent_used": "...", "actions_taken": [...]}
    - Server sends: {"type": "error", "message": "..."}
    """
    await websocket.accept()

    # Authenticate from token
    from jose import JWTError, jwt as jose_jwt
    from config import get_settings
    from sqlalchemy import select
    from models.user import User
    from database import async_session_factory

    settings = get_settings()

    try:
        payload = jose_jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        if not user_id or not tenant_id:
            await websocket.send_json({"type": "error", "message": "Invalid token"})
            await websocket.close()
            return
    except JWTError:
        await websocket.send_json({"type": "error", "message": "Invalid or expired token"})
        await websocket.close()
        return

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message = data.get("message", "").strip()
            conversation_id = data.get("conversation_id") or str(uuid.uuid4())

            if not message:
                await websocket.send_json({"type": "error", "message": "Empty message"})
                continue

            # Send start signal
            await websocket.send_json({
                "type": "start",
                "conversation_id": conversation_id,
            })

            # Process in a DB session
            async with async_session_factory() as db:
                try:
                    # Fetch user
                    result = await db.execute(
                        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
                    )
                    user = result.scalar_one_or_none()
                    if not user:
                        await websocket.send_json({"type": "error", "message": "User not found"})
                        continue

                    # Check permission
                    if not has_permission(user.role, Permission.USE_CHAT):
                        await websocket.send_json({"type": "error", "message": "Chat not permitted"})
                        continue

                    # Set tenant context for this WebSocket request
                    TenantContext.set(
                        tenant_id=user.tenant_id,
                        user_id=user.id,
                        user_role=user.role.value,
                        request_id=str(uuid.uuid4()),
                    )

                    # Save user message
                    from sqlalchemy import func as sa_func
                    count_result = await db.execute(
                        select(sa_func.count(ConversationMessage.id))
                        .where(ConversationMessage.conversation_id == conversation_id)
                    )
                    turn = (count_result.scalar() or 0) + 1

                    await _save_message(
                        db, user.tenant_id, conversation_id, user.id,
                        role="user", content=message, turn_number=turn,
                    )

                    # Load conversation history
                    history = await _get_conversation_history(db, conversation_id, user.tenant_id)

                    # Build context
                    context = AgentContext(
                        tenant_id=user.tenant_id,
                        user_id=user.id,
                        user_role=user.role,
                        conversation_id=conversation_id,
                        db_session=db,
                    )

                    # Stream partial chunks as we process
                    # Send a "thinking" indicator
                    await websocket.send_json({"type": "chunk", "content": ""})

                    # Process through orchestrator
                    response = await process_message(
                        user_input=message,
                        context=context,
                        conversation_history=history,
                    )

                    # Save assistant message — find the source with agent routing info
                    agent_name = None
                    intent_name = None
                    for src in (response.sources or []):
                        if "agent" in src:
                            agent_name = src["agent"]
                            intent_name = src.get("intent")
                            break
                    await _save_message(
                        db, user.tenant_id, conversation_id, user.id,
                        role="assistant", content=response.message,
                        agent_used=agent_name, intent_detected=intent_name,
                        turn_number=turn + 1,
                    )

                    await db.commit()

                    # Stream the response in chunks for smoother UX
                    full_msg = response.message
                    chunk_size = 50  # characters per chunk
                    for i in range(0, len(full_msg), chunk_size):
                        chunk = full_msg[i:i + chunk_size]
                        await websocket.send_json({
                            "type": "chunk",
                            "content": chunk,
                        })

                    # Send complete signal with full data
                    await websocket.send_json({
                        "type": "complete",
                        "message": response.message,
                        "conversation_id": conversation_id,
                        "agent_used": agent_name,
                        "actions_taken": response.actions_taken,
                        "requires_approval": response.requires_approval,
                        "approval_action": response.approval_action,
                    })

                except Exception as e:
                    await db.rollback()
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Processing error: {str(e)[:200]}",
                    })
                finally:
                    TenantContext.clear()

    except WebSocketDisconnect:
        TenantContext.clear()
    except Exception:
        TenantContext.clear()
        try:
            await websocket.close()
        except Exception:
            pass
