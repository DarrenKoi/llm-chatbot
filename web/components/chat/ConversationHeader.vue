<template>
  <header class="flex items-center justify-between gap-4 border-b border-gray-200 px-4 py-3 dark:border-gray-800">
    <div class="flex items-center gap-3">
      <UAvatar
        :alt="user?.user_name ?? '?'"
        size="md"
      />
      <div>
        <div class="text-sm font-semibold">
          {{ user?.user_name ?? '로그인 필요' }}
        </div>
        <div class="text-xs text-gray-500 dark:text-gray-400">
          {{ conversationId ? `대화 ${conversationId}` : '대화를 선택하거나 새로 시작하세요' }}
        </div>
      </div>
    </div>
    <UBadge
      :color="connectionColor"
      variant="subtle"
      size="sm"
    >
      {{ connectionLabel }}
    </UBadge>
  </header>
</template>

<script setup lang="ts">
import type { WebChatUser } from '~/types/chat'

interface Props {
  user: WebChatUser | null
  conversationId: string | null
  connectionStatus: 'connected' | 'connecting' | 'error' | 'unauthenticated'
}

const props = defineProps<Props>()

const connectionLabel = computed(() => {
  switch (props.connectionStatus) {
    case 'connected':
      return '연결됨'
    case 'connecting':
      return '연결 중'
    case 'error':
      return '오류'
    case 'unauthenticated':
      return '인증 필요'
    default:
      return ''
  }
})

const connectionColor = computed<'success' | 'warning' | 'error' | 'neutral'>(() => {
  switch (props.connectionStatus) {
    case 'connected':
      return 'success'
    case 'connecting':
      return 'warning'
    case 'error':
      return 'error'
    default:
      return 'neutral'
  }
})
</script>
