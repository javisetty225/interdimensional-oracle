<template>
  <div class="app">

    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <div class="portal-icon">🌀</div>
        <div>
          <div class="app-title">INTERDIMENSIONAL ORACLE</div>
          <div class="app-status">
            <span :style="{ color: statusColor }">● {{ statusText }}</span>
            <span> · Rick & Morty Universe</span>
          </div>
        </div>
      </div>
      <button
        class="archive-btn"
        :class="{ active: showBrowse }"
        @click="showBrowse = !showBrowse"
      >
        ◈ Archive
      </button>
    </header>

    <!-- Chat area -->
    <main
      class="chat-area"
      :style="{ paddingRight: showBrowse ? '400px' : '20px' }"
    >
      <!-- Empty state with suggested queries -->
      <div v-if="messages.length === 0" class="empty-state">
        <div class="empty-icon">🌀</div>
        <div class="empty-title">The Oracle is ready.</div>
        <div class="empty-subtitle">
          Ask about any character, episode, or location
          in the Rick & Morty universe.
        </div>
        <div class="suggestions">
          <button
            v-for="q in SUGGESTED_QUERIES"
            :key="q"
            class="suggestion-btn"
            @click="sendMessage(q)"
          >
            {{ q }}
          </button>
        </div>
      </div>

      <!-- Message list -->
      <ChatMessage
        v-for="msg in messages"
        :key="msg.id"
        :msg="msg"
        @feedback="sendFeedback"
      />

      <!-- Scroll anchor -->
      <div ref="bottomRef" />
    </main>

    <!-- Input area -->
    <footer
      class="input-area"
      :style="{ paddingRight: showBrowse ? '400px' : '20px' }"
    >
      <div class="input-wrapper">
        <div class="input-box">
          <textarea
            v-model="input"
            rows="1"
            placeholder="Ask about any dimension, character, or episode..."
            class="chat-input"
            @keydown.enter.prevent="handleEnter"
            @input="autoResize"
          />
        </div>
        <button
          class="send-btn"
          :class="{ active: input.trim() && !isStreaming }"
          :disabled="isStreaming || !input.trim()"
          @click="handleSend"
        >
          ↑
        </button>
      </div>
      <div class="input-hint">
        RAG-powered · Answers from retrieved data only · Press Enter to send
      </div>
    </footer>

    <!-- Browse panel -->
    <BrowsePanel
      v-if="showBrowse"
      @close="showBrowse = false"
    />

  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import ChatMessage from './components/ChatMessage.vue'
import BrowsePanel from './components/BrowsePanel.vue'
import { useChat } from './composables/useChat.js'
import { useApi } from './composables/useApi.js'
import {
  SUGGESTED_QUERIES,
  STATUS_COLORS,
  STATUS_TEXTS,
} from './constants/index.js'

const { messages, isStreaming, sendMessage, sendFeedback } = useChat()
const { checkHealth } = useApi()

const input = ref('')
const showBrowse = ref(false)
const apiStatus = ref('checking')
const bottomRef = ref(null)

const statusColor = computed(() => STATUS_COLORS[apiStatus.value])
const statusText = computed(() => STATUS_TEXTS[apiStatus.value])

// Check backend health on mount
onMounted(async () => {
  try {
    const data = await checkHealth()
    apiStatus.value = data.index_loaded ? 'ready' : 'no-index'
  } catch {
    apiStatus.value = 'offline'
  }
})

// Auto scroll to bottom when messages change
watch(
  messages,
  () => {
    nextTick(() => {
      bottomRef.value?.scrollIntoView({ behavior: 'smooth' })
    })
  },
  { deep: true }
)

function handleEnter(e) {
  if (!e.shiftKey) handleSend()
}

function handleSend() {
  const query = input.value.trim()
  if (!query || isStreaming.value) return
  sendMessage(query)
  input.value = ''
}

function autoResize(e) {
  const el = e.target
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}
</script>

<!-- Global styles — animations and scrollbar -->
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500&display=swap');

@keyframes portalPulse {
  0%, 100% { box-shadow: 0 0 8px #39FF1433; }
  50%       { box-shadow: 0 0 18px #39FF1466; }
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #050810; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 2px; }
</style>

<!-- Scoped styles — component-specific layout -->
<style scoped>
.app {
  min-height: 100vh;
  background: #050810;
  color: #e2e8f0;
  font-family: 'Inter', system-ui, sans-serif;
  display: flex;
  flex-direction: column;
}

.header {
  padding: 12px 20px;
  background: #080c10;
  border-bottom: 1px solid #0f172a;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.portal-icon {
  width: 36px; height: 36px;
  border-radius: 50%;
  background: #0a1a0d;
  border: 2px solid #39FF14;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px;
  animation: portalPulse 3s ease-in-out infinite;
}
.app-title {
  font-family: monospace;
  font-size: 14px;
  font-weight: 600;
  color: #39FF14;
  letter-spacing: .05em;
}
.app-status {
  font-size: 11px;
  color: #475569;
}
.archive-btn {
  background: transparent;
  border: 1px solid #1e293b;
  border-radius: 6px;
  padding: 6px 14px;
  color: #64748b;
  cursor: pointer;
  font-size: 12px;
  font-family: monospace;
  transition: all 0.2s;
}
.archive-btn.active {
  background: #0f2647;
  border-color: #00d4ff;
  color: #00d4ff;
}

.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
  max-width: 780px;
  width: 100%;
  margin: 0 auto;
  transition: padding-right 0.3s;
}

.empty-state {
  text-align: center;
  padding-top: 60px;
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.empty-title {
  font-family: monospace;
  font-size: 18px;
  color: #39FF14;
  margin-bottom: 8px;
}
.empty-subtitle {
  font-size: 13px;
  color: #475569;
  margin-bottom: 32px;
}
.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}
.suggestion-btn {
  background: #0f1117;
  border: 1px solid #1e293b;
  border-radius: 20px;
  padding: 8px 16px;
  color: #94a3b8;
  font-size: 12px;
  cursor: pointer;
  font-family: 'Inter', sans-serif;
  transition: all 0.2s;
}
.suggestion-btn:hover {
  border-color: #39FF1466;
  color: #39FF14;
}

.input-area {
  border-top: 1px solid #0f172a;
  background: #080c10;
  padding: 14px 20px;
  flex-shrink: 0;
  transition: padding-right 0.3s;
}
.input-wrapper {
  max-width: 780px;
  margin: 0 auto;
  display: flex;
  gap: 10px;
  align-items: flex-end;
}
.input-box {
  flex: 1;
  background: #0f1117;
  border: 1px solid #1e293b;
  border-radius: 10px;
  padding: 8px 12px;
}
.chat-input {
  background: transparent;
  border: none;
  color: #e2e8f0;
  font-size: 13px;
  width: 100%;
  font-family: 'Inter', sans-serif;
  outline: none;
  overflow: hidden;
  min-height: 20px;
  resize: none;
}
.send-btn {
  width: 40px; height: 40px;
  border-radius: 8px;
  background: #0f1117;
  border: 1px solid #1e293b;
  color: #334155;
  cursor: default;
  font-size: 16px;
  font-weight: 700;
  flex-shrink: 0;
  transition: all 0.2s;
}
.send-btn.active {
  background: #39FF14;
  border-color: #39FF14;
  color: #050810;
  cursor: pointer;
}
.input-hint {
  max-width: 780px;
  margin: 5px auto 0;
  font-size: 11px;
  color: #334155;
}
</style>