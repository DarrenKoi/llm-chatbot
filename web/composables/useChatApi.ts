import type {
  WebChatConversationSummary,
  WebChatMessage,
  WebChatReply,
  WebChatUser,
} from '~/types/chat'

interface ConversationsResponse {
  conversations: WebChatConversationSummary[]
}

interface MessagesResponse {
  conversation_id: string
  messages: WebChatMessage[]
}

class WebChatApiError extends Error {
  status: number
  detail?: string

  constructor(status: number, message: string, detail?: string) {
    super(message)
    this.status = status
    this.detail = detail
    this.name = 'WebChatApiError'
  }
}

export function useChatApi() {
  const config = useRuntimeConfig()
  const apiBase = config.public.webChatApiBase

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${apiBase}${path}`, {
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(init.headers ?? {}),
      },
      ...init,
    })

    if (!response.ok) {
      let detail: string | undefined
      try {
        const body = await response.json()
        detail = body?.detail ?? body?.error
      } catch {
        // ignore non-JSON error bodies
      }
      throw new WebChatApiError(response.status, `web-chat API ${response.status}`, detail)
    }

    return (await response.json()) as T
  }

  async function fetchCurrentUser(): Promise<WebChatUser> {
    return request<WebChatUser>('/me')
  }

  async function listConversations(): Promise<WebChatConversationSummary[]> {
    const body = await request<ConversationsResponse>('/conversations')
    return body.conversations
  }

  async function fetchMessages(conversationId: string): Promise<WebChatMessage[]> {
    const body = await request<MessagesResponse>(
      `/conversations/${encodeURIComponent(conversationId)}/messages`,
    )
    return body.messages
  }

  async function sendMessage(conversationId: string, message: string): Promise<WebChatReply> {
    return request<WebChatReply>(
      `/conversations/${encodeURIComponent(conversationId)}/messages`,
      {
        method: 'POST',
        body: JSON.stringify({ message }),
      },
    )
  }

  return {
    fetchCurrentUser,
    listConversations,
    fetchMessages,
    sendMessage,
  }
}

export { WebChatApiError }
