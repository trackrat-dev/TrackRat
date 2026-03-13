import Foundation
import Combine

// MARK: - Chat Message Model

struct ChatMessage: Identifiable, Equatable {
    let id: Int
    let senderRole: String
    let message: String
    let readAt: String?
    let createdAt: String

    var isFromUser: Bool { senderRole == "user" }
    var isFromAdmin: Bool { senderRole == "admin" }
    var isUnread: Bool { readAt == nil }

    var formattedTime: String {
        // Parse ISO8601 and format as short time
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: createdAt) {
            let display = DateFormatter()
            display.dateStyle = .none
            display.timeStyle = .short
            return display.string(from: date)
        }
        // Fallback: try without fractional seconds
        formatter.formatOptions = [.withInternetDateTime]
        if let date = formatter.date(from: createdAt) {
            let display = DateFormatter()
            display.dateStyle = .none
            display.timeStyle = .short
            return display.string(from: date)
        }
        return ""
    }

    var formattedDate: String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        var date = formatter.date(from: createdAt)
        if date == nil {
            formatter.formatOptions = [.withInternetDateTime]
            date = formatter.date(from: createdAt)
        }
        guard let date else { return "" }
        let cal = Calendar.current
        if cal.isDateInToday(date) { return "Today" }
        if cal.isDateInYesterday(date) { return "Yesterday" }
        let display = DateFormatter()
        display.dateStyle = .medium
        display.timeStyle = .none
        return display.string(from: date)
    }
}

// MARK: - Conversation Model (Admin)

struct ChatConversation: Identifiable {
    let deviceId: String
    let lastMessage: String
    let lastMessageAt: String
    let lastSenderRole: String
    let unreadCount: Int

    var id: String { deviceId }

    var shortDeviceId: String {
        String(deviceId.prefix(8))
    }

    var formattedTime: String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        var date = formatter.date(from: lastMessageAt)
        if date == nil {
            formatter.formatOptions = [.withInternetDateTime]
            date = formatter.date(from: lastMessageAt)
        }
        guard let date else { return "" }
        let display = DateFormatter()
        let cal = Calendar.current
        if cal.isDateInToday(date) {
            display.dateStyle = .none
            display.timeStyle = .short
        } else {
            display.dateStyle = .short
            display.timeStyle = .none
        }
        return display.string(from: date)
    }
}

// MARK: - Chat Service

@MainActor
final class ChatService: ObservableObject {
    static let shared = ChatService()

    @Published private(set) var unreadCount: Int = 0
    @Published var isAdmin: Bool {
        didSet { UserDefaults.standard.set(isAdmin, forKey: "ChatService.isAdmin") }
    }

    private var deviceId: String {
        AlertSubscriptionService.shared.deviceId
    }

    private var unreadTimer: Timer?

    private init() {
        self.isAdmin = UserDefaults.standard.bool(forKey: "ChatService.isAdmin")
    }

    // MARK: - Unread Count Polling

    func startUnreadPolling() {
        stopUnreadPolling()
        // Fetch immediately, then every 60 seconds
        Task { await refreshUnreadCount() }
        unreadTimer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.refreshUnreadCount()
            }
        }
    }

    func stopUnreadPolling() {
        unreadTimer?.invalidate()
        unreadTimer = nil
    }

    func refreshUnreadCount() async {
        // Skip if no chat token yet (device not registered — avoids 401 spam)
        guard AlertSubscriptionService.shared.chatToken != nil else { return }
        do {
            unreadCount = try await APIService.shared.getChatUnreadCount(deviceId: deviceId)
        } catch {
            // Silently ignore — non-critical
        }
    }

    // MARK: - User Chat

    func fetchMessages(before: Int? = nil) async throws -> (messages: [ChatMessage], hasMore: Bool) {
        let response = try await APIService.shared.getChatMessages(deviceId: deviceId, before: before)
        return (response.messages.map { toChatMessage($0) }, response.has_more)
    }

    func sendMessage(_ text: String) async throws -> ChatMessage {
        let response = try await APIService.shared.sendChatMessage(deviceId: deviceId, message: text)
        return ChatMessage(
            id: response.id,
            senderRole: "user",
            message: text,
            readAt: nil,
            createdAt: response.created_at
        )
    }

    func markAsRead(upToId: Int) async throws {
        try await APIService.shared.markChatMessagesRead(deviceId: deviceId, upToId: upToId)
        await refreshUnreadCount()
    }

    // MARK: - Admin Registration

    func registerAsAdmin(code: String) async throws {
        try await APIService.shared.registerChatAdmin(deviceId: deviceId, registrationCode: code)
        isAdmin = true
    }

    // MARK: - Admin Chat

    func fetchConversations() async throws -> [ChatConversation] {
        let conversations = try await APIService.shared.getChatConversations(deviceId: deviceId)
        return conversations.map {
            ChatConversation(
                deviceId: $0.device_id,
                lastMessage: $0.last_message,
                lastMessageAt: $0.last_message_at,
                lastSenderRole: $0.last_sender_role,
                unreadCount: $0.unread_count
            )
        }
    }

    func fetchAdminMessages(targetDeviceId: String, before: Int? = nil) async throws -> (messages: [ChatMessage], hasMore: Bool) {
        let response = try await APIService.shared.getAdminChatMessages(
            deviceId: deviceId,
            targetDeviceId: targetDeviceId,
            before: before
        )
        return (response.messages.map { toChatMessage($0) }, response.has_more)
    }

    func sendAdminMessage(targetDeviceId: String, text: String) async throws -> ChatMessage {
        let response = try await APIService.shared.sendAdminChatMessage(
            deviceId: deviceId,
            targetDeviceId: targetDeviceId,
            message: text
        )
        return ChatMessage(
            id: response.id,
            senderRole: "admin",
            message: text,
            readAt: nil,
            createdAt: response.created_at
        )
    }

    func markAdminMessagesRead(targetDeviceId: String) async throws {
        try await APIService.shared.markAdminChatMessagesRead(
            deviceId: deviceId,
            targetDeviceId: targetDeviceId
        )
    }

    // MARK: - Private

    private func toChatMessage(_ r: APIService.ChatMessageResponse) -> ChatMessage {
        ChatMessage(
            id: r.id,
            senderRole: r.sender_role,
            message: r.message,
            readAt: r.read_at,
            createdAt: r.created_at
        )
    }
}
