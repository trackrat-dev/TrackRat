import SwiftUI

struct AdminChatListView: View {
    @ObservedObject private var chatService = ChatService.shared
    @State private var conversations: [ChatConversation] = []
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        Group {
            if isLoading && conversations.isEmpty {
                ProgressView()
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if conversations.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "tray")
                        .font(.system(size: 40))
                        .foregroundStyle(.secondary)
                    Text("No conversations yet")
                        .font(.headline)
                        .foregroundStyle(.white)
                    Text("Messages from users will appear here.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List(conversations) { conversation in
                    NavigationLink(value: conversation.deviceId) {
                        ConversationRow(conversation: conversation)
                    }
                    .listRowBackground(Color.clear)
                }
                .listStyle(.plain)
            }
        }
        .background(TrackRatTheme.Colors.primaryBackground)
        .navigationTitle("Developer Inbox")
        .navigationBarTitleDisplayMode(.inline)
        .navigationDestination(for: String.self) { deviceId in
            ChatView(targetDeviceId: deviceId)
        }
        .task {
            await loadConversations()
        }
        .refreshable {
            await loadConversations()
        }
    }

    private func loadConversations() async {
        isLoading = true
        defer { isLoading = false }
        do {
            conversations = try await chatService.fetchConversations()
            errorMessage = nil
        } catch {
            errorMessage = "Could not load conversations"
        }
    }
}

// MARK: - Conversation Row

private struct ConversationRow: View {
    let conversation: ChatConversation

    var body: some View {
        HStack(spacing: 12) {
            // Avatar
            Circle()
                .fill(Color.orange.opacity(0.3))
                .frame(width: 40, height: 40)
                .overlay(
                    Text(String(conversation.shortDeviceId.prefix(2)).uppercased())
                        .font(.caption.weight(.bold))
                        .foregroundStyle(.orange)
                )

            VStack(alignment: .leading, spacing: 3) {
                HStack {
                    Text(conversation.shortDeviceId)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white)
                    Spacer()
                    Text(conversation.formattedTime)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }

                HStack {
                    Text(conversation.lastMessage)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                    Spacer()
                    if conversation.unreadCount > 0 {
                        Text("\(conversation.unreadCount)")
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Capsule().fill(.orange))
                    }
                }
            }
        }
        .padding(.vertical, 4)
    }
}
