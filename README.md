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
Retriever (retriever.py)
    ├── Attribute-list query  →  exact metadata filtering
    │   ("all dead characters")   (status / species / gender)
    └── Everything else       →  semantic search
        ├── Query encoded as 768-dim embedding vector
        ├── Cosine similarity over 1003 document embeddings
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

## Retrieval Strategy

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

### Hybrid retrieval — semantic search + metadata filtering

Semantic search is strong at meaning but weak at exact field filtering. A query like "show me all dead characters" is not a similarity problem — it is a structured filter over a known field. Pure embedding search returns the *closest in meaning*, not *every record where status = Dead*.

The retriever therefore routes by intent:

- **Attribute-list queries** — a list intent (the words "all", "list", "show", "every", "how many", "which", or a plural entity noun like "characters"/"locations"/"episodes") combined with a known attribute (status, species, or gender) is routed to **exact metadata filtering** via ChromaDB's `where` clause. "Show me all dead characters" returns characters where `status == "Dead"`, not the nearest semantic neighbours.
- **Everything else** — including single-entity questions like "Is Rick dead?" — stays on **semantic search**, where embeddings are the right tool.

This keeps embeddings for what they are good at (meaning) and uses exact filtering for what they are bad at (field equality), without the user having to know which path they triggered.

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
- ✅ Data pipeline — fetches 826 characters, 51 episodes, 126 locations from the Rick & Morty API with pagination and rate-limit handling
- ✅ RAG pipeline — hybrid retrieval (semantic + metadata filtering) → context injection → streamed response with source citation
- ✅ Chat interface — conversation history, streaming responses, clean Vue.js UX
- ✅ Prompt engineering — Oracle persona, strict grounding rules, off-topic refusal
- ✅ Guardrails — dual layer: code-level pattern classifier + prompt-level LLM instruction

**Optional (all four implemented)**
- ✅ Feedback mechanism — 👍/👎 per message logged to `feedback.jsonl` for Human-in-the-Loop signal collection
- ✅ Confidence display — cosine similarity score shown as a percentage bar before each response
- ✅ Browse mode — searchable, filterable, paginated archive of all 1003 entities alongside the chat
- ✅ Streaming responses — Server-Sent Events stream Claude's response token by token

**Engineering**
- ✅ Unit tests for the code-level guardrail classifier (`tests/test_guardrails.py`)
- ✅ Automated RAG evaluation with RAGAS (see below)

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
# for tests + evaluation, install the dev extras:
# pip install -e ".[dev]"
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

The fetcher logs a confirmation as it saves each file (`character.json`, `episode.json`, `location.json`) to `data/raw/` — 826 characters, 51 episodes, and 126 locations, with pagination and 429 rate-limit handling.

### Step 4 — Build the vector index

```bash
python -m data.indexer
```

> First run downloads the embedding model (~420MB). This is cached locally — subsequent runs take under 2 minutes. The index stores `status`, `species`, and `gender` as filterable metadata, which powers the hybrid attribute-filtering path.

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

### Run the tests

```bash
pytest
```

---

## Evaluation

The system is evaluated with **RAGAS** — a standard RAG evaluation framework — using **Claude Haiku as the LLM judge** over a 10-question golden set.

### Metrics

| Metric | Description |
|--------|-------------|
| **Faithfulness** | Does the answer use only retrieved context? 1.0 = no ungrounded statements |
| **Context Precision** | Are retrieved documents relevant to the query? 1.0 = all docs useful |
| **Context Recall** | Does context contain enough to answer correctly? 1.0 = nothing missing |

These three isolate the two failure points of a RAG system: precision and recall measure **retrieval**, faithfulness measures **generation grounding**. If an answer is wrong, the metrics localise the cause — a retrieval problem (precision/recall) versus the model drifting off-context (faithfulness).

### Results

Two prompt configurations were evaluated to isolate the cost of the Oracle persona — the shipped persona prompt versus a minimal baseline prompt used only as an evaluation control.

| Metric | Persona (shipped) | Minimal (baseline) |
|--------|-------------------|--------------------|
| Faithfulness | ~0.59 | ~0.95 |
| Context Precision | 0.85 | 0.85 |
| Context Recall | 1.00 | 1.00 |

**Reading this:** Context precision and recall are **identical** across both runs — the system prompt affects only the generated answer, not retrieval, so only the generation metric moves. The faithfulness gap is the *measured cost* of the persona: the Oracle's sardonic commentary adds sentences not literally present in the retrieved context, which RAGAS correctly counts as ungrounded. Crucially, this is a stylistic gap, not a factual one — character names, statuses, episode codes, and dimensions remain grounded in both configurations.

The ~0.95 minimal score confirms the underlying retrieval-and-grounding pipeline is sound. Keeping the persona is therefore a deliberate trade-off — personality is a graded requirement, and the lost faithfulness points are decorative, not factual.

> Note: faithfulness is LLM-judged and carries roughly ±0.05 run-to-run variance; the retrieval metrics are deterministic. Quote these numbers as approximate.

