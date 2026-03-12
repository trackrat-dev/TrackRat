import SwiftUI

struct ChatView: View {
    /// When nil, this is the user's own chat. When set, this is admin viewing a specific conversation.
    let targetDeviceId: String?

    @ObservedObject private var chatService = ChatService.shared
    @State private var messages: [ChatMessage] = []
    @State private var messageText = ""
    @State private var hasMore = false
    @State private var isLoading = false
    @State private var isSending = false
    @State private var errorMessage: String?
    @State private var pollTimer: Timer?
    @State private var showingPaywall = false

    /// Whether the current user is viewing as admin
    private var isAdminMode: Bool { targetDeviceId != nil }

    /// Read-only when subscription lapsed (user mode only)
    @ObservedObject private var subscriptionService = SubscriptionService.shared

    private var isReadOnly: Bool {
        !isAdminMode && !subscriptionService.hasAccess(to: .developerChat)
    }

    private let maxMessageLength = 255

    private var headerTitle: String {
        isAdminMode ? "User \(targetDeviceId?.prefix(8) ?? "")" : "Chat with Developer"
    }

    var body: some View {
        VStack(spacing: 0) {
            TrackRatNavigationHeader(
                title: headerTitle,
                showBackButton: false
            )

            // Messages
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 4) {
                        if hasMore {
                            Button("Load earlier messages") {
                                Task { await loadMore() }
                            }
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .padding(.top, 8)
                        }

                        ForEach(groupedByDate(), id: \.date) { group in
                            Text(group.date)
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                                .padding(.top, 12)
                                .padding(.bottom, 4)

                            ForEach(group.messages) { message in
                                MessageBubble(message: message, isAdminMode: isAdminMode)
                                    .id(message.id)
                            }
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.bottom, 8)
                }
                .onChange(of: messages.count) {
                    if let last = messages.last {
                        withAnimation(.easeOut(duration: 0.2)) {
                            proxy.scrollTo(last.id, anchor: .bottom)
                        }
                    }
                }
            }

            // Read-only banner
            if isReadOnly {
                VStack(spacing: 8) {
                    Text("Subscribe to continue the conversation")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                    Button("Restore Chat Access") {
                        showingPaywall = true
                    }
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.orange)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .frame(maxWidth: .infinity)
                .background(.ultraThinMaterial)
            }

            // Input bar
            if !isReadOnly {
                inputBar
            }
        }
        .background(TrackRatTheme.Colors.primaryBackground)
        .navigationBarHidden(true)
        .task {
            await loadMessages()
            startPolling()
        }
        .onDisappear {
            stopPolling()
            markVisibleAsRead()
        }
        .sheet(isPresented: $showingPaywall) {
            PaywallView(context: .developerChat)
        }
    }

    // MARK: - Input Bar

    private var inputBar: some View {
        HStack(spacing: 8) {
            TextField("Message...", text: $messageText, axis: .vertical)
                .textFieldStyle(.plain)
                .lineLimit(1...4)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(
                    RoundedRectangle(cornerRadius: 20)
                        .fill(.ultraThinMaterial)
                )
                .onChange(of: messageText) {
                    if messageText.count > maxMessageLength {
                        messageText = String(messageText.prefix(maxMessageLength))
                    }
                }

            Button {
                Task { await sendMessage() }
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.title2)
                    .foregroundStyle(messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? .gray : .orange)
            }
            .disabled(messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isSending)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.ultraThinMaterial)
    }

    // MARK: - Data Loading

    private func loadMessages() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let result: (messages: [ChatMessage], hasMore: Bool)
            if let target = targetDeviceId {
                result = try await chatService.fetchAdminMessages(targetDeviceId: target)
            } else {
                result = try await chatService.fetchMessages()
            }
            messages = result.messages
            hasMore = result.hasMore
            errorMessage = nil
        } catch {
            errorMessage = "Could not load messages"
        }
    }

    private func loadMore() async {
        guard let firstId = messages.first?.id else { return }
        do {
            let result: (messages: [ChatMessage], hasMore: Bool)
            if let target = targetDeviceId {
                result = try await chatService.fetchAdminMessages(targetDeviceId: target, before: firstId)
            } else {
                result = try await chatService.fetchMessages(before: firstId)
            }
            messages.insert(contentsOf: result.messages, at: 0)
            hasMore = result.hasMore
        } catch {
            // Silently ignore load-more failures
        }
    }

    private func sendMessage() async {
        let text = messageText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        messageText = ""
        isSending = true
        defer { isSending = false }
        do {
            let msg: ChatMessage
            if let target = targetDeviceId {
                msg = try await chatService.sendAdminMessage(targetDeviceId: target, text: text)
            } else {
                msg = try await chatService.sendMessage(text)
            }
            messages.append(msg)
        } catch {
            // Restore text on failure
            messageText = text
            errorMessage = "Failed to send message"
        }
    }

    // MARK: - Polling

    private func startPolling() {
        stopPolling()
        pollTimer = Timer.scheduledTimer(withTimeInterval: 10, repeats: true) { _ in
            Task { @MainActor in
                await refreshMessages()
            }
        }
    }

    private func stopPolling() {
        pollTimer?.invalidate()
        pollTimer = nil
    }

    private func refreshMessages() async {
        do {
            let result: (messages: [ChatMessage], hasMore: Bool)
            if let target = targetDeviceId {
                result = try await chatService.fetchAdminMessages(targetDeviceId: target)
            } else {
                result = try await chatService.fetchMessages()
            }
            // Only update if there are new messages
            if result.messages.count != messages.count || result.messages.last?.id != messages.last?.id {
                messages = result.messages
                hasMore = result.hasMore
            }
        } catch {
            // Silently ignore refresh failures
        }
    }

    // MARK: - Read Receipts

    private func markVisibleAsRead() {
        guard let lastMsg = messages.last else { return }
        Task {
            if let target = targetDeviceId {
                // Admin marks user messages as read
                try? await chatService.markAdminMessagesRead(targetDeviceId: target)
            } else {
                // User marks admin messages as read
                if messages.contains(where: { $0.isFromAdmin && $0.isUnread }) {
                    try? await chatService.markAsRead(upToId: lastMsg.id)
                }
            }
        }
    }

    // MARK: - Grouping

    private struct DateGroup {
        let date: String
        let messages: [ChatMessage]
    }

    private func groupedByDate() -> [DateGroup] {
        let grouped = Dictionary(grouping: messages) { $0.formattedDate }
        return grouped.map { DateGroup(date: $0.key, messages: $0.value) }
            .sorted { ($0.messages.first?.id ?? 0) < ($1.messages.first?.id ?? 0) }
    }
}

// MARK: - Message Bubble

private struct MessageBubble: View {
    let message: ChatMessage
    let isAdminMode: Bool

    /// In user mode: user messages are "mine" (right-aligned)
    /// In admin mode: admin messages are "mine" (right-aligned)
    private var isMine: Bool {
        isAdminMode ? message.isFromAdmin : message.isFromUser
    }

    var body: some View {
        HStack {
            if isMine { Spacer(minLength: 60) }

            VStack(alignment: isMine ? .trailing : .leading, spacing: 2) {
                Text(message.message)
                    .font(.body)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(
                        RoundedRectangle(cornerRadius: 16)
                            .fill(isMine ? Color.orange.opacity(0.8) : Color.white.opacity(0.15))
                    )

                Text(message.formattedTime)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 4)
            }

            if !isMine { Spacer(minLength: 60) }
        }
        .padding(.vertical, 1)
    }
}
