/**
 * API communication layer.
 * All fetch calls to the backend live here.
 * Components never call fetch directly.
 */
import { API_BASE } from '../constants/index.js'

export function useApi() {

  async function checkHealth() {
    const res = await fetch(`${API_BASE}/health`)
    return res.json()
  }

  async function submitFeedback(msgId, query, helpful) {
    await fetch(`${API_BASE}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message_id: String(msgId),
        query,
        helpful,
      }),
    })
  }

  async function browseEntities({ filterType, search, page, pageSize }) {
    const res = await fetch(`${API_BASE}/browse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filter_type: filterType || null,
        search: search || null,
        page,
        page_size: pageSize,
      }),
    })
    return res.json()
  }

  async function openChatStream(query, history, topK = 5) {
    return fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, history, top_k: topK }),
    })
  }

  return {
    checkHealth,
    submitFeedback,
    browseEntities,
    openChatStream,
  }
}