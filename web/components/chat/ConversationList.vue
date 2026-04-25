<template>
  <aside class="flex h-full w-72 flex-col border-r border-gray-200 dark:border-gray-800">
    <div class="flex items-center justify-between gap-2 px-4 py-3">
      <span class="text-sm font-semibold text-gray-700 dark:text-gray-200">대화</span>
      <UButton
        size="xs"
        icon="i-lucide-plus"
        variant="soft"
        :loading="creating"
        @click="$emit('create')"
      >
        새 대화
      </UButton>
    </div>
    <div class="flex-1 overflow-y-auto">
      <div v-if="!conversations.length" class="px-4 py-6 text-sm text-gray-500 dark:text-gray-400">
        아직 대화가 없습니다. "새 대화"로 시작하세요.
      </div>
      <ul class="space-y-1 px-2 pb-3">
        <li v-for="item in conversations" :key="item.conversation_id">
          <button
            class="w-full rounded-md px-3 py-2 text-left transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
            :class="{ 'bg-gray-100 dark:bg-gray-800': item.conversation_id === selectedId }"
            @click="$emit('select', item.conversation_id)"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="truncate text-sm font-medium">{{ item.conversation_id }}</span>
              <UBadge v-if="item.source" size="xs" variant="subtle" color="neutral">
                {{ item.source }}
              </UBadge>
            </div>
            <div class="mt-1 truncate text-xs text-gray-500 dark:text-gray-400">
              {{ item.last_message_role }}: {{ item.last_message_preview }}
            </div>
          </button>
        </li>
      </ul>
    </div>
  </aside>
</template>

<script setup lang="ts">
import type { WebChatConversationSummary } from '~/types/chat'

interface Props {
  conversations: WebChatConversationSummary[]
  selectedId: string | null
  creating?: boolean
}

defineProps<Props>()
defineEmits<{
  select: [conversationId: string]
  create: []
}>()
</script>
