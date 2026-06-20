<template>
  <div class="confidence-bar">
    <div class="track">
      <div
        class="fill"
        :style="{ width: `${pct}%`, background: color }"
      />
    </div>
    <span class="label" :style="{ color }">{{ pct }}%</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  confidence: { type: Number, required: true },
})

const pct = computed(() => Math.round(props.confidence * 100))

const color = computed(() => {
  if (pct.value >= 70) return '#4ade80'
  if (pct.value >= 40) return '#facc15'
  return '#f87171'
})
</script>

<style scoped>
.confidence-bar {
  display: flex;
  align-items: center;
  gap: 6px;
}
.track {
  width: 44px;
  height: 3px;
  background: #1e293b;
  border-radius: 2px;
  overflow: hidden;
}
.fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s ease;
}
.label {
  font-size: 10px;
  font-family: monospace;
}
</style>