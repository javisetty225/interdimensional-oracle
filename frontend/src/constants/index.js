export const API_BASE = 'http://localhost:8000'

export const TYPE_COLORS = {
  character: { bg: '#00d4ff15', border: '#00d4ff40', text: '#00d4ff' },
  episode:   { bg: '#a855f715', border: '#a855f740', text: '#c084fc' },
  location:  { bg: '#22c55e15', border: '#22c55e40', text: '#4ade80' },
}

export const SUGGESTED_QUERIES = [
  'Who is Rick Sanchez?',
  'What is the Citadel of Ricks?',
  'Which episodes feature Birdperson?',
  'Show me all dead characters',
  'What dimension is Earth C-137?',
]

export const STATUS_COLORS = {
  ready:      '#4ade80',
  offline:    '#f87171',
  checking:   '#94a3b8',
  'no-index': '#facc15',
}

export const STATUS_TEXTS = {
  ready:      'Online',
  offline:    'Offline — start backend',
  checking:   'Connecting...',
  'no-index': 'No index — run indexer.py',
}