"""
Tests for the developer chat API endpoints.

Uses the e2e_client fixture for real database integration.
Tests cover: user messaging, admin registration, admin messaging,
read receipts, pagination, and authorization.
"""

import os

import pytest
from starlette.testclient import TestClient

# Set admin registration code before settings are loaded
os.environ["TRACKRAT_CHAT_ADMIN_REGISTRATION_CODE"] = "test-secret-code"


def _register_device(client: TestClient, device_id: str, apns_token: str = "tok") -> None:
    """Helper to register a device (required before sending chat messages)."""
    resp = client.post(
        "/api/v2/devices/register",
        json={"device_id": device_id, "apns_token": apns_token},
    )
    assert resp.status_code == 200


def _register_admin(client: TestClient, device_id: str) -> None:
    """Helper to register a device as admin."""
    _register_device(client, device_id, f"tok-{device_id}")
    resp = client.post(
        "/api/v2/chat/admin/register",
        json={"device_id": device_id, "registration_code": "test-secret-code"},
    )
    assert resp.status_code == 200, f"Admin registration failed: {resp.json()}"


class TestUserSendMessage:
    """POST /api/v2/chat/messages"""

    def test_send_message(self, e2e_client: TestClient):
        """User can send a message after registering their device."""
        _register_device(e2e_client, "chat-user-1")
        resp = e2e_client.post(
            "/api/v2/chat/messages",
            json={"device_id": "chat-user-1", "message": "Hello developer!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] > 0
        assert data["created_at"] is not None

    def test_send_message_unregistered_device(self, e2e_client: TestClient):
        """Sending from an unregistered device returns 404."""
        resp = e2e_client.post(
            "/api/v2/chat/messages",
            json={"device_id": "nonexistent-device", "message": "Hello"},
        )
        assert resp.status_code == 404

    def test_send_empty_message(self, e2e_client: TestClient):
        """Empty messages are rejected."""
        _register_device(e2e_client, "chat-user-empty")
        resp = e2e_client.post(
            "/api/v2/chat/messages",
            json={"device_id": "chat-user-empty", "message": "   "},
        )
        assert resp.status_code == 400

    def test_message_too_long(self, e2e_client: TestClient):
        """Messages exceeding 255 characters are rejected by Pydantic validation."""
        _register_device(e2e_client, "chat-user-long")
        resp = e2e_client.post(
            "/api/v2/chat/messages",
            json={"device_id": "chat-user-long", "message": "x" * 256},
        )
        assert resp.status_code == 422  # Pydantic validation error


class TestUserGetMessages:
    """GET /api/v2/chat/messages"""

    def test_get_empty_messages(self, e2e_client: TestClient):
        """Getting messages for a device with no messages returns empty list."""
        resp = e2e_client.get("/api/v2/chat/messages?device_id=no-messages-device")
        assert resp.status_code == 200
        data = resp.json()
        assert data["messages"] == []
        assert data["has_more"] is False

    def test_get_messages_after_send(self, e2e_client: TestClient):
        """Messages appear in the list after being sent."""
        _register_device(e2e_client, "chat-user-getmsg")
        e2e_client.post(
            "/api/v2/chat/messages",
            json={"device_id": "chat-user-getmsg", "message": "First message"},
        )
        e2e_client.post(
            "/api/v2/chat/messages",
            json={"device_id": "chat-user-getmsg", "message": "Second message"},
        )

        resp = e2e_client.get("/api/v2/chat/messages?device_id=chat-user-getmsg")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) == 2
        # Messages returned oldest-first
        assert data["messages"][0]["message"] == "First message"
        assert data["messages"][1]["message"] == "Second message"
        assert all(m["sender_role"] == "user" for m in data["messages"])

    def test_pagination_with_before(self, e2e_client: TestClient):
        """Pagination using 'before' cursor works correctly."""
        _register_device(e2e_client, "chat-user-page")
        msg_ids = []
        for i in range(5):
            resp = e2e_client.post(
                "/api/v2/chat/messages",
                json={"device_id": "chat-user-page", "message": f"Msg {i}"},
            )
            msg_ids.append(resp.json()["id"])

        # Get messages before the last one, limit 2
        resp = e2e_client.get(
            f"/api/v2/chat/messages?device_id=chat-user-page&before={msg_ids[-1]}&limit=2"
        )
        data = resp.json()
        assert len(data["messages"]) == 2
        assert data["has_more"] is True
        assert data["messages"][0]["message"] == "Msg 2"
        assert data["messages"][1]["message"] == "Msg 3"


class TestUnreadCount:
    """GET /api/v2/chat/unread-count"""

    def test_unread_count_zero(self, e2e_client: TestClient):
        """Unread count is 0 when no admin messages exist."""
        resp = e2e_client.get("/api/v2/chat/unread-count?device_id=unread-user")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0

    def test_unread_count_after_admin_reply(self, e2e_client: TestClient):
        """Unread count reflects admin messages not yet read."""
        _register_device(e2e_client, "chat-user-unread")
        _register_admin(e2e_client, "admin-unread")

        # User sends a message
        e2e_client.post(
            "/api/v2/chat/messages",
            json={"device_id": "chat-user-unread", "message": "Help!"},
        )

        # Admin replies
        e2e_client.post(
            "/api/v2/chat/admin/conversations/chat-user-unread/messages",
            json={"device_id": "admin-unread", "message": "Sure!"},
        )
        e2e_client.post(
            "/api/v2/chat/admin/conversations/chat-user-unread/messages",
            json={"device_id": "admin-unread", "message": "What's up?"},
        )

        resp = e2e_client.get("/api/v2/chat/unread-count?device_id=chat-user-unread")
        assert resp.json()["unread_count"] == 2


class TestMarkRead:
    """POST /api/v2/chat/messages/read"""

    def test_mark_messages_read(self, e2e_client: TestClient):
        """Marking messages as read decrements unread count."""
        _register_device(e2e_client, "chat-user-read")
        _register_admin(e2e_client, "admin-read")

        # Admin sends two messages
        resp1 = e2e_client.post(
            "/api/v2/chat/admin/conversations/chat-user-read/messages",
            json={"device_id": "admin-read", "message": "Hello"},
        )
        resp2 = e2e_client.post(
            "/api/v2/chat/admin/conversations/chat-user-read/messages",
            json={"device_id": "admin-read", "message": "How are you?"},
        )

        # Mark first as read
        mark_resp = e2e_client.post(
            "/api/v2/chat/messages/read",
            json={"device_id": "chat-user-read", "up_to_id": resp1.json()["id"]},
        )
        assert mark_resp.json()["marked_count"] == 1

        # Unread count should be 1
        unread = e2e_client.get("/api/v2/chat/unread-count?device_id=chat-user-read")
        assert unread.json()["unread_count"] == 1

        # Mark all as read
        mark_resp2 = e2e_client.post(
            "/api/v2/chat/messages/read",
            json={"device_id": "chat-user-read", "up_to_id": resp2.json()["id"]},
        )
        assert mark_resp2.json()["marked_count"] == 1

        unread2 = e2e_client.get("/api/v2/chat/unread-count?device_id=chat-user-read")
        assert unread2.json()["unread_count"] == 0


class TestAdminRegistration:
    """POST /api/v2/chat/admin/register"""

    def test_register_admin_success(self, e2e_client: TestClient):
        """Valid registration code registers the device as admin."""
        _register_device(e2e_client, "admin-reg-ok")
        resp = e2e_client.post(
            "/api/v2/chat/admin/register",
            json={"device_id": "admin-reg-ok", "registration_code": "test-secret-code"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "registered"

    def test_register_admin_wrong_code(self, e2e_client: TestClient):
        """Wrong registration code returns 403."""
        resp = e2e_client.post(
            "/api/v2/chat/admin/register",
            json={"device_id": "admin-reg-bad", "registration_code": "wrong-code"},
        )
        assert resp.status_code == 403

    def test_register_admin_idempotent(self, e2e_client: TestClient):
        """Registering the same device twice succeeds without error."""
        _register_device(e2e_client, "admin-reg-idem")
        for _ in range(2):
            resp = e2e_client.post(
                "/api/v2/chat/admin/register",
                json={"device_id": "admin-reg-idem", "registration_code": "test-secret-code"},
            )
            assert resp.status_code == 200


class TestAdminConversations:
    """GET /api/v2/chat/admin/conversations"""

    def test_non_admin_rejected(self, e2e_client: TestClient):
        """Non-admin device gets 403."""
        resp = e2e_client.get("/api/v2/chat/admin/conversations?device_id=not-admin")
        assert resp.status_code == 403

    def test_list_conversations(self, e2e_client: TestClient):
        """Admin can see all conversations with last message and unread count."""
        _register_admin(e2e_client, "admin-conv")

        # Two users send messages
        _register_device(e2e_client, "conv-user-a")
        _register_device(e2e_client, "conv-user-b")
        e2e_client.post(
            "/api/v2/chat/messages",
            json={"device_id": "conv-user-a", "message": "Hello from A"},
        )
        e2e_client.post(
            "/api/v2/chat/messages",
            json={"device_id": "conv-user-b", "message": "Hello from B"},
        )

        resp = e2e_client.get("/api/v2/chat/admin/conversations?device_id=admin-conv")
        assert resp.status_code == 200
        data = resp.json()
        conversations = data["conversations"]

        # Should see both conversations
        device_ids = {c["device_id"] for c in conversations}
        assert "conv-user-a" in device_ids
        assert "conv-user-b" in device_ids

        # Each should have unread_count=1
        for conv in conversations:
            if conv["device_id"] in ("conv-user-a", "conv-user-b"):
                assert conv["unread_count"] == 1


class TestAdminSendMessage:
    """POST /api/v2/chat/admin/conversations/{target}/messages"""

    def test_admin_reply(self, e2e_client: TestClient):
        """Admin can reply to a user's conversation."""
        _register_admin(e2e_client, "admin-reply")
        _register_device(e2e_client, "chat-user-reply")

        # User sends message
        e2e_client.post(
            "/api/v2/chat/messages",
            json={"device_id": "chat-user-reply", "message": "Question?"},
        )

        # Admin replies
        resp = e2e_client.post(
            "/api/v2/chat/admin/conversations/chat-user-reply/messages",
            json={"device_id": "admin-reply", "message": "Answer!"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] > 0

        # User should see both messages
        msgs = e2e_client.get("/api/v2/chat/messages?device_id=chat-user-reply")
        messages = msgs.json()["messages"]
        assert len(messages) == 2
        assert messages[0]["sender_role"] == "user"
        assert messages[1]["sender_role"] == "admin"

    def test_admin_reply_non_admin_rejected(self, e2e_client: TestClient):
        """Non-admin cannot use admin reply endpoint."""
        _register_device(e2e_client, "fake-admin")
        _register_device(e2e_client, "target-user")
        resp = e2e_client.post(
            "/api/v2/chat/admin/conversations/target-user/messages",
            json={"device_id": "fake-admin", "message": "Sneaky!"},
        )
        assert resp.status_code == 403

    def test_admin_reply_nonexistent_user(self, e2e_client: TestClient):
        """Admin replying to a nonexistent device returns 404."""
        _register_admin(e2e_client, "admin-404")
        resp = e2e_client.post(
            "/api/v2/chat/admin/conversations/nonexistent-user/messages",
            json={"device_id": "admin-404", "message": "Hello?"},
        )
        assert resp.status_code == 404


class TestAdminMarkRead:
    """POST /api/v2/chat/admin/conversations/{target}/read"""

    def test_admin_marks_user_messages_read(self, e2e_client: TestClient):
        """Admin marking messages as read updates read_at for user messages."""
        _register_admin(e2e_client, "admin-markread")
        _register_device(e2e_client, "user-markread")

        # User sends messages
        e2e_client.post(
            "/api/v2/chat/messages",
            json={"device_id": "user-markread", "message": "Msg 1"},
        )
        e2e_client.post(
            "/api/v2/chat/messages",
            json={"device_id": "user-markread", "message": "Msg 2"},
        )

        # Admin marks as read
        resp = e2e_client.post(
            "/api/v2/chat/admin/conversations/user-markread/read?device_id=admin-markread"
        )
        assert resp.status_code == 200
        assert resp.json()["marked_count"] == 2

        # Conversation should show 0 unread
        convs = e2e_client.get("/api/v2/chat/admin/conversations?device_id=admin-markread")
        for conv in convs.json()["conversations"]:
            if conv["device_id"] == "user-markread":
                assert conv["unread_count"] == 0

    def test_admin_mark_read_non_admin_rejected(self, e2e_client: TestClient):
        """Non-admin cannot mark admin messages as read."""
        resp = e2e_client.post(
            "/api/v2/chat/admin/conversations/some-user/read?device_id=not-admin"
        )
        assert resp.status_code == 403


class TestAdminGetConversationMessages:
    """GET /api/v2/chat/admin/conversations/{target}/messages"""

    def test_admin_views_conversation(self, e2e_client: TestClient):
        """Admin can view a specific user's conversation history."""
        _register_admin(e2e_client, "admin-view")
        _register_device(e2e_client, "chat-user-view")

        # User sends, admin replies
        e2e_client.post(
            "/api/v2/chat/messages",
            json={"device_id": "chat-user-view", "message": "User says hi"},
        )
        e2e_client.post(
            "/api/v2/chat/admin/conversations/chat-user-view/messages",
            json={"device_id": "admin-view", "message": "Admin says hi back"},
        )

        resp = e2e_client.get(
            "/api/v2/chat/admin/conversations/chat-user-view/messages?device_id=admin-view"
        )
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        assert len(messages) == 2
        assert messages[0]["sender_role"] == "user"
        assert messages[1]["sender_role"] == "admin"

    def test_non_admin_rejected(self, e2e_client: TestClient):
        """Non-admin cannot view conversation messages."""
        resp = e2e_client.get(
            "/api/v2/chat/admin/conversations/some-user/messages?device_id=not-admin"
        )
        assert resp.status_code == 403
