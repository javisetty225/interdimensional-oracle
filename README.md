# 🌀 Interdimensional Oracle

> A RAG-powered AI agent that answers questions about the Rick & Morty universe — exclusively from retrieved data, never from LLM memory.

---

## The Problem

The Interdimensional Council of Ricks has a data problem. 826 characters, 51 episodes, 126 locations across infinite dimensions. Even the smartest Rick loses track. This oracle solves it.

---

## Architecture

```
User Query
    ↓
Guardrails (guardrails.py)
    ├── Greeting / help  →  instant response, no LLM, zero API cost
    ├── Off-topic        →  blocked immediately, no LLM, zero API cost
    └── Valid query      →  passes through
    ↓
ChromaDB Retriever (retriever.py)
    ├── Query encoded as 768-dim embedding vector
    ├── Cosine similarity search over 1003 document embeddings
    └── Returns top-5 documents with confidence scores
    ↓
RAG Pipeline (rag.py)
    ├── Retrieved documents injected into prompt as context
    ├── System prompt enforces strict grounding — no hallucination
    └── Claude streams response via Server-Sent Events
    ↓
Vue.js Frontend
    ├── Confidence bar shown from retrieval scores
    ├── Text streams word by word
    └── Source tags + 👍/👎 feedback
```

---

## Retrieval Strategy — Why ChromaDB

### What was evaluated first: BM25 + TF-IDF

BM25 is a keyword search algorithm that matches exact words between query and document.

**What worked:** Exact name queries like "Rick Sanchez" or "S03E01" performed well.

**What failed:** Paraphrased queries failed consistently:

- "winged alien friend of Rick" → returned "Alien Rick" not Birdperson
- "first episode of season 3" → returned character documents not episodes

**Root cause:** The word "winged" does not exist in Birdperson's document. BM25 cannot understand that "winged" and "Bird-Person" are semantically related — it only matches exact words.

### Why ChromaDB with sentence-transformers

ChromaDB stores documents as mathematical vectors that capture meaning. Two semantically similar sentences produce similar vectors even with no shared words. After switching:

- "characters from Bird World" → correctly finds Birdperson
- "what dimension is Earth C-137" → correctly finds the location document
- "first episode of the show" → correctly finds Pilot

### Why ChromaDB over other vector databases

| Option | Why not chosen |
|--------|---------------|
| Pinecone | External API — network calls, latency, cost per query |
| Weaviate | Requires a separate Docker container to run |
| pgvector | Requires PostgreSQL — overkill for 1003 documents |
| FAISS | In-memory only, no persistence — rebuilds on every restart |
| **ChromaDB** | Local file persistence, zero external dependencies, no server needed |

### Why all-mpnet-base-v2 over other embedding models

| Option | Why not chosen |
|--------|---------------|
| all-MiniLM-L6-v2 | Tested — weaker results on paraphrased queries |
| text-embedding-3-large | OpenAI API call per query — adds cost and latency |
| **all-mpnet-base-v2** | Runs fully locally, no API cost, strong semantic understanding |

---

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Backend | FastAPI + Python | Async, native SSE streaming support |
| Vector store | ChromaDB | Local persistence, zero external dependencies |
| Embeddings | all-mpnet-base-v2 | Runs fully locally, strong semantic understanding |
| LLM | Claude Sonnet (Anthropic) | Strong instruction following, strict context grounding |
| Frontend | Vue.js + Vite | Recruiter preference, clean composables architecture |

---

## Features

**Required**
- ✅ Data pipeline — fetches 826 characters, 51 episodes, 126 locations from the Rick & Morty API with pagination and rate limit handling
- ✅ RAG pipeline — semantic retrieval → context injection → streamed response with source citation
- ✅ Chat interface — conversation history, streaming responses, clean Vue.js UX
- ✅ Prompt engineering — Oracle persona, strict grounding rules, off-topic refusal
- ✅ Guardrails — dual layer: code-level pattern classifier + prompt-level LLM instruction

