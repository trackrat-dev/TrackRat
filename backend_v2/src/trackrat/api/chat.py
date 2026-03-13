"""
Developer chat API endpoints.

Enables two-party messaging between users and the developer (admin).
Users send messages via their device_id; admin is identified by device_id
registered in the admin_devices table.

Auth model:
  User endpoints require a bearer token (returned by POST /devices/register)
  sent as Authorization: Bearer <token>. The token proves device ownership.

  Admin endpoints verify admin status via the admin_devices table, using
  X-Device-Id header for identification.
"""

import hashlib
import time
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.db.engine import get_db
from trackrat.models.database import AdminDevice, ChatMessage, DeviceToken
from trackrat.settings import get_settings

logger = get_logger("trackrat.api.chat")

router = APIRouter(prefix="/api/v2/chat", tags=["chat"])

MAX_MESSAGE_LENGTH = 255

# --- Rate Limiter ---

RATE_LIMIT_MAX_MESSAGES = 10
RATE_LIMIT_WINDOW_SECONDS = 60


class _ChatRateLimiter:
    """In-memory per-device rate limiter for chat message sending."""

    def __init__(self) -> None:
        self._timestamps: dict[str, list[float]] = {}
        self._call_count = 0

    def check(self, device_id: str) -> bool:
        """Return True if the request is allowed, False if rate-limited."""
        now = time.monotonic()
        window_start = now - RATE_LIMIT_WINDOW_SECONDS

        timestamps = self._timestamps.get(device_id, [])
        timestamps = [t for t in timestamps if t > window_start]

        if len(timestamps) >= RATE_LIMIT_MAX_MESSAGES:
            self._timestamps[device_id] = timestamps
            return False

        timestamps.append(now)
        self._timestamps[device_id] = timestamps

        # Periodic cleanup of stale entries
        self._call_count += 1
        if self._call_count % 100 == 0:
            self._cleanup(window_start)

        return True

    def _cleanup(self, window_start: float) -> None:
        stale = [
            k for k, v in self._timestamps.items() if not v or v[-1] < window_start
        ]
        for k in stale:
            del self._timestamps[k]


_rate_limiter = _ChatRateLimiter()


# --- Request/Response Models ---


class SendMessageRequest(BaseModel):
    device_id: str
    message: str = Field(max_length=MAX_MESSAGE_LENGTH)


class SendMessageResponse(BaseModel):
    id: int
    created_at: str


class ChatMessageOut(BaseModel):
    id: int
    sender_role: str
    message: str
    read_at: str | None
    created_at: str


class MessagesResponse(BaseModel):
    messages: list[ChatMessageOut]
    has_more: bool


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkReadRequest(BaseModel):
    device_id: str
    up_to_id: int


class MarkReadResponse(BaseModel):
    marked_count: int


class AdminRegisterRequest(BaseModel):
    device_id: str
    registration_code: str


class AdminRegisterResponse(BaseModel):
    status: str = "registered"


class ConversationOut(BaseModel):
    device_id: str
    last_message: str
    last_message_at: str
    last_sender_role: str
    unread_count: int


class ConversationsResponse(BaseModel):
    conversations: list[ConversationOut]


# --- Helpers ---


def _format_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


async def _is_admin(db: AsyncSession, device_id: str) -> bool:
    """Check if a device_id is registered as admin."""
    result = await db.execute(
        select(AdminDevice.id).where(AdminDevice.device_id == device_id).limit(1)
    )
    return result.scalar() is not None


async def _device_exists(db: AsyncSession, device_id: str) -> bool:
    """Check if a device_id exists in device_tokens."""
    result = await db.execute(
        select(DeviceToken.id).where(DeviceToken.device_id == device_id).limit(1)
    )
    return result.scalar() is not None


