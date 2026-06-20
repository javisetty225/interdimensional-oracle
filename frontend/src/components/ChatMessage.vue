<template>
  <div
    class="message-wrapper"
    :class="isUser ? 'align-end' : 'align-start'"
  >
    <!-- Oracle header — shown only for assistant messages -->
    <div v-if="!isUser" class="oracle-header">
      <div class="oracle-avatar">🛸</div>
      <span class="oracle-label">ORACLE</span>
      <ConfidenceBar
        v-if="uniqueSources.length > 0"
        :confidence="msg.overallConfidence || 0"
      />
    </div>

    <!-- Message bubble -->
    <div
      class="bubble"
      :class="isUser ? 'bubble-user' : 'bubble-assistant'"
    >
      <!-- Oracle messages render markdown -->
      <span
        v-if="!isUser"
        v-html="renderedContent"
      />
      <!-- User messages render as plain text -->
      <span v-else>{{ msg.content }}</span>

      <!-- Blinking cursor while streaming -->
      <span v-if="msg.streaming" class="cursor">▋</span>
    </div>

    <!-- Source tags — shown only for assistant messages with sources -->
    <div
      v-if="!isUser && uniqueSources.length > 0"
      class="sources"
    >
      <span
        v-for="(source, i) in uniqueSources"
        :key="i"
        class="source-tag"
        :style="{
          background: typeColors[source.type]?.bg,
          border: `1px solid ${typeColors[source.type]?.border}`,
          color: typeColors[source.type]?.text,
        }"
      >
        <span class="source-type">{{ source.type.toUpperCase() }}</span>
        {{ source.name }}
      </span>
    </div>

    <!-- Feedback buttons — shown after streaming completes -->
    <div
      v-if="!isUser && !msg.streaming && msg.content"
      class="feedback"
    >
      <span class="feedback-label">Helpful?</span>
      <button
        v-for="helpful in [true, false]"
        :key="String(helpful)"
        :disabled="voted !== null"
        class="feedback-btn"
        :class="{
          'voted-yes': voted === true && helpful,
          'voted-no': voted === false && !helpful,
        }"
        @click="handleVote(helpful)"
      >
        {{ helpful ? '👍' : '👎' }}
      </button>
    </div>

  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { marked } from 'marked'
import ConfidenceBar from './ConfidenceBar.vue'
import { TYPE_COLORS } from '../constants/index.js'

// Configure marked for clean rendering
marked.setOptions({
  breaks: true,  // convert single \n to <br>
})

const props = defineProps({
  msg: { type: Object, required: true },
})

const emit = defineEmits(['feedback'])

const voted = ref(null)

const isUser = computed(() => props.msg.role === 'user')

const typeColors = TYPE_COLORS

// Deduplicate sources by name before rendering
const uniqueSources = computed(() =>
  (props.msg.sources || []).filter(
    (s, i, arr) => arr.findIndex((x) => x.name === s.name) === i
  )
)

// Render markdown for Oracle responses
const renderedContent = computed(() => {
  if (!props.msg.content) return ''
  return marked.parse(props.msg.content)
})

function handleVote(helpful) {
  if (voted.value !== null) return
  voted.value = helpful
  emit('feedback', props.msg.id, props.msg.query, helpful)
}
</script>

<style scoped>
.message-wrapper {
  display: flex;
  flex-direction: column;
  margin-bottom: 20px;
}
.align-end   { align-items: flex-end; }
.align-start { align-items: flex-start; }

.oracle-header {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 6px;
}
.oracle-avatar {
  width: 22px; height: 22px;
  border-radius: 50%;
  background: #0a1a0d;
  border: 1px solid #39FF14;
  display: flex; align-items: center; justify-content: center;
  font-size: 10px;
}
.oracle-label {
  font-size: 10px;
  color: #64748b;
  font-family: monospace;
}

.bubble {
  max-width: 88%;
  padding: 11px 15px;
  color: #cbd5e1;
  font-size: 14px;
  line-height: 1.65;
  word-break: break-word;
}
.bubble-user {
  border-radius: 14px 14px 4px 14px;
  background: linear-gradient(135deg, #1e3a5f, #0f2647);
  border: 1px solid #00d4ff33;
  white-space: pre-wrap;
}
.bubble-assistant {
  border-radius: 4px 14px 14px 14px;
  background: #0f1117;
  border: 1px solid #1e293b;
}
.cursor { color: #39FF14; }

/* Markdown rendering styles for Oracle responses */
:deep(p)            { margin-bottom: 8px; }
:deep(p:last-child) { margin-bottom: 0; }
:deep(strong)       { color: #e2e8f0; font-weight: 600; }
:deep(em)           { color: #94a3b8; font-style: italic; }
:deep(ul), :deep(ol) {
  padding-left: 20px;
  margin-bottom: 8px;
}
:deep(li)           { margin-bottom: 4px; }
:deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin-bottom: 8px;
  font-size: 13px;
}
:deep(th), :deep(td) {
  border: 1px solid #1e293b;
  padding: 6px 10px;
  text-align: left;
}
:deep(th) {
  background: #080c10;
  color: #94a3b8;
}
:deep(hr) {
  border: none;
  border-top: 1px solid #1e293b;
  margin: 12px 0;
}
:deep(code) {
  background: #080c10;
  padding: 1px 5px;
  border-radius: 3px;
  font-family: monospace;
  font-size: 12px;
  color: #39FF14;
}
:deep(blockquote) {
  border-left: 3px solid #1e293b;
  padding-left: 12px;
  color: #64748b;
  margin: 8px 0;
}
:deep(h1), :deep(h2), :deep(h3) {
  color: #e2e8f0;
  margin-bottom: 8px;
  font-weight: 600;
}

.sources {
  display: flex;
  flex-wrap: wrap;
  margin-top: 6px;
  max-width: 88%;
}
.source-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 4px;
  margin: 2px;
  font-size: 11px;
  font-family: monospace;
  white-space: nowrap;
}
.source-type {
  font-size: 9px;
  opacity: 0.7;
}

.feedback {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}
.feedback-label {
  font-size: 11px;
  color: #475569;
}
.feedback-btn {
  background: transparent;
  border: 1px solid #334155;
  border-radius: 4px;
  padding: 2px 8px;
  cursor: pointer;
  color: #64748b;
  font-size: 12px;
  transition: all 0.2s;
}
.feedback-btn:disabled { cursor: default; }
.voted-yes {
  background: #14532d;
  border-color: #4ade80;
  color: #4ade80;
}
.voted-no {
  background: #450a0a;
  border-color: #f87171;
  color: #f87171;
}
</style>