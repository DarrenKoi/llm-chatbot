<template>
  <div class="flex h-screen flex-col bg-white text-gray-900 dark:bg-gray-950 dark:text-gray-100">
    <ConversationHeader
      :user="user"
      :conversation-id="selectedConversationId"
      :connection-status="connectionStatus"
    />
    <UAlert
      v-if="errorMessage"
      class="m-3"
      color="error"
      variant="subtle"
      icon="i-lucide-alert-triangle"
      :title="errorMessage"
      :close-button="{ icon: 'i-lucide-x' }"
      @close="errorMessage = null"
    />
    <div class="flex flex-1 overflow-hidden">
      <ConversationList
        :conversations="conversations"
        :selected-id="selectedConversationId"
        :creating="creatingConversation"
        @select="onSelectConversation"
        @create="onCreateConversation"
      />
      <main class="flex flex-1 flex-col">
        <ChatTimeline :messages="messages" :pending="sending" />
        <ChatComposer
          :loading="sending"
          :disabled="!user || !selectedConversationId"
          @send="onSend"
        />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import type {
  WebChatConversationSummary,
  WebChatMessage,
  WebChatUser,
} from '~/types/chat'
import { WebChatApiError } from '~/composables/useChatApi'

const api = useChatApi()

const user = ref<WebChatUser | null>(null)
const conversations = ref<WebChatConversationSummary[]>([])
const messages = ref<WebChatMessage[]>([])
const selectedConversationId = ref<string | null>(null)
const sending = ref(false)
const creatingConversation = ref(false)
const errorMessage = ref<string | null>(null)
const connectionStatus = ref<'connected' | 'connecting' | 'error' | 'unauthenticated'>('connecting')

function setError(message: string) {
  errorMessage.value = message
}

function describeError(error: unknown, fallback: string): string {
  if (error instanceof WebChatApiError) {
    if (error.status === 401) return '로그인이 필요합니다 (LASTUSER 쿠키 누락).'
    if (error.detail) return error.detail
  }
  if (error instanceof Error) return error.message
  return fallback
}

async function bootstrap() {
  connectionStatus.value = 'connecting'
  try {
    user.value = await api.fetchCurrentUser()
    conversations.value = await api.listConversations()
    if (conversations.value.length && !selectedConversationId.value) {
      await selectConversation(conversations.value[0].conversation_id)
    }
    connectionStatus.value = 'connected'
  } catch (error) {
    if (error instanceof WebChatApiError && error.status === 401) {
      connectionStatus.value = 'unauthenticated'
    } else {
      connectionStatus.value = 'error'
    }
    setError(describeError(error, '초기 데이터를 불러오지 못했습니다.'))
  }
}

async function selectConversation(conversationId: string) {
  selectedConversationId.value = conversationId
  try {
    messages.value = await api.fetchMessages(conversationId)
  } catch (error) {
    setError(describeError(error, '대화 이력을 불러오지 못했습니다.'))
  }
}

async function onSelectConversation(conversationId: string) {
  await selectConversation(conversationId)
}

function generateConversationId(): string {
  const stamp = new Date().toISOString().replace(/[^0-9]/g, '').slice(0, 14)
  const suffix = Math.random().toString(36).slice(2, 8)
  return `web-${stamp}-${suffix}`
}

async function onCreateConversation() {
  if (creatingConversation.value) return
  creatingConversation.value = true
  try {
    const newId = generateConversationId()
    selectedConversationId.value = newId
    messages.value = []
  } finally {
    creatingConversation.value = false
  }
}

async function onSend(text: string) {
  if (!selectedConversationId.value) return
  const conversationId = selectedConversationId.value
  sending.value = true
  messages.value = [...messages.value, { role: 'user', content: text }]
  try {
    const reply = await api.sendMessage(conversationId, text)
    messages.value = [...messages.value, { role: 'assistant', content: reply.reply }]
    conversations.value = await api.listConversations()
  } catch (error) {
    setError(describeError(error, '메시지를 전송하지 못했습니다.'))
  } finally {
    sending.value = false
  }
}

onMounted(bootstrap)
</script>