async def _verify_device(
    db: AsyncSession, device_id: str, authorization: str | None
) -> None:
    """Verify device ownership via bearer token. Raises HTTPException on failure."""
    result = await db.execute(
        select(DeviceToken.chat_token_hash)
        .where(DeviceToken.device_id == device_id)
        .limit(1)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Device not registered")

    stored_hash = row[0]
    if stored_hash is None:
        # Device registered before auth was added — require re-registration
        raise HTTPException(
            status_code=401, detail="Chat token required. Re-register device."
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required")

    token = authorization[7:]  # Strip "Bearer "
    if hashlib.sha256(token.encode()).hexdigest() != stored_hash:
        raise HTTPException(status_code=401, detail="Invalid chat token")


async def _send_chat_push(
    request: Request,
    db: AsyncSession,
    target_device_id: str,
    title: str,
    body: str,
    custom_data: dict[str, Any] | None = None,
) -> None:
    """Send a push notification for a chat message. Best-effort, never raises."""
    try:
        apns_service = getattr(request.app.state, "apns_service", None)
        if apns_service is None or not apns_service.is_configured:
            return

        result = await db.execute(
            select(DeviceToken.apns_token).where(
                DeviceToken.device_id == target_device_id
            )
        )
        apns_token = result.scalar()

        if not apns_token:
            return

        await apns_service.send_alert_notification(
            device_token=apns_token,
            title=title,
            body=body,
            custom_data=custom_data,
        )
    except Exception:
        logger.warning(
            "chat_push_failed",
            target_device_id=target_device_id[:8] + "...",
            exc_info=True,
        )


def _to_message_out(m: ChatMessage) -> ChatMessageOut:
    return ChatMessageOut(
        id=m.id,
        sender_role=m.sender_role,
        message=m.message,
        read_at=_format_dt(m.read_at),
        created_at=_format_dt(m.created_at),
    )


async def _get_messages_page(
    db: AsyncSession,
    device_id: str,
    before: int | None,
    limit: int,
) -> MessagesResponse:
    """Shared pagination logic for message endpoints."""
    if limit < 1 or limit > 100:
        limit = 50

    query = select(ChatMessage).where(ChatMessage.device_id == device_id)
    if before is not None:
        query = query.where(ChatMessage.id < before)
    query = query.order_by(ChatMessage.id.desc()).limit(limit + 1)

    result = await db.execute(query)
    rows = result.scalars().all()

    has_more = len(rows) > limit
    messages = rows[:limit]

    return MessagesResponse(
        messages=[_to_message_out(m) for m in reversed(messages)],
        has_more=has_more,
    )


# --- User Endpoints ---


@router.get("/messages", response_model=MessagesResponse)
async def get_messages(
    before: int | None = None,
    limit: int = 50,
    x_device_id: str = Header(),
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> MessagesResponse:
    """Get paginated message history for a device."""
    await _verify_device(db, x_device_id, authorization)
    return await _get_messages_page(db, x_device_id, before, limit)


@router.post("/messages", response_model=SendMessageResponse)
async def send_message(
    req: SendMessageRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> SendMessageResponse:
    """Send a message from a user."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    await _verify_device(db, req.device_id, authorization)

    if not _rate_limiter.check(req.device_id):
        raise HTTPException(
            status_code=429, detail="Too many messages. Try again later."
        )

    now = datetime.now(UTC)
    msg = ChatMessage(
        device_id=req.device_id,
        sender_role="user",
        message=req.message.strip(),
        created_at=now,
    )
    db.add(msg)
    await db.flush()

    logger.info(
        "chat_message_sent",
        device_id=req.device_id[:8] + "...",
        sender_role="user",
        message_id=msg.id,
    )

    # Notify all admin devices
    result = await db.execute(select(AdminDevice.device_id))
    admin_device_ids = [row[0] for row in result.all()]

    for admin_device_id in admin_device_ids:
        await _send_chat_push(
            request,
            db,
            admin_device_id,
            title="New message from a TrackRat user",
            body=req.message.strip()[:100],
            custom_data={"type": "chat_message", "from_device_id": req.device_id},
        )

    return SendMessageResponse(id=msg.id, created_at=_format_dt(msg.created_at))


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    x_device_id: str = Header(),
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    """Get count of unread messages from admin for this device."""
    await _verify_device(db, x_device_id, authorization)
    result = await db.execute(
        select(func.count(ChatMessage.id)).where(
            ChatMessage.device_id == x_device_id,
            ChatMessage.sender_role == "admin",
            ChatMessage.read_at.is_(None),
        )
    )
    count = result.scalar() or 0
    return UnreadCountResponse(unread_count=count)


@router.post("/messages/read", response_model=MarkReadResponse)
async def mark_messages_read(
    req: MarkReadRequest,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> MarkReadResponse:
    """Mark messages as read up to a given message ID."""
    await _verify_device(db, req.device_id, authorization)
    now = datetime.now(UTC)
    result = cast(
        CursorResult[tuple[()]],
        await db.execute(
            update(ChatMessage)
            .where(
                ChatMessage.device_id == req.device_id,
                ChatMessage.sender_role == "admin",
                ChatMessage.read_at.is_(None),
                ChatMessage.id <= req.up_to_id,
            )
            .values(read_at=now)
        ),
    )
    return MarkReadResponse(marked_count=result.rowcount)


# --- Admin Endpoints ---


@router.post("/admin/register", response_model=AdminRegisterResponse)
async def register_admin(
    req: AdminRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> AdminRegisterResponse:
    """Register a device as admin using a secret registration code."""
    settings = get_settings()

    if not settings.chat_admin_registration_code:
        raise HTTPException(status_code=503, detail="Admin registration not configured")

    if req.registration_code != settings.chat_admin_registration_code:
        logger.warning(
            "admin_registration_failed",
            device_id=req.device_id[:8] + "...",
        )
        raise HTTPException(status_code=403, detail="Invalid registration code")

    # Upsert — ignore if already registered
    existing = await db.execute(
        select(AdminDevice.id).where(AdminDevice.device_id == req.device_id).limit(1)
    )
    if existing.scalar() is None:
        db.add(AdminDevice(device_id=req.device_id))

    logger.info("admin_device_registered", device_id=req.device_id[:8] + "...")
    return AdminRegisterResponse()


@router.get("/admin/conversations", response_model=ConversationsResponse)
async def get_conversations(
    x_device_id: str = Header(),
    db: AsyncSession = Depends(get_db),
) -> ConversationsResponse:
    """List all conversations (admin only)."""
    if not await _is_admin(db, x_device_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    # Subquery for latest message per device
    latest_msg_subq = (
        select(
            ChatMessage.device_id,
            func.max(ChatMessage.id).label("max_id"),
        )
        .group_by(ChatMessage.device_id)
        .subquery()
    )

    # Join to get full message details
    result = await db.execute(
        select(ChatMessage)
        .join(
            latest_msg_subq,
            (ChatMessage.device_id == latest_msg_subq.c.device_id)
            & (ChatMessage.id == latest_msg_subq.c.max_id),
        )
        .order_by(ChatMessage.id.desc())
    )
    latest_messages = result.scalars().all()

    # Get unread counts (messages from users that admin hasn't read)
    unread_result = await db.execute(
        select(
            ChatMessage.device_id,
            func.count(ChatMessage.id).label("unread"),
        )
        .where(
            ChatMessage.sender_role == "user",
            ChatMessage.read_at.is_(None),
        )
        .group_by(ChatMessage.device_id)
    )
    unread_map = {row[0]: row[1] for row in unread_result.all()}

    return ConversationsResponse(
        conversations=[
            ConversationOut(
                device_id=m.device_id,
                last_message=m.message,
                last_message_at=_format_dt(m.created_at),
                last_sender_role=m.sender_role,
                unread_count=unread_map.get(m.device_id, 0),
            )
            for m in latest_messages
        ]
    )


@router.get(
    "/admin/conversations/{target_device_id}/messages",
    response_model=MessagesResponse,
)
async def get_conversation_messages(
    target_device_id: str,
    before: int | None = None,
    limit: int = 50,
    x_device_id: str = Header(),
    db: AsyncSession = Depends(get_db),
) -> MessagesResponse:
    """Get messages for a specific conversation (admin only)."""
    if not await _is_admin(db, x_device_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    return await _get_messages_page(db, target_device_id, before, limit)


@router.post(
    "/admin/conversations/{target_device_id}/messages",
    response_model=SendMessageResponse,
)
async def send_admin_message(
    target_device_id: str,
    req: SendMessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SendMessageResponse:
    """Send a message from admin to a user."""
    if not await _is_admin(db, req.device_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if not await _device_exists(db, target_device_id):
        raise HTTPException(status_code=404, detail="Target device not found")

    now = datetime.now(UTC)
    msg = ChatMessage(
        device_id=target_device_id,
        sender_role="admin",
        message=req.message.strip(),
        created_at=now,
    )
    db.add(msg)
    await db.flush()

    logger.info(
        "chat_message_sent",
        target_device_id=target_device_id[:8] + "...",
        sender_role="admin",
        message_id=msg.id,
    )

    # Notify the user
    await _send_chat_push(
        request,
        db,
        target_device_id,
        title="The developer replied to your message",
        body=req.message.strip()[:100],
        custom_data={"type": "chat_message"},
    )

    return SendMessageResponse(id=msg.id, created_at=_format_dt(msg.created_at))


@router.post(
    "/admin/conversations/{target_device_id}/read", response_model=MarkReadResponse
)
async def mark_admin_messages_read(
    target_device_id: str,
    x_device_id: str = Header(),
    db: AsyncSession = Depends(get_db),
) -> MarkReadResponse:
    """Mark user messages as read in a conversation (admin only)."""
    if not await _is_admin(db, x_device_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    now = datetime.now(UTC)
    result = cast(
        CursorResult[tuple[()]],
        await db.execute(
            update(ChatMessage)
            .where(
                ChatMessage.device_id == target_device_id,
                ChatMessage.sender_role == "user",
                ChatMessage.read_at.is_(None),
            )
            .values(read_at=now)
        ),
    )
    return MarkReadResponse(marked_count=result.rowcount)
