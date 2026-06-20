<template>
  <div class="browse-panel">

    <!-- Header -->
    <div class="panel-header">
      <span class="panel-title">◈ DIMENSIONAL ARCHIVE</span>
      <button class="close-btn" @click="$emit('close')">✕</button>
    </div>

    <!-- Search and filter -->
    <div class="panel-search">
      <input
        v-model="search"
        placeholder="Search..."
        class="search-input"
      />
      <select v-model="filterType" class="filter-select">
        <option value="">All</option>
        <option value="character">Characters</option>
        <option value="episode">Episodes</option>
        <option value="location">Locations</option>
      </select>
    </div>

    <!-- Results list -->
    <div class="panel-results">
      <div v-if="loading" class="panel-empty">Loading...</div>

      <div v-else-if="results.length === 0" class="panel-empty">
        No results found
      </div>

      <div
        v-else
        v-for="r in results"
        :key="r.id"
        class="result-card"
        :style="{
          border: `1px solid ${
            expandedId === r.id
              ? typeColors[r.type]?.border
              : '#1e293b'
          }`,
        }"
        @click="toggleExpand(r.id)"
      >
        <!-- Card header -->
        <div class="result-header">
          <span class="result-name">{{ r.name }}</span>
          <span
            class="result-type"
            :style="{
              background: typeColors[r.type]?.bg,
              color: typeColors[r.type]?.text,
            }"
          >
            {{ r.type }}
          </span>
        </div>

        <!-- Expanded details -->
        <div v-if="expandedId === r.id" class="result-details">

          <template v-if="r.type === 'character'">
            <div>
              <span class="detail-label">Status: </span>
              <span :style="{ color: statusColor(r.raw?.status) }">
                {{ r.raw?.status }}
              </span>
            </div>
            <div>
              <span class="detail-label">Species: </span>
              {{ r.raw?.species }}{{ r.raw?.type ? ` · ${r.raw.type}` : '' }}
            </div>
            <div>
              <span class="detail-label">Origin: </span>
              {{ r.raw?.origin?.name }}
            </div>
            <div>
              <span class="detail-label">Location: </span>
              {{ r.raw?.location?.name }}
            </div>
          </template>

          <template v-else-if="r.type === 'episode'">
            <div>
              <span class="detail-label">Code: </span>
              {{ r.raw?.episode }}
            </div>
            <div>
              <span class="detail-label">Air date: </span>
              {{ r.raw?.air_date }}
            </div>
          </template>

          <template v-else-if="r.type === 'location'">
            <div>
              <span class="detail-label">Type: </span>
              {{ r.raw?.type }}
            </div>
            <div>
              <span class="detail-label">Dimension: </span>
              {{ r.raw?.dimension }}
            </div>
          </template>

        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div class="panel-footer">
      <span class="total-label">{{ total }} entries</span>
      <div class="pagination">
        <button
          :disabled="page === 1"
          class="page-btn"
          @click="page--"
        >←</button>
        <span class="page-label">{{ page }}/{{ totalPages }}</span>
        <button
          :disabled="page >= totalPages"
          class="page-btn"
          @click="page++"
        >→</button>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useApi } from '../composables/useApi.js'
import { TYPE_COLORS } from '../constants/index.js'

const PAGE_SIZE = 15

defineEmits(['close'])

const { browseEntities } = useApi()

const results = ref([])
const total = ref(0)
const loading = ref(false)
const search = ref('')
const filterType = ref('')
const page = ref(1)
const expandedId = ref(null)

const typeColors = TYPE_COLORS

const totalPages = computed(() => Math.ceil(total.value / PAGE_SIZE))

function statusColor(status) {
  if (status === 'Alive') return '#4ade80'
  if (status === 'Dead') return '#f87171'
  return '#94a3b8'
}

function toggleExpand(id) {
  expandedId.value = expandedId.value === id ? null : id
}

async function load() {
  loading.value = true
  try {
    const data = await browseEntities({
      filterType: filterType.value,
      search: search.value,
      page: page.value,
      pageSize: PAGE_SIZE,
    })
    results.value = data.results || []
    total.value = data.total || 0
  } catch (e) {
    console.error('Browse error:', e)
  }
  loading.value = false
}

// Reset to page 1 when search or filter changes
watch([search, filterType], () => { page.value = 1 })

// Reload whenever search, filter, or page changes
watch([search, filterType, page], load)

onMounted(load)
</script>

<style scoped>
.browse-panel {
  position: fixed;
  right: 0; top: 0; bottom: 0;
  width: 360px;
  background: #080c10;
  border-left: 1px solid #1e293b;
  display: flex; flex-direction: column;
  z-index: 100;
  box-shadow: -8px 0 32px #00000088;
}
.panel-header {
  padding: 14px 18px;
  border-bottom: 1px solid #1e293b;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.panel-title {
  color: #39FF14;
  font-family: monospace;
  font-size: 12px;
  font-weight: 600;
}
.close-btn {
  background: transparent; border: none;
  color: #64748b; cursor: pointer; font-size: 18px;
}
.panel-search {
  padding: 10px 14px;
  border-bottom: 1px solid #1e293b;
  display: flex; gap: 8px;
}
.search-input {
  flex: 1; background: #0f1117;
  border: 1px solid #1e293b; border-radius: 6px;
  padding: 6px 10px; color: #e2e8f0;
  font-size: 13px; outline: none;
}
.filter-select {
  background: #0f1117; border: 1px solid #1e293b;
  border-radius: 6px; padding: 6px 8px;
  color: #94a3b8; font-size: 12px; outline: none;
}
.panel-results {
  flex: 1; overflow-y: auto; padding: 8px 10px;
}
.panel-empty {
  text-align: center; padding: 32px; color: #475569;
}
.result-card {
  margin: 5px 0; padding: 10px 12px;
  background: #0f1117; border-radius: 8px;
  cursor: pointer; transition: border-color 0.2s;
}
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.result-name {
  font-size: 13px; color: #e2e8f0; font-weight: 500;
}
.result-type {
  font-size: 10px; padding: 2px 6px;
  border-radius: 3px; font-family: monospace;
}
.result-details {
  margin-top: 10px; font-size: 12px;
  color: #64748b; line-height: 1.6;
}
.detail-label { color: #94a3b8; }
.panel-footer {
  padding: 10px 14px; border-top: 1px solid #1e293b;
  display: flex; justify-content: space-between; align-items: center;
}
.total-label { font-size: 11px; color: #475569; }
.pagination { display: flex; gap: 6px; align-items: center; }
.page-btn {
  background: transparent; border: 1px solid #1e293b;
  border-radius: 4px; padding: 3px 10px;
  color: #64748b; cursor: pointer; font-size: 12px;
}
.page-btn:disabled { color: #334155; cursor: default; }
.page-label { font-size: 11px; color: #475569; }
</style>