# Deep Research Agent

A fully autonomous, multi-source research agent that generates publication-quality reports on any topic. Built on LangGraph for stateful orchestration, it combines five adaptive search providers, a three-tier LLM hierarchy, and multi-format output compilation into a single optimised end-to-end pipeline. A React frontend streams real-time progress via Server-Sent Events and provides follow-up chat over the generated report.

![Deep Research Agent Overview](assets/img1.png)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Pipeline Walkthrough](#pipeline-walkthrough)
3. [Performance Optimisations](#performance-optimisations)
4. [Project Structure](#project-structure)
5. [Backend Modules](#backend-modules)
6. [Frontend](#frontend)
7. [LLM Model Hierarchy](#llm-model-hierarchy)
8. [Search Providers](#search-providers)
9. [Caching](#caching)
10. [Follow-up Chat (RAG)](#follow-up-chat-rag)
11. [Output Formats](#output-formats)
12. [Cost Tracking](#cost-tracking)
13. [Observability (LangSmith)](#observability-langsmith)
14. [Test Suite](#test-suite)
15. [Setup and Installation](#setup-and-installation)
16. [Environment Variables](#environment-variables)
17. [Running the Application](#running-the-application)
18. [API Endpoints](#api-endpoints)
19. [Technologies Used](#technologies-used)
20. [Deployment Guide](#deployment-guide)

---

## Architecture Overview

### Main Reporter Agent

```
START
  |
  v
query_analyzer_hyde          ← Fused query analysis + HyDE anchor + cache check
  |                            Pre-computes HyDE embedding (reused by all sections)
  |--- [cache hit] ──────────> output_compiler ──> END
  |
  |--- [cache miss]
  v
generate_report_plan         ← All 3 planning queries run in PARALLEL
  |
  |  Send() fan-out (one per section)
  v
section_builder_with_web_search  (parallel, N sections simultaneously)
  |
  v
aggregator_deduplicator
  |
  v
final_synthesis_writer       ← Single premium LLM call (Claude Sonnet)
  |
  v
output_compiler              ← PDF in thread pool, ChromaDB in background
  |
  v
END
```

### Section Builder Subagent (per section, all run in parallel)

```
START
  |
  v
query_rewriter_expander      ← Generates diverse multi-angle search queries
  |
  v
multi_source_search          ← Adaptive routing: selects providers per query
  |
  v
result_merger_ranker         ← Dedup + semantic ranking (reuses global HyDE embedding)
  |
  v
write_section                ← Mid-tier LLM drafts the section (250–300 words)
  |
  v
END
```

---

## Pipeline Walkthrough

![LangGraph Pipeline](assets/img2.png)

The pipeline is defined in `backend/app/graph.py` and consists of a main reporter agent and a nested section builder subagent.

### Stage 1 — Query Analysis & Cache Check (`query_analyzer_hyde`)

The entry point of every run:

1. Embeds the incoming topic and checks Redis for a semantically similar previous result (cosine similarity ≥ 0.90).
2. If **cache hit**: short-circuits to `output_compiler` — report returned in seconds.
3. If **cache miss**: uses the mid-tier LLM to perform fused query analysis + HyDE (Hypothetical Document Embedding) generation in a single structured call. The HyDE is a 200–300 word "ideal answer" that serves as a dense search anchor.
4. **Pre-computes the HyDE embedding vector** once and stores it in state so every section can reuse it without extra API calls.

### Stage 2 — Report Planning (`generate_report_plan`)

Uses the cheap LLM to generate 3 planning queries, then fires **all 3 in parallel** against Tavily + Serper simultaneously. The merged results are ranked and fed to a second cheap LLM call that plans the full section list (5–6 sections for `deep`, 3–4 for `quick`).

### Stage 3 — Parallel Section Building (`section_builder_with_web_search`)

All research sections are built **simultaneously** via LangGraph's `Send()` fan-out. Each section subagent runs four nodes:

- **`query_rewriter_expander`**: Generates 1–2 diverse search queries (factual, conceptual, practical, comparative, recent angles) using the HyDE document as context.
- **`multi_source_search`**: Routes each query to the most relevant providers (Tavily, Wikipedia, ArXiv, NewsAPI) using an LLM router. Results are capped at 30 per section to prevent memory bloat.
- **`result_merger_ranker`**: Deduplicates by URL, scores by credibility + recency + semantic relevance (using the **pre-computed global HyDE embedding** — no redundant API call), and returns the top-10 ranked sources.
- **`write_section`**: Mid-tier LLM (Claude Haiku) drafts a focused 250–300 word section from the ranked context.

### Stage 4 — Aggregation (`aggregator_deduplicator`)

Collects all completed sections, deduplicates sources across sections by URL, and formats combined content for the synthesis writer.

### Stage 5 — Final Synthesis (`final_synthesis_writer`)

The **one premium LLM call** per run. Claude Sonnet receives all research sections and synthesises:

- Executive Summary (3–5 bullet takeaways)
- Introduction (~100 words)
- All research sections with smooth transitions
- Conclusion (~150 words) with a summary table/list
- Full consolidated Sources section with clickable links

### Stage 6 — Output Compilation (`output_compiler`)

Compiles the final report into all formats, with two key async optimisations:

- **PDF generation** runs in a thread pool (`asyncio.to_thread`) — non-blocking.
- **ChromaDB embedding** runs as a background `asyncio.create_task` — the user receives the report instantly while ChromaDB indexes in the background.

---

## Performance Optimisations

The pipeline has been tuned to reduce end-to-end latency from ~5–7 minutes to ~2–3 minutes without any degradation in report quality.

| Optimisation                                                                                                                                                                                                           | Files Changed                       | Latency Saved |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- | ------------- |
| **All LLM calls switched to `ainvoke`** — 4 blocking `.invoke()` calls replaced with proper async `await .ainvoke()`, unblocking the event loop                                                                        | `nodes.py`                          | ~8–15s        |
| **Parallel planning search** — all 3 planning queries now fire simultaneously via `asyncio.gather` instead of sequentially                                                                                             | `nodes.py`                          | ~8–10s        |
| **Tavily basic depth + no raw content** — switched from `advanced` to `basic` search depth and disabled `include_raw_content`. Cuts per-call latency ~50–70% and dramatically reduces peak memory (OOM fix for Vercel) | `tavily_search.py`                  | ~4–6s         |
| **Single global HyDE embedding** — pre-computed once in `query_analyzer_hyde`, stored in `ReportState`, passed to all section subagents via `SectionState`. Eliminates N redundant `embed_text` API calls              | `nodes.py`, `state.py`, `merger.py` | ~4s           |
| **Background ChromaDB indexing** — ChromaDB embedding runs as `asyncio.create_task` (fire-and-forget), decoupled from the SSE response                                                                                 | `output_compiler.py`                | ~3–4s         |
| **Non-blocking PDF rendering** — WeasyPrint wrapped in `asyncio.to_thread`; Google Fonts HTTP import removed (was making a live network call per render)                                                               | `output_compiler.py`                | ~2–4s         |

### Memory Safety (Vercel / Render)

- Tavily `include_raw_content=False` eliminates the largest source of per-request memory growth.
- `MAX_RESULTS_PER_SECTION = 30` cap enforced in `multi_source_search`.
- `del all_results` after conversion to dicts in search nodes.
- `gc.collect()` called after each research task in production.
- Concurrency semaphore: `asyncio.Semaphore(2)` in `main.py`.

---

## Project Structure

```
deep_research_agent/
|
|-- backend/
|   |-- app/
|   |   |-- __init__.py
|   |   |-- main.py               # FastAPI app, SSE streaming, API endpoints
|   |   |-- graph.py              # LangGraph orchestration (main + subagent)
|   |   |-- nodes.py              # All graph node implementations
|   |   |-- state.py              # Pydantic models and TypedDict schemas
|   |   |-- prompts.py            # LLM prompt templates
|   |   |-- models.py             # 3-tier LLM factory (cheap/mid/premium)
|   |   |-- sse.py                # SSE event manager for real-time streaming
|   |   |-- embeddings.py         # Embedding utility (embed_text / embed_texts)
|   |   |-- cost_tracker.py       # Per-call LLM cost tracking
|   |   |-- output_compiler.py    # Multi-format compiler (PDF/MD/JSON)
|   |   |-- utils.py              # Shared utilities
|   |   |-- search/
|   |   |   |-- __init__.py
|   |   |   |-- tavily_search.py  # Tavily web search (basic depth)
|   |   |   |-- serper_search.py  # Serper Google search
|   |   |   |-- arxiv_search.py   # ArXiv academic papers
|   |   |   |-- wikipedia_search.py # Wikipedia articles
|   |   |   |-- news_search.py    # NewsAPI recent articles
|   |   |   |-- merger.py         # Result dedup + credibility ranking
|   |   |-- cache/
|   |   |   |-- __init__.py
|   |   |   |-- redis_cache.py    # Upstash Redis semantic cache (no TTL)
|   |   |-- chat/
|   |       |-- __init__.py
|   |       |-- followup.py       # ChromaDB RAG for follow-up Q&A
|   |-- tests/
|   |   |-- __init__.py
|   |   |-- conftest.py           # Shared fixtures
|   |   |-- test_models.py
|   |   |-- test_search_providers.py
|   |   |-- test_merger.py
|   |   |-- test_cache.py
|   |   |-- test_cost_tracker.py
|   |   |-- test_graph.py
|   |-- test_api_keys.py          # Script to selectively test API keys
|   |-- requirements.txt          # Python dependencies
|   |-- outputs/                  # Generated reports (.md, .pdf, .json)
|
|-- frontend/
|   |-- src/
|   |   |-- App.jsx               # Main React component
|   |   |-- App.css               # Full application styles
|   |   |-- main.jsx              # Vite entry point
|   |   |-- index.css             # Global styles
|   |-- index.html                # Frontend HTML template
|   |-- package.json              # Node dependencies
|   |-- vite.config.js            # Vite bundler configuration
|
|-- .env                          # Local environment variables
|-- .env.example                  # Environment variable template
|-- .gitignore
|-- run_app.sh                    # Test + launch script
|-- langgraph.json                # LangGraph Studio config
|-- pyproject.toml                # Project metadata
|-- render.yaml                   # Render deployment config
```

---

## Backend Modules

### `main.py` — FastAPI Application

The central entry point. Defines:

- `POST /api/research` — Accepts a `ResearchRequest` (topic, depth, output_format) and returns an SSE stream. Internally invokes `reporter_agent.astream()` and maps each LangGraph node completion to a typed SSE event. When the graph finishes, emits a `REPORT_READY` event with the Markdown content, PDF URL, JSON data, suggestion chips, source count, runtime, and estimated cost.
- `POST /api/chat/{report_id}` — Follow-up question endpoint. Retrieves relevant chunks from ChromaDB and answers using Claude Haiku.
- `GET /api/reports/{report_id}/json` — Structured JSON report.
- `GET /api/reports/{report_id}/markdown` — Raw Markdown content.
- `GET /api/reports/{filename}` — Serve any file from the outputs directory.

**Dynamic Suggestion Chips**: After report generation, the cheap LLM generates 10 focused follow-up questions from the first 3,000 characters of the report using a `RequestQuestions` structured output schema. These are cached in Redis. Each time the chat panel opens, 3 are randomly sampled and shown as suggestion chips.

A concurrency semaphore (`asyncio.Semaphore(2)`) prevents resource exhaustion under concurrent load.

### `graph.py` — LangGraph Definition

Defines two compiled graphs:

1. **`create_section_builder_subagent()`** — A `StateGraph` over `SectionState` with four nodes: `query_rewriter_expander → multi_source_search → result_merger_ranker → write_section`. Linear flow, single pass per section, no loops.

2. **`create_reporter_agent()`** — The main `StateGraph` over `ReportState`. Nodes: `query_analyzer_hyde → generate_report_plan → [fan-out] section_builder_with_web_search → aggregator_deduplicator → final_synthesis_writer → output_compiler`. Uses `Send()` for parallel section execution.

### `nodes.py` — Node Functions

All nine graph node implementations:

- **`query_analyzer_hyde`** — Checks Redis cache, runs fused query analysis + HyDE generation (single `ainvoke`), pre-computes and stores the HyDE embedding vector in state.
- **`generate_report_plan`** — Generates planning queries (`ainvoke`), fires all 3 against Tavily + Serper **in parallel** via `asyncio.gather`, then generates the section list (`ainvoke`).
- **`query_rewriter_expander`** — Generates diverse search queries per section using HyDE context.
- **`multi_source_search`** — LLM-routed adaptive provider selection (`ainvoke`). Collects results capped at 30 per section.
- **`result_merger_ranker`** — Deduplication + credibility/recency/relevance ranking using the **pre-computed HyDE embedding** passed from state (skips redundant `embed_text` call).
- **`write_section`** — 250–300 word section draft via mid-tier LLM.
- **`parallelize_section_writing`** — Fan-out: creates a `Send()` per research section, forwarding `hyde_document`, `hyde_embedding`, `domain`, and `depth`.
- **`aggregator_deduplicator`** — Collects all completed sections, deduplicates sources by URL.
- **`final_synthesis_writer`** — Single premium LLM call. Synthesises executive summary, intro, all sections, conclusion, and sources.

### `state.py` — State Schemas

Key TypedDicts:

- **`ReportState`** — Main graph state. Includes `hyde_document`, `hyde_embedding` (pre-computed vector, `Optional[List[float]]`), `sections`, `completed_sections` (merge via `operator.add`), `sources`, `domain`, `cache_hit`, `output_metadata`.
- **`SectionState`** — Per-section subagent state. Includes `section`, `search_queries`, `source_str`, `search_results`, `hyde_document`, `hyde_embedding`, `domain`, `depth`.
- **`SectionOutputState`** — What the subagent returns: `completed_sections`, `sources`.

### `prompts.py` — Prompt Templates

| Prompt                                  | Used By                   | Purpose                               |
| --------------------------------------- | ------------------------- | ------------------------------------- |
| `DEFAULT_REPORT_STRUCTURE`              | Report planner            | Standard intro/body/conclusion layout |
| `REPORT_PLAN_QUERY_GENERATOR_PROMPT`    | `generate_report_plan`    | Planning search queries               |
| `REPORT_PLAN_SECTION_GENERATOR_PROMPT`  | `generate_report_plan`    | Section list planning                 |
| `REPORT_SECTION_QUERY_GENERATOR_PROMPT` | `query_rewriter_expander` | Per-section queries with HyDE context |
| `SECTION_WRITER_PROMPT`                 | `write_section`           | 250–300 word section drafting         |
| `QUERY_ANALYZER_AND_HYDE_PROMPT`        | `query_analyzer_hyde`     | Fused analysis + HyDE generation      |
| `SEARCH_ROUTER_PROMPT`                  | `multi_source_search`     | Provider routing per query            |
| `FINAL_SYNTHESIS_PROMPT`                | `final_synthesis_writer`  | Full report synthesis                 |

### `models.py` — LLM Factory

Three-tier singleton factory, all via OpenRouter:

| Getter              | Default Model     | Temperature | Used For                                       |
| ------------------- | ----------------- | ----------- | ---------------------------------------------- |
| `get_cheap_llm()`   | Gemini Flash 2.0  | 0           | Planning, routing, HyDE, query rewriting       |
| `get_mid_llm()`     | Claude Haiku 3.5  | 0.3         | Section writing, HyDE analysis, follow-up chat |
| `get_premium_llm()` | Claude Sonnet 3.5 | 0.6         | Final synthesis (one call per run)             |

All use OpenRouter's `middle-out` transform for automatic prompt compression.

### `embeddings.py` — Embedding Utility

Async text embedding via `text-embedding-3-small` (routed through OpenRouter):

- **`embed_text(text)`** — Single text embedding, run in thread pool via `asyncio.to_thread`.
- **`embed_texts(texts)`** — Batch embedding with max 20 texts per API call to prevent OOM.
- **`cosine_similarity(a, b)`** — NumPy-based cosine similarity used by both the merger and the cache.

### `output_compiler.py` — Multi-Format Compiler

The `OutputCompiler` class handles all post-pipeline output:

1. **Markdown** — Saved as `{topic}.md`.
2. **PDF** — WeasyPrint HTML→PDF, run in `asyncio.to_thread` (non-blocking). Uses system font stack (no live Google Fonts HTTP request).
3. **JSON** — Structured report with sections, sources, and metadata.
4. **ChromaDB** — Report chunks embedded as `asyncio.create_task` (fire-and-forget background task).
5. **Redis** — Full result cached for future semantic cache hits.
6. **LangSmith metadata** — Runtime, cost estimate, section/source counts.

### `cache/redis_cache.py` — Semantic Cache

Upstash Redis-backed semantic cache with **no TTL** (entries persist indefinitely):

- Uses `embed_text` to embed the incoming query.
- Compares against all cached query embeddings via cosine similarity.
- Threshold: **0.90** similarity required for a cache hit.
- Stale index entries (report missing but index present) are automatically cleaned up.
- All Redis ops use `decode_responses=True`; Upstash URLs auto-upgraded from `redis://` to `rediss://` for SSL.

### `chat/followup.py` — RAG Follow-up Chat

ChromaDB-backed retrieval for follow-up Q&A:

- **Embedding**: Uses `embed_texts` and `embed_text` from `embeddings.py` directly (custom embedding function, `embedding_function=None` in ChromaDB).
- **Indexing**: Report chunked by `##` headers, each chunk embedded and stored in a per-report ChromaDB collection (`report_{report_id}`).
- **Retrieval**: Follow-up question embedded via `embed_text`, queried against ChromaDB with `query_embeddings` for top-5 relevant chunks.
- **Generation**: Claude Haiku answers strictly from retrieved context.

### `cost_tracker.py` — Cost Tracking

Tracks token usage and estimated cost across all LLM calls:

| Tier    | Input (per 1K tokens) | Output (per 1K tokens) |
| ------- | --------------------- | ---------------------- |
| Cheap   | Free                  | Free                   |
| Mid     | $0.0008               | $0.004                 |
| Premium | $0.003                | $0.015                 |

Includes `estimate_run_cost(section_count)` for pre-run estimation and `to_langsmith_metadata()` for observability.

---

## Frontend

A single-page React application built with Vite.

### Search Interface

- Text input for the research topic.
- Depth selector (Quick / Deep).
- Output format preference (PDF + MD / PDF Only / Markdown Only).

### Real-Time Progress

SSE stream rendered as a timeline. Each node completion shows the event type, message, and timestamp. Active steps show a spinner.

### Report Viewer

- **Metadata Bar** — Runtime, source count, estimated cost.
- **Executive Summary Card** — Auto-extracted and rendered at the top.
- **Tabbed Viewer** — Rendered Markdown (`react-markdown` + `remark-gfm` + `rehype-highlight`), embedded PDF iframe, raw JSON.

### Follow-up Chat Panel

Slide-out chat panel. Messages go to `POST /api/chat/{report_id}`. Responses include cited source chunks. When first opened, displays **3 dynamic suggestion chips** randomly sampled from 10 LLM-generated questions cached in Redis.

### Key Frontend Dependencies

| Package            | Purpose                  |
| ------------------ | ------------------------ |
| `react` 19         | UI framework             |
| `react-markdown`   | Markdown rendering       |
| `remark-gfm`       | GitHub Flavored Markdown |
| `rehype-highlight` | Code syntax highlighting |
| `lucide-react`     | Icons                    |
| `axios`            | HTTP client              |

---

## LLM Model Hierarchy

| Tier    | Model             | Used For                                                                       | Calls Per Deep Run |
| ------- | ----------------- | ------------------------------------------------------------------------------ | ------------------ |
| Cheap   | Gemini Flash 2.0  | Query routing, HyDE analysis, report planning, query rewriting, search routing | ~14–16             |
| Mid     | Claude Haiku 3.5  | HyDE generation, section writing, follow-up chat                               | ~7–8               |
| Premium | Claude Sonnet 3.5 | Final synthesis                                                                | 1                  |

All models configured via environment variables through OpenRouter's unified API.

---

## Search Providers

Five providers, selected adaptively per query by the LLM router:

| Provider  | Module                | Source Type           | Depth Setting                       |
| --------- | --------------------- | --------------------- | ----------------------------------- |
| Tavily    | `tavily_search.py`    | General web, curated  | `basic` (fast, no raw HTML)         |
| Serper    | `serper_search.py`    | Google search results | Standard                            |
| ArXiv     | `arxiv_search.py`     | Academic papers       | Used only for scientific topics     |
| Wikipedia | `wikipedia_search.py` | Encyclopedic content  | Used for foundational concepts      |
| NewsAPI   | `news_search.py`      | Recent news (30 days) | Used only for current events topics |

The LLM search router (`SEARCH_ROUTER_PROMPT`) determines which providers to call for each query — avoiding unnecessary API calls and latency.

### Result Merger (`merger.py`)

After collection, `ResultMerger.merge_and_rank()`:

1. **Deduplicates** by URL.
2. **Embeds** document contents in batch (`embed_texts`). Uses **pre-computed HyDE embedding** when provided — skips one `embed_text` API call per section.
3. **Scores** each result: credibility (domain tier, 30%) + recency (30%) + semantic relevance to HyDE (40%).
4. **Corroboration bonus** — sources with high embedding similarity to multiple other sources score higher.
5. Returns **top-10** sorted by final score.

---

## Caching

### Redis Semantic Cache (`cache/redis_cache.py`)

- Topic embedding compared against all cached query embeddings in a Redis hash.
- Cosine similarity ≥ **0.90** → cache hit, full pipeline skipped.
- Cache entries have **no TTL** — results persist indefinitely (change `CACHE_TTL_SECONDS` in `redis_cache.py` to re-enable TTL if desired).
- Suggestion chips (10 questions per topic) also cached in Redis under the same key.
- Connection failures are handled gracefully — pipeline runs normally if Redis is unavailable.
- Upstash URLs auto-upgraded to SSL (`rediss://`).

---

## Follow-up Chat (RAG)

After report generation (ChromaDB embedding runs in background):

1. Report chunked by `##` headers → each chunk embedded with `embed_texts`.
2. Chunks stored in ChromaDB collection `report_{report_id}` with `embedding_function=None` (manual embeddings supplied).
3. On follow-up question: `embed_text(question)` → `collection.query(query_embeddings=[...])` → top-5 chunks retrieved.
4. Claude Haiku answers strictly from retrieved context + returns raw source chunks.

---

## Output Formats

| Format   | File           | Description                                           |
| -------- | -------------- | ----------------------------------------------------- |
| Markdown | `{topic}.md`   | Full report in raw Markdown                           |
| PDF      | `{topic}.pdf`  | Styled PDF via WeasyPrint (system fonts, thread pool) |
| JSON     | `{topic}.json` | Structured data: topic, sections, sources, metadata   |

All outputs saved to `backend/outputs/` and served via API.

---

## Cost Tracking

The `CostTracker` class tracks token usage and costs per LLM call. Provides aggregated summaries, per-tier breakdowns, and a static `estimate_run_cost(section_count)` for quick estimation. The estimated cost is included in the `REPORT_READY` SSE event and shown in the frontend metadata bar.

---

## Observability (LangSmith)

When `LANGCHAIN_TRACING_V2=true`, all LangGraph invocations are traced in LangSmith with custom metadata: `topic`, `depth`, version tags, and `cost_estimate_usd`.

---

## Test Suite

Tests live in `backend/tests/`:

| File                       | Tests | Coverage                                                         |
| -------------------------- | ----- | ---------------------------------------------------------------- |
| `test_models.py`           | 8     | Tier init, singleton behaviour, env var mapping                  |
| `test_search_providers.py` | 7     | All 5 providers with mocked APIs, error handling                 |
| `test_merger.py`           | 14    | Dedup, credibility/recency/relevance scoring, top-K ranking      |
| `test_cache.py`            | 11    | Cache hit/miss, stale entry cleanup, embed failures, store/close |
| `test_cost_tracker.py`     | 12    | Per-call tracking, summaries, LangSmith metadata, estimation     |
| `test_graph.py`            | 10    | Graph topology, node existence, aggregator, merger               |

Tests use `pytest` + `pytest-asyncio`. All external APIs are fully mocked — no network calls made during testing.

```bash
cd backend
python -m pytest tests/ -v
```

---

## Setup and Installation

### Prerequisites

- Python 3.11+
- Node.js 20+
- npm 9+
- Redis (optional — use [Upstash](https://upstash.com/) for free serverless Redis)

### Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend Setup

```bash
cd frontend
npm install
```

### Environment Configuration

```bash
cp .env.example .env
# Edit .env with your API keys
```

---

## Environment Variables

| Variable               | Required | Description                                                |
| ---------------------- | -------- | ---------------------------------------------------------- |
| `OPENROUTER_API_KEY`   | Yes      | OpenRouter API key for all LLM and embedding calls         |
| `TAVILY_API_KEY`       | Yes      | Tavily search API key                                      |
| `SERPER_API_KEY`       | No       | Serper Google search API key                               |
| `NEWSAPI_KEY`          | No       | NewsAPI key for recent news                                |
| `LANGSMITH_API_KEY`    | No       | LangSmith API key for observability                        |
| `LLM_MODEL_CHEAP`      | Yes      | Cheap tier model (e.g. `google/gemini-2.0-flash-exp:free`) |
| `LLM_MODEL_MID`        | Yes      | Mid tier model (e.g. `anthropic/claude-3.5-haiku`)         |
| `LLM_MODEL_PREMIUM`    | Yes      | Premium tier model (e.g. `anthropic/claude-3.5-sonnet`)    |
| `EMBEDDING_MODEL`      | No       | Embedding model (default: `text-embedding-3-small`)        |
| `REDIS_URL`            | No       | Redis/Upstash connection URL                               |
| `LANGCHAIN_TRACING_V2` | No       | Enable LangSmith tracing (`true`/`false`)                  |
| `LANGCHAIN_PROJECT`    | No       | LangSmith project name                                     |

---

## Running the Application

### One-Command Launch

```bash
chmod +x run_app.sh
./run_app.sh
```

This will:

1. Run the full pytest suite. If any test fails, the script aborts.
2. Start the FastAPI backend on port 8000 with hot-reload.
3. Start the Vite dev server on port 5173.

### Manual Launch

```bash
# Terminal 1 — Backend
cd backend
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Frontend: `http://localhost:5173` | Backend API: `http://localhost:8000`

---

## API Endpoints

| Method | Path                                | Description                             |
| ------ | ----------------------------------- | --------------------------------------- |
| `POST` | `/api/research`                     | Start a research session (SSE stream)   |
| `POST` | `/api/chat/{report_id}`             | Ask a follow-up question about a report |
| `GET`  | `/api/reports/{report_id}/json`     | Structured JSON report                  |
| `GET`  | `/api/reports/{report_id}/markdown` | Raw Markdown                            |
| `GET`  | `/api/reports/{filename}`           | Serve any file from outputs directory   |
| `GET`  | `/health`                           | Health check                            |

### Research Request Body

```json
{
  "topic": "Vector Databases",
  "depth": "deep",
  "output_format": "both"
}
```

- `depth`: `"quick"` (3–4 sections) or `"deep"` (5–6 sections)
- `output_format`: `"pdf"`, `"markdown"`, or `"both"`

### SSE Event Types

| Event Type            | Emitted By                | Description                        |
| --------------------- | ------------------------- | ---------------------------------- |
| `query_analyzing`     | `query_analyzer_hyde`     | Query analysis + HyDE generation   |
| `plan_generated`      | `generate_report_plan`    | Section plan ready                 |
| `section_researching` | Section builder nodes     | Search / merge / write in progress |
| `section_complete`    | `aggregator_deduplicator` | A section finished                 |
| `synthesis_writing`   | `final_synthesis_writer`  | Premium LLM synthesising           |
| `compiling_output`    | `output_compiler`         | Generating PDF, MD, JSON           |
| `report_ready`        | Final event               | Complete report with all data      |
| `error`               | Any node                  | Error during processing            |

### `report_ready` Event Payload

```json
{
  "type": "report_ready",
  "message": "Report ready!",
  "data": {
    "report_id": "unique-id",
    "content": "Full Markdown report...",
    "markdown_url": "/api/reports/{id}/markdown",
    "pdf_filename": "Topic.pdf",
    "pdf_url": "/api/reports/Topic.pdf",
    "json_url": "/api/reports/{id}/json",
    "json_report": { "sections": [], "sources": [] },
    "chat_enabled": true,
    "suggestion_chips": ["Question 1?", "Question 2?", "Question 3?"],
    "source_count": 42,
    "runtime_seconds": 130.5,
    "cost_estimate_usd": 0.023
  }
}
```

---

## Technologies Used

### Backend

| Technology              | Purpose                                            |
| ----------------------- | -------------------------------------------------- |
| Python 3.11+            | Runtime                                            |
| FastAPI                 | HTTP API framework + SSE streaming                 |
| LangGraph               | Stateful agent orchestration with parallel fan-out |
| LangChain               | LLM abstraction layer                              |
| OpenRouter              | Unified LLM API gateway                            |
| WeasyPrint              | HTML→PDF conversion (thread pool)                  |
| ChromaDB                | Vector store for follow-up chat RAG                |
| Upstash Redis           | Serverless semantic cache (no TTL)                 |
| LangSmith               | Observability and tracing                          |
| pytest + pytest-asyncio | Test framework                                     |

### Frontend

| Technology       | Purpose                   |
| ---------------- | ------------------------- |
| React 19         | UI framework              |
| Vite 7           | Build tool and dev server |
| react-markdown   | Markdown rendering        |
| remark-gfm       | GitHub Flavored Markdown  |
| rehype-highlight | Code syntax highlighting  |
| lucide-react     | Icons                     |

### Search APIs

| Provider  | Access           |
| --------- | ---------------- |
| Tavily    | API key required |
| Serper    | API key required |
| ArXiv     | Free, no key     |
| Wikipedia | Free, no key     |
| NewsAPI   | API key required |

---

## Deployment Guide

Deploy for **free** using Upstash (Redis), Render (Backend), and Vercel (Frontend).

### Step 1 — Deploy Semantic Cache (Upstash Redis)

1. Sign up at [Upstash](https://upstash.com/).
2. Create a new **Redis Database** (Serverless, Free tier).
3. Copy the **Redis URL** (format: `rediss://default:password@endpoint:port`).

> The backend automatically upgrades `redis://` URLs from Upstash to `rediss://` for SSL.

### Step 2 — Deploy Backend (Render)

1. Push your code to GitHub.
2. Sign in to [Render](https://render.com/) → **New Web Service** → connect your repo.
3. Configure:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port 10000`
4. Add all environment variables from your `.env` file (especially `OPENROUTER_API_KEY`, `TAVILY_API_KEY`, `REDIS_URL`).
5. Click **Deploy**. Copy your Render backend URL once live.

### Step 3 — Deploy Frontend (Vercel)

1. Sign in to [Vercel](https://vercel.com/) → **Add New Project** → import your repo.
2. Set **Root Directory** to `frontend`.
3. Add environment variable:
   - `VITE_API_URL` = your Render backend URL (no trailing slash)
4. Click **Deploy**.

Once Vercel finishes, your Deep Research Agent is live at the provided URL.

> **Note**: WeasyPrint PDF generation requires filesystem write access and binary dependencies. If you ever move the backend to Vercel Serverless Functions (vs. Render), PDF generation will not work — return Markdown only in that case.
