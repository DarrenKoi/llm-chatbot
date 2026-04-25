export interface WebChatUser {
  user_id: string
  user_name: string
}

export interface WebChatMessage {
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
}

export interface WebChatConversationSummary {
  conversation_id: string
  last_message_at: string
  last_message_role: string
  last_message_preview: string
  source: string | null
}

export interface WebChatReply {
  conversation_id: string
  message_id: string
  reply: string
  workflow_id: string
}

export interface WebChatErrorBody {
  error: string
  detail?: string
}
