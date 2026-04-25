<template>
  <div ref="scroller" class="flex-1 overflow-y-auto px-4 py-4">
    <div v-if="!messages.length && !pending" class="flex h-full items-center justify-center text-sm text-gray-500 dark:text-gray-400">
      메시지를 입력하면 대화가 시작됩니다.
    </div>
    <ul class="mx-auto flex max-w-3xl flex-col gap-3">
      <li
        v-for="(message, index) in messages"
        :key="`${index}-${message.role}`"
        class="flex"
        :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
      >
        <UCard
          :ui="{ body: 'p-3' }"
          class="max-w-[80%]"
          :class="message.role === 'user' ? 'bg-primary-50 dark:bg-primary-950' : ''"
        >
          <div class="text-xs font-medium text-gray-500 dark:text-gray-400">
            {{ message.role === 'user' ? '나' : message.role }}
          </div>
          <div class="mt-1 whitespace-pre-wrap break-words text-sm">
            {{ message.content }}
          </div>
        </UCard>
      </li>
      <li v-if="pending" class="flex justify-start">
        <UCard :ui="{ body: 'p-3' }" class="max-w-[80%]">
          <div class="text-xs font-medium text-gray-500 dark:text-gray-400">assistant</div>
          <div class="mt-1 flex items-center gap-2 text-sm text-gray-500">
            <UIcon name="i-lucide-loader-circle" class="animate-spin" />
            응답 생성 중...
          </div>
        </UCard>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import type { WebChatMessage } from '~/types/chat'

interface Props {
  messages: WebChatMessage[]
  pending?: boolean
}

const props = defineProps<Props>()
const scroller = ref<HTMLElement | null>(null)

function scrollToBottom() {
  nextTick(() => {
    if (!scroller.value) return
    scroller.value.scrollTop = scroller.value.scrollHeight
  })
}

watch(
  () => props.messages.length,
  () => scrollToBottom(),
)
watch(
  () => props.pending,
  () => scrollToBottom(),
)
onMounted(scrollToBottom)
</script>