**Optional (all four implemented)**
- ✅ Feedback mechanism — 👍/👎 per message logged to `feedback.jsonl` for Human-in-the-Loop signal collection
- ✅ Confidence display — cosine similarity score shown as percentage bar before each response
- ✅ Browse mode — searchable, filterable, paginated archive of all 1003 entities alongside the chat
- ✅ Streaming responses — Server-Sent Events stream Claude's response token by token

---

## Setup — Running Locally in 5 Minutes

### Prerequisites
- Python 3.13+ (tested on 3.14.0)
- Node.js 20+ (tested on v20.20.1)
- Anthropic API key — [console.anthropic.com](https://console.anthropic.com)

### Step 1 — Clone and install

```bash
git clone https://github.com/javisetty225/interdimensional-oracle
cd interdimensional-oracle
pip install -e .
```

### Step 2 — Add your API key

```bash
cp .env.example .env
# Edit .env and add your key:
# ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### Step 3 — Fetch data from the Rick & Morty API

```bash
cd backend
python -m data.fetcher
```

Expected output:
```
✅ character: 826 records saved
✅ episode:   51 records saved
✅ location:  126 records saved
```

### Step 4 — Build the vector index

```bash
python -m data.indexer
```

> First run downloads the embedding model (~420MB). This is cached locally — subsequent runs take under 2 minutes.

### Step 5 — Start the backend

```bash
uvicorn api.main:app --reload --port 8000
```

Verify at `http://localhost:8000/health`:
```json
{"status": "ok", "index_loaded": true, "doc_count": 1003}
```

### Step 6 — Start the frontend

```bash
cd ../frontend
npm install
npm run dev
```

Open `http://localhost:5173` — the Oracle is ready.

---

## Evaluation

The system is evaluated using **RAGAS** — the industry standard RAG evaluation framework — with **Claude Haiku as the LLM judge**.

### Metrics

| Metric | Description |
|--------|-------------|
| **Faithfulness** | Does the answer use only retrieved context? 1.0 = no hallucination |
| **Context Precision** | Are retrieved documents relevant to the query? 1.0 = all docs useful |
| **Context Recall** | Does context contain enough to answer correctly? 1.0 = nothing missing |

### Results

| Metric | Score | Notes |
|--------|-------|-------|
| Faithfulness | **0.60** | Oracle persona adds narrative commentary that RAGAS flags as outside retrieved context. All factual claims are grounded. |
| Context Precision | **0.85** | 85% of retrieved documents are directly relevant to each query. |
| Context Recall | **1.00** | Retrieved context always contains all information needed to answer. |

**Note on faithfulness score:** The Oracle persona intentionally adds sardonic commentary ("*sighs across seventeen dimensions*") which RAGAS correctly identifies as not present in the retrieved context. The factual content — character names, statuses, episode codes, dimensions — is always grounded in retrieved data. A minimal prompt without persona scores above 0.90 on faithfulness.

### Run the evaluation yourself

```bash
cd backend
python ../scripts/evaluate.py
```

Results are saved to `scripts/evaluation_results.json`.

---

## Example Queries

```
Who is Rick Sanchez?
What is the Citadel of Ricks?
Which episodes feature Birdperson?
What dimension is Earth C-137 in?
Show me all characters from Bird World
What is the status of Morty Smith?
```

---

## Project Structure

```
interdimensional-oracle/
├── pyproject.toml              ← project metadata and dependencies
├── .env.example                ← API key template
├── scripts/
│   └── evaluate.py             ← RAGAS evaluation script
├── backend/
│   ├── api/
│   │   ├── main.py             ← FastAPI app setup and middleware
│   │   ├── endpoints.py        ← all route handlers
│   │   └── models.py           ← Pydantic request/response models
│   ├── core/
│   │   ├── rag.py              ← RAG pipeline + prompt-level guardrail
│   │   ├── retriever.py        ← ChromaDB semantic search
│   │   └── guardrails.py       ← code-level query classification
│   └── data/
│       ├── fetcher.py          ← Rick & Morty API data fetcher
│       ├── indexer.py          ← ChromaDB vector index builder
│       ├── raw/                ← downloaded JSON (gitignored)
│       └── chroma_db/          ← vector index files (gitignored)
└── frontend/
    └── src/
        ├── App.vue             ← main layout and shell
        ├── constants/          ← shared colors and configuration
        ├── composables/        ← useChat, useApi, useStream
        └── components/         ← ChatMessage, BrowsePanel, ConfidenceBar
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Server and index status |
| GET | `/stats` | Document counts by entity type |
| POST | `/chat/stream` | Streaming SSE chat endpoint |
| POST | `/feedback` | Log 👍/👎 feedback to JSONL |
| POST | `/browse` | Paginated, searchable entity browser |

---

## Guardrails — Two Mechanisms

**Code-level (`guardrails.py`) — runs before any LLM call**

```
Greeting      → instant welcome response, no LLM, zero API cost
Help request  → instant help response, no LLM, zero API cost
R&M signals   → allowed through to retriever and LLM
Off-topic     → blocked with explanation, no LLM, zero API cost
```

Greetings and help requests get instant rule-based responses. Sending "hi" to an LLM wastes tokens and adds unnecessary latency — rule-based responses handle these cases in zero milliseconds.

**Prompt-level (`rag.py` system prompt) — runs inside the LLM**

Claude is instructed to answer only from retrieved context and refuse non-Rick & Morty questions. This catches anything the code layer misses — for example "Who is the US president?" has no blocked keywords but the LLM correctly refuses it.

---

## Known Limitations

**Relationship and paraphrased queries**

Queries like "Rick's best friend" or "winged alien friend of Rick" fail
because the Rick & Morty API only stores factual entity data — name,
species, status, origin. The relationship "Birdperson is Rick's friend"
is never written anywhere in the source data. No retrieval model can
find information that was never stored.

Fix: ingest episode transcripts to add relationship context.

**Combined attribute queries**

"Show me all dead characters" returns partial results. Semantic search
finds the closest meaning match — it does not filter by field value.

Fix: hybrid search combining semantic similarity with metadata filtering:

```python
collection.get(where={"status": "Dead"})
```

## What I Would Improve With More Time

| Priority | Improvement | Why It Matters for This Project |
|----------|-------------|--------------------------------|
| High | **Hybrid search** — ChromaDB semantic similarity + metadata filtering | Fixes "show me all dead characters" — semantic search cannot filter by field value |
| High | **Query rewriting with HyDE** — generate hypothetical answer first, use it to search | Fixes paraphrased queries — hypothetical document contains right vocabulary for retrieval |
| High | **Redis response caching** — cache answers to common queries by question hash | Rick & Morty universe is finite — "Who is Rick Sanchez?" asked repeatedly. Cache hit returns in <10ms at zero API cost |
| High | **Cross-encoder re-ranker** — re-rank top-20 cosine results before passing top-5 to Claude | Would improve Context Precision from 0.85 toward 0.95+ — directly measurable with existing RAGAS evaluation |
| Medium | **Conversation history persistence** — store chat history in PostgreSQL | Currently history lives in browser memory and is lost on refresh. Database enables cross-session continuity and conversation analytics |
| Medium | **Summarised context window** — keep last 5 full Q&A pairs verbatim, summarise older turns | Current sliding window (`history[-12:]`) drops older context entirely. Summarisation preserves long-term context while controlling token cost |
| Medium | **Close the feedback loop** — use `feedback.jsonl` signals to identify and fix weak queries | Currently 👍/👎 data is collected but never acted on. Analysing low-rated queries reveals specific retrieval and prompt failures |
| Medium | **Observability with Langfuse** — trace every query through retrieval → prompt → response | When a query returns a bad answer there is currently no visibility into whether retrieval, context injection, or the LLM caused it |
| Medium | **Episode transcript ingestion** — add full episode text to the knowledge base | Enables relationship queries like "Rick's best friend" — the API never states relationships but transcripts do |
| Low | **Nightly data refresh** — scheduled job to pull new API data and rebuild index | Ensures the knowledge base stays current if the Rick & Morty API adds new characters or episodes |