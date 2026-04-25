<template>
  <form
    class="flex items-end gap-2 border-t border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-gray-950"
    @submit.prevent="onSubmit"
  >
    <UTextarea
      v-model="draft"
      :rows="1"
      :maxrows="6"
      autoresize
      :disabled="disabled"
      placeholder="메시지를 입력하세요…"
      class="flex-1"
      @keydown.enter.exact.prevent="onSubmit"
    />
    <UButton
      type="submit"
      icon="i-lucide-send"
      :loading="loading"
      :disabled="disabled || !draft.trim()"
    >
      전송
    </UButton>
  </form>
</template>

<script setup lang="ts">
interface Props {
  loading?: boolean
  disabled?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{ send: [text: string] }>()

const draft = ref('')

function onSubmit() {
  const trimmed = draft.value.trim()
  if (!trimmed || props.loading || props.disabled) return
  emit('send', trimmed)
  draft.value = ''
}
</script>
