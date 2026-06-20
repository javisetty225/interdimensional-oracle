/**
 * Chat state and message management.
 * Orchestrates the full query lifecycle:
 * guardrail response → sources → streaming text → done
 */
import { ref } from 'vue'
import { useApi } from './useApi.js'
import { useStream } from './useStream.js'

export function useChat() {
  const messages = ref([])
  const isStreaming = ref(false)

  const { openChatStream, submitFeedback } = useApi()
  const { readStream } = useStream()

  function buildHistory() {
    return messages.value.map((m) => ({
      role: m.role,
      content: m.content,
    }))
  }

  function addMessage(msg) {
    messages.value.push(msg)
  }

  function updateMessage(id, updates) {
    const msg = messages.value.find((m) => m.id === id)
    if (msg) Object.assign(msg, updates)
  }

  function applyChunk(chunk, assistantId) {
    if (chunk.type === 'instant') {
      updateMessage(assistantId, {
        content: chunk.text,
        streaming: false,
      })
    } else if (chunk.type === 'sources') {
      updateMessage(assistantId, {
        sources: chunk.sources,
        overallConfidence: chunk.overall_confidence,
      })
    } else if (chunk.type === 'text_delta') {
      const msg = messages.value.find((m) => m.id === assistantId)
      if (msg) msg.content += chunk.text
    } else if (chunk.type === 'guardrail_block') {
      updateMessage(assistantId, {
        content: `🚫 ${chunk.detail}`,
        streaming: false,
      })
    } else if (chunk.type === 'done') {
      updateMessage(assistantId, { streaming: false })
    } else if (chunk.type === 'error') {
      updateMessage(assistantId, {
        content: `⚠️ ${chunk.message}`,
        streaming: false,
      })
    }
  }

  async function sendMessage(query) {
    if (!query.trim() || isStreaming.value) return

    const history = buildHistory()
    const assistantId = Date.now() + 1

    addMessage({ id: Date.now(), role: 'user', content: query })
    addMessage({
      id: assistantId,
      role: 'assistant',
      content: '',
      streaming: true,
      sources: [],
      overallConfidence: 0,
      query,
    })

    isStreaming.value = true

    try {
      const response = await openChatStream(query, history)
      for await (const chunk of readStream(response)) {
        applyChunk(chunk, assistantId)
      }
    } catch (err) {
      updateMessage(assistantId, {
        content: `⚠️ Cannot reach the Oracle. Is the backend running?\n${err.message}`,
        streaming: false,
      })
    }

    isStreaming.value = false
  }

  async function sendFeedback(msgId, query, helpful) {
    try {
      await submitFeedback(msgId, query, helpful)
    } catch (e) {
      console.error('Feedback error:', e)
    }
  }

  return {
    messages,
    isStreaming,
    sendMessage,
    sendFeedback,
  }
}