### Run the evaluation yourself

```bash
pip install -e ".[dev]"
python scripts/evaluate.py
```

Results are saved to `scripts/evaluation_results.json`.

---

## Example Queries

```
Who is Rick Sanchez?
What is the Citadel of Ricks?
Which episodes feature Birdperson?
What dimension is Earth C-137 in?
What is the status of Morty Smith?
Show me all dead characters          ← hybrid metadata filter
How many female characters are there ← hybrid metadata filter
```

---

## Project Structure

```
interdimensional-oracle/
├── pyproject.toml              ← project metadata and dependencies
├── .env.example                ← API key template
├── scripts/
│   ├── evaluate.py             ← RAGAS evaluation (persona vs minimal)
│   ├── golden_dataset.py       ← evaluation question set
│   └── evaluation_results.json ← committed evaluation artifact
├── tests/
│   └── test_guardrails.py      ← unit tests for the guardrail classifier
├── backend/
│   ├── api/
│   │   ├── main.py             ← FastAPI app setup and middleware
│   │   ├── endpoints.py        ← all route handlers
│   │   └── models.py           ← Pydantic request/response models
│   ├── core/
│   │   ├── rag.py              ← RAG pipeline + prompt-level guardrail
│   │   ├── retriever.py        ← hybrid retrieval (semantic + metadata)
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

Greetings and help requests get instant rule-based responses. Sending "hi" to an LLM wastes tokens and adds unnecessary latency — rule-based responses handle these cases in zero milliseconds. The classifier is covered by unit tests in `tests/test_guardrails.py`.

**Prompt-level (`rag.py` system prompt) — runs inside the LLM**

Claude is instructed to answer only from retrieved context and refuse non-Rick & Morty questions. This catches anything the code layer misses — for example "Who is the US president?" has no blocked keywords but the LLM correctly refuses it.

---

## Known Limitations

**Relationship and paraphrased queries**

Queries like "Rick's best friend" or "winged alien friend of Rick" fail because the Rick & Morty API only stores factual entity data — name, species, status, origin. The relationship "Birdperson is Rick's friend" is never written anywhere in the source data. No retrieval model can find information that was never stored.

Fix: ingest episode transcripts to add relationship context.

**Attribute filtering is limited to status, species, and gender**

The hybrid filter handles attribute-list queries over the three indexed fields. Queries over other fields (e.g. "all characters from Earth C-137") or combining multiple non-indexed attributes still fall back to semantic search and may return partial results.

Fix: index additional fields as filterable metadata and extend the attribute detector.

**Persona reduces measured faithfulness**

The Oracle persona trades ~0.35 faithfulness for personality (see Evaluation). The lost points are stylistic, not factual.

Fix: constrain the persona so tone comes from word choice rather than invented asides, recovering faithfulness toward 0.90+ while keeping character.

---

## What I Would Improve With More Time

| Priority | Improvement | Why It Matters for This Project |
|----------|-------------|--------------------------------|
| High | **Query rewriting with HyDE** — generate a hypothetical answer first, use it to search | Fixes paraphrased queries — the hypothetical document contains the right vocabulary for retrieval |
| High | **Cross-encoder re-ranker** — re-rank top-20 cosine results before passing top-5 to Claude | Would push Context Precision from 0.85 toward 0.95+ — directly measurable with the existing RAGAS evaluation |
| High | **Redis response caching** — cache answers to common queries by question hash | The Rick & Morty universe is finite — "Who is Rick Sanchez?" is asked repeatedly. A cache hit returns in <10ms at zero API cost |
| Medium | **Tiered evaluation in CI** — fast deterministic smoke set per PR, full RAGAS suite nightly via the Batches API, gated on a regression threshold | A full LLM-judge suite is too slow to block every push; this is how RAG eval scales to a daily-deploy workflow |
| Medium | **Conversation history persistence** — store chat history in PostgreSQL | History currently lives in browser memory and is lost on refresh. A database enables cross-session continuity and analytics |
| Medium | **Summarised context window** — keep the last 5 full Q&A pairs verbatim, summarise older turns | The current sliding window (`history[-12:]`) drops older context entirely. Summarisation preserves long-term context while controlling token cost |
| Medium | **Close the feedback loop** — use `feedback.jsonl` signals to identify and fix weak queries | 👍/👎 data is collected but not yet acted on. Analysing low-rated queries reveals specific retrieval and prompt failures |
| Medium | **Observability with Langfuse** — trace every query through retrieval → prompt → response | When a query returns a bad answer there is currently no visibility into whether retrieval, context injection, or the LLM caused it |
| Medium | **Episode transcript ingestion** — add full episode text to the knowledge base | Enables relationship queries like "Rick's best friend" — the API never states relationships but transcripts do |
| Low | **Nightly data refresh** — scheduled job to pull new API data and rebuild the index | Keeps the knowledge base current if the Rick & Morty API adds new characters or episodes |