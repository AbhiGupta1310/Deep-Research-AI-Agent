# Deep Research Agent

A fully autonomous, multi-source research agent that generates publication-quality reports on any topic. Built on LangGraph for stateful orchestration, it combines five search providers, a three-tier LLM hierarchy, iterative self-critique, fact-checking, and multi-format output compilation into a single end-to-end pipeline. A React frontend streams real-time progress via Server-Sent Events and provides follow-up chat over the generated report.

![Deep Research Agent Overview](assets/img1.png)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Pipeline Walkthrough](#pipeline-walkthrough)
3. [Project Structure](#project-structure)
4. [Backend Modules](#backend-modules)
5. [Frontend](#frontend)
6. [LLM Model Hierarchy](#llm-model-hierarchy)
7. [Search Providers](#search-providers)
8. [Caching](#caching)
9. [Follow-up Chat (RAG)](#follow-up-chat-rag)
10. [Output Formats](#output-formats)
11. [Cost Tracking](#cost-tracking)
12. [Observability (LangSmith)](#observability-langsmith)
13. [Test Suite](#test-suite)
14. [Setup and Installation](#setup-and-installation)
15. [Environment Variables](#environment-variables)
16. [Running the Application](#running-the-application)
17. [API Endpoints](#api-endpoints)
18. [Technologies Used](#technologies-used)
19. [Deployment Guide](#deployment-guide)

---

## Architecture Overview

### Main Reporter Agent

```
START
  |
  v
query_analyzer_hyde
  |
  |--- [cache hit] ---> output_compiler ---> END
  |
  |--- [cache miss]
  v
generate_report_plan
  |
  |  Send() fan-out (one per section)
  v
section_builder_with_web_search  (parallel, N sections)
  |
  v
aggregator_deduplicator
  |
  v
fact_checker
  |
  v
final_synthesis_writer   (single premium LLM call)
  |
  v
output_compiler
  |
  v
END
```

---

## Pipeline Walkthrough

![LangGraph Pipeline](assets/img2.png)

The LangGraph pipeline is defined in `backend/app/graph.py` and consists of a main reporter agent and a nested section builder subagent. The full execution flow is:

### Main Reporter Agent

```
START
  |
  v
query_analyzer_hyde
  |
  |--- [cache hit] ---> output_compiler ---> END
  |
  |--- [cache miss]
  v
generate_report_plan
  |
  |  Send() fan-out (one per section)
  v
section_builder_with_web_search  (parallel, N sections)
  |
  v
aggregator_deduplicator
  |
  v
fact_checker
  |
  v
final_synthesis_writer   (single premium LLM call)
  |
  v
output_compiler
  |
  v
END
```

### Section Builder Subagent (per section)

Each section runs through an internal reflection loop:

```
START
  |
  v
query_rewriter_expander
  |
  v
multi_source_search
  |
  v
result_merger_ranker
  |
  v
write_section
  |
  v
critic_agent
  |
  |--- [gaps found AND loop count < 3] ---> query_rewriter_expander
  |
  |--- [approved OR loop count == 3] ---> END
```

The critic agent can loop back to the query rewriter up to three times. Each loop rewrites the search queries based on identified knowledge gaps, searches again, merges new results, and re-drafts the section.

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
|   |   |-- embeddings.py         # OpenAI embedding utility + similarity check
|   |   |-- cost_tracker.py       # Per-call LLM cost tracking
|   |   |-- output_compiler.py    # Multi-format compiler (PDF/MD/JSON)
|   |   |-- utils.py              # Shared utilities
|   |   |-- search/
|   |   |   |-- __init__.py
|   |   |   |-- tavily_search.py  # Tavily deep web search
|   |   |   |-- serper_search.py  # Serper Google search
|   |   |   |-- arxiv_search.py   # ArXiv academic papers
|   |   |   |-- wikipedia_search.py # Wikipedia articles
|   |   |   |-- news_search.py    # NewsAPI recent articles
|   |   |   |-- merger.py         # Result deduplication + credibility ranking
|   |   |-- cache/
|   |   |   |-- __init__.py
|   |   |   |-- redis_cache.py    # Redis semantic cache
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
|   |   |-- test_llm_ids.py       # LLM fallback and tracking tests
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
|   |-- eslint.config.js          # ESLint configuration
|
|-- .env                          # Local environment variables
|-- .env.example                  # Environment variable template
|-- .gitignore                    # Tracking exclusions
|-- run_app.sh                    # Test + launch script
|-- langgraph.json                # LangGraph Studio config
|-- pyproject.toml                # Project metadata
```

---

## Backend Modules

### `main.py` -- FastAPI Application

The central entry point. Defines:

- `POST /api/research` -- Accepts a `ResearchRequest` (topic, depth, output_format) and returns an SSE stream. Internally, it invokes `reporter_agent.astream()` and maps each LangGraph node completion to a typed SSE event. When the graph finishes, it emits a `REPORT_READY` event containing the Markdown content, PDF download URL, JSON report data, confidence scores, source count, runtime, and estimated cost.
- `POST /api/chat/{report_id}` -- Accepts a follow-up question and returns an answer with cited source chunks using ChromaDB retrieval.
- `GET /api/reports/{report_id}/pdf` -- Serves the generated PDF file.
- `GET /api/reports/{report_id}/json` -- Returns the structured JSON report.
- `GET /api/reports/{report_id}/markdown` -- Returns the raw Markdown content.

A semaphore limits concurrent research requests to prevent resource exhaustion.

### `graph.py` -- LangGraph Definition

Defines two compiled graphs:

1. **`create_section_builder_subagent()`** -- A `StateGraph` over `SectionState` with five nodes: `query_rewriter_expander`, `multi_source_search`, `result_merger_ranker`, `write_section`, and `critic_agent`. A conditional edge from `critic_agent` either loops back (up to 3 times) or terminates.

2. **`create_reporter_agent()`** -- The main `StateGraph` over `ReportState`. Seven nodes: `query_analyzer_hyde`, `generate_report_plan`, the compiled section builder subagent, `aggregator_deduplicator`, `fact_checker`, `final_synthesis_writer`, and `output_compiler`. Uses `Send()` for parallel fan-out of the section builder across all research sections.

### `nodes.py` -- Node Functions

Contains all the graph node implementations:

- **`query_analyzer_hyde`** -- Analyzes the user query, checks the Redis semantic cache, and generates a HyDE (Hypothetical Document Embedding) anchor document. If a cache hit is found (cosine similarity > 0.92), the pipeline short-circuits directly to the output compiler.
- **`generate_report_plan`** -- Uses the cheap LLM to generate search queries for planning, runs them through Tavily and Serper, then generates a structured list of report sections with names, descriptions, and research flags.
- **`query_rewriter_expander`** -- Generates diverse search queries for a given section using the HyDE document as context. Produces queries across multiple angles: factual, conceptual, practical, comparative, and recent.
- **`multi_source_search`** -- Fans out each query to all five search providers in parallel using `asyncio.gather`. Collects raw results without ranking.
- **`result_merger_ranker`** -- Takes raw search results and runs them through the `ResultMerger` for deduplication and credibility-based ranking. Returns the top-k results formatted as source context for the writer.
- **`write_section`** -- Uses the mid-tier LLM (Claude Haiku) to draft a section based on the ranked source context. Enforces a 150-200 word limit per section.
- **`critic_agent`** -- Uses the cheap LLM (Gemini Flash) to evaluate the draft on knowledge gaps, unsupported claims, outdated data, and source contradictions. Returns a confidence score and whether gaps were found.
- **`should_reflect`** -- Conditional edge function. Routes back to `query_rewriter_expander` if gaps are found and the loop count is under 3, otherwise approves the section.
- **`parallelize_section_writing`** -- Fan-out function that creates a `Send()` message for each research section, enabling parallel execution of the section builder subagent.
- **`aggregator_deduplicator`** -- Replaces the old `format_completed_sections`. Aggregates all completed sections, deduplicates cross-section sources by URL, and formats the combined content for the synthesis writer.
- **`fact_checker`** -- Cross-references claims across all completed sections. Flags claims with single-source support, identifies contradictions, and produces per-section confidence scores.
- **`final_synthesis_writer`** -- The single premium LLM call (Claude Sonnet). Receives all research sections, confidence scores, and fact-check flags. Writes the executive summary, introduction, conclusion, and smooths transitions between sections to produce a cohesive final report.

### `state.py` -- State Schemas

Defines the data structures that flow through the graph:

- `Section` -- A Pydantic model for a single report section (name, description, research flag, content, key questions, search angle, priority).
- `Sections` -- Wrapper for structured LLM output containing a list of sections.
- `SearchQuery` / `Queries` -- Pydantic models for structured search query generation.
- `CriticFeedback` -- Structured output from the critic agent (gaps_found, confidence_score, knowledge_gaps, unsupported_claims, suggested_queries).
- `SectionState` -- TypedDict for the section builder subagent (section, search_queries, source_str, search_results, reflection_count, hyde_document, critic_feedback, etc.).
- `SectionOutputState` -- TypedDict defining what the section builder returns to the parent graph.
- `ReportState` -- TypedDict for the main reporter agent. Uses `Annotated[list, operator.add]` for merge-friendly fields like `completed_sections`.
- `ReportStateInput` / `ReportStateOutput` -- Input and output schemas for the top-level graph.

### `prompts.py` -- Prompt Templates

Contains all system prompts used throughout the pipeline:

| Prompt                                  | Used By                   | Purpose                                                      |
| --------------------------------------- | ------------------------- | ------------------------------------------------------------ |
| `DEFAULT_REPORT_STRUCTURE`              | Report planner            | Defines the standard report layout (intro, body, conclusion) |
| `REPORT_PLAN_QUERY_GENERATOR_PROMPT`    | `generate_report_plan`    | Generates search queries for initial planning                |
| `REPORT_PLAN_SECTION_GENERATOR_PROMPT`  | `generate_report_plan`    | Plans report sections based on search context                |
| `REPORT_SECTION_QUERY_GENERATOR_PROMPT` | `query_rewriter_expander` | Generates per-section queries with HyDE context              |
| `SECTION_WRITER_PROMPT`                 | `write_section`           | Guides section drafting with strict formatting rules         |
| `FINAL_SECTION_WRITER_PROMPT`           | (legacy)                  | Template for intro/conclusion writing                        |
| `CRITIC_AGENT_PROMPT`                   | `critic_agent`            | Evaluates sections for gaps and issues                       |
| `QUERY_ANALYZER_PROMPT`                 | `query_analyzer_hyde`     | Analyzes user query intent and scope                         |
| `HYDE_GENERATOR_PROMPT`                 | `query_analyzer_hyde`     | Generates the hypothetical ideal answer                      |
| `FACT_CHECKER_PROMPT`                   | `fact_checker`            | Cross-references claims and flags issues                     |
| `FINAL_SYNTHESIS_PROMPT`                | `final_synthesis_writer`  | Instructs the premium LLM to synthesize the full report      |

### `models.py` -- LLM Factory

Provides a three-tier singleton factory for LLM instances, all routed through OpenRouter:

- `get_cheap_llm()` -- Returns the cheap tier (Gemini Flash 2.0)
- `get_mid_llm()` -- Returns the mid tier (Claude Haiku 3.5)
- `get_premium_llm()` -- Returns the premium tier (Claude Sonnet 3.5)

Each returns a `ChatOpenAI` instance configured with the appropriate model name from environment variables, OpenRouter base URL, and custom headers.

### `sse.py` -- Server-Sent Events Manager

Manages real-time progress streaming. Each research session gets its own `SSEManager` instance backed by an `asyncio.Queue`. Defines the `EventTypes` enum with all event categories: `QUERY_ANALYZING`, `PLAN_GENERATED`, `SECTION_RESEARCHING`, `SECTION_COMPLETE`, `FACT_CHECKING`, `SYNTHESIS_WRITING`, `COMPILING_OUTPUT`, `REPORT_READY`, and `ERROR`.

### `embeddings.py` -- Embedding Utility

Provides async text embedding via OpenAI's `text-embedding-3-small` model (routed through OpenRouter). Includes a `cosine_similarity` function using NumPy for comparing embedding vectors. Used by the Redis semantic cache and for HyDE-based relevance scoring.

### `output_compiler.py` -- Multi-Format Compiler

The `OutputCompiler` class handles all post-pipeline processing:

1. Saves the report as Markdown (`.md`).
2. Converts to PDF using WeasyPrint (`.pdf`).
3. Generates structured JSON with metadata (`.json`).
4. Embeds report chunks into ChromaDB for follow-up chat.
5. Caches the result in Redis for future similar queries.
6. Writes LangSmith metadata for observability.

The `output_compiler_node` function wraps this as a LangGraph node.

### `cost_tracker.py` -- Cost Tracking

Tracks per-call LLM costs based on a model pricing table:

| Tier    | Input (per 1K tokens) | Output (per 1K tokens) |
| ------- | --------------------- | ---------------------- |
| Cheap   | Free                  | Free                   |
| Mid     | \$0.0008              | \$0.004                |
| Premium | \$0.003               | \$0.015                |

Provides aggregated summaries, per-tier breakdowns, and a `to_langsmith_metadata()` method for observability integration. Includes a static `estimate_run_cost()` method for quick cost estimation based on section count.

---

## Frontend

The frontend is a single-page React application built with Vite. It provides:

### Search Interface

- A text input for the research topic.
- A depth selector (Quick / Deep) that controls the number of search queries and reflection loops.
- An output format preference (PDF + MD / PDF Only / Markdown Only).

### Real-Time Progress

Connects to the SSE stream and renders a timeline of progress steps. Each step shows the node type, a descriptive message, and a timestamp. Active steps show a spinner.

### Report Viewer

After report completion, displays:

- **Metadata Bar** -- Runtime, source count, average confidence score, and estimated cost.
- **Executive Summary Card** -- Auto-extracted from the report content and rendered prominently at the top.
- **Tabbed Viewer** -- Three tabs:
  - Rendered Markdown (using `react-markdown` with `remark-gfm` for tables/strikethrough and `rehype-highlight` for syntax highlighting).
  - PDF (embedded iframe).
  - Raw JSON (structured report data).

### Follow-up Chat Panel

A slide-out chat panel for asking questions about the generated report. Messages are sent to `POST /api/chat/{report_id}`, which retrieves relevant chunks from ChromaDB and answers using Claude Haiku. Assistant responses include cited source snippets. The empty state shows suggestion chips for common follow-up questions.

### Key Frontend Dependencies

| Package            | Purpose                                       |
| ------------------ | --------------------------------------------- |
| `react` 19         | UI framework                                  |
| `react-markdown`   | Markdown rendering                            |
| `remark-gfm`       | GitHub Flavored Markdown (tables, task lists) |
| `rehype-highlight` | Code syntax highlighting                      |
| `lucide-react`     | Icon library                                  |
| `axios`            | HTTP client                                   |

---

## LLM Model Hierarchy

The system uses a three-tier LLM strategy to balance quality against cost:

| Tier    | Model             | Used For                                                                                            | Calls Per Report |
| ------- | ----------------- | --------------------------------------------------------------------------------------------------- | ---------------- |
| Cheap   | Gemini Flash 2.0  | Query analysis, HyDE generation, report planning, query rewriting, critic evaluation, fact-checking | ~20-40           |
| Mid     | Claude Haiku 3.5  | Section writing, follow-up chat                                                                     | ~5-10            |
| Premium | Claude Sonnet 3.5 | Final synthesis (one call)                                                                          | 1                |

All models are accessed through OpenRouter, which provides a unified API across providers. The model names are configurable via environment variables, making it easy to swap models without code changes.

---

## Search Providers

Five providers run in parallel for every section query:

| Provider  | Module                | Source Type           | Typical Results |
| --------- | --------------------- | --------------------- | --------------- |
| Tavily    | `tavily_search.py`    | Deep web, curated     | 4 per query     |
| Serper    | `serper_search.py`    | Google search         | 4 per query     |
| ArXiv     | `arxiv_search.py`     | Academic papers       | 3 per query     |
| Wikipedia | `wikipedia_search.py` | Encyclopedic content  | 2 per query     |
| NewsAPI   | `news_search.py`      | Recent news (30 days) | 3 per query     |

All providers return a standardized dict with keys: `url`, `title`, `content`, `raw_content`, `domain`, `publish_date`, and `source_type`. This uniform format allows the `ResultMerger` to process results from any provider identically.

The pipeline uses **topic-aware adaptive search routing** to reduce unnecessary API calls and latency (e.g., automatically bypassing ArXiv for strictly non-academic topics based on the query analysis).

### Result Merger and Ranker (`merger.py`)

After collection, the `ResultMerger` class:

1. **Deduplicates** by URL -- removes duplicate results from different providers.
2. **Scores Credibility** -- rates domains on a tier system (academic/government = 0.9+, major publications = 0.8, generic = 0.5).
3. **Scores Recency** -- more recent content scores higher.
4. **Scores Relevance** -- keyword overlap with the HyDE document.
5. **Calculates Corroboration** -- sources covering similar topics boost each other.
6. **Computes Final Score** -- weighted combination (credibility 30%, relevance 40%, recency 15%, corroboration 15%).
7. **Returns Top-K** -- sorted by final score descending.

---

## Caching

### Redis Semantic Cache (`cache/redis_cache.py`)

Before running the full pipeline, the `query_analyzer_hyde` node checks if a semantically similar query has been run before:

1. The incoming query is embedded using `text-embedding-3-small`.
2. All cached query embeddings are retrieved from a Redis hash.
3. Cosine similarity is computed against each cached embedding.
4. If any similarity exceeds 0.92, the cached report is returned immediately, bypassing the entire pipeline.

Cache entries have a 24-hour TTL. Redis connection failures are handled gracefully -- the cache is simply skipped and the pipeline runs normally.

---

## Follow-up Chat (RAG)

After a report is generated, the `FollowupChatHandler` in `chat/followup.py`:

1. **Chunks** the report by `##` headers (with fallback to paragraph splitting).
2. **Embeds** each chunk into a ChromaDB collection named `report_{report_id}`.
3. When a user asks a follow-up question:
   - The question is used to query ChromaDB for the top-3 most relevant chunks.
   - The chunks are assembled as context for Claude Haiku.
   - The LLM answers strictly based on the retrieved context.
   - The raw source chunks are returned alongside the answer.

### Smart Suggestion Chips

When the chat panel is opened, the UI displays 3 dynamic suggestion chips. These chips are created by a cheap LLM analyzing the generated report. To optimize token usage and latency, the system caches the generated suggestion chips in the Redis Semantic Cache under the original research topic. Subsequent load of the same topic grabs these chips instantly without an LLM call.

---

## Output Formats

The `OutputCompiler` generates three output formats:

| Format   | File           | Description                                                            |
| -------- | -------------- | ---------------------------------------------------------------------- |
| Markdown | `{topic}.md`   | Raw Markdown with full report content                                  |
| PDF      | `{topic}.pdf`  | Styled PDF generated via WeasyPrint with custom CSS                    |
| JSON     | `{topic}.json` | Structured data: topic, sections, sources, confidence scores, metadata |

All outputs are saved to `backend/outputs/` and served via API endpoints.

---

## Cost Tracking

The `CostTracker` class in `cost_tracker.py` tracks token usage and costs across all LLM calls during a research session. It maintains a per-tier pricing table and provides:

- Per-call cost tracking with optional node name annotation.
- Aggregated summaries (total cost, tokens, calls by tier).
- A `to_langsmith_metadata()` method for attaching cost data to LangSmith traces.
- A static `estimate_run_cost(section_count)` method for pre-run estimation.

The estimated cost is included in the `REPORT_READY` SSE event and displayed in the frontend metadata bar.

---

## Observability (LangSmith)

When `LANGCHAIN_TRACING_V2=true` is set, all LangGraph invocations are traced in LangSmith. Custom metadata is attached to each run:

- `topic` -- the research topic
- `depth` -- quick or deep
- `tags` -- version and depth tags
- `cost_estimate_usd` -- estimated cost from the cost tracker

Traces can be viewed in the LangSmith dashboard under the project specified by `LANGCHAIN_PROJECT`.

---

## Test Suite

The test suite lives in `backend/tests/` with 61 tests across 6 files:

| File                       | Tests | Coverage                                                                  |
| -------------------------- | ----- | ------------------------------------------------------------------------- |
| `test_models.py`           | 8     | Tier initialization, singleton behavior, environment variable mapping     |
| `test_search_providers.py` | 7     | All 5 providers with mocked APIs, error handling                          |
| `test_merger.py`           | 14    | Deduplication, credibility/recency/relevance scoring, ranking, formatting |
| `test_cache.py`            | 10    | Cache hit/miss flow, store, close, embedding failures                     |
| `test_cost_tracker.py`     | 12    | Per-call tracking, summaries, LangSmith metadata, estimation              |
| `test_graph.py`            | 10    | Graph topology, node existence, aggregator dedup, merger ranker           |

Tests use `pytest` with `pytest-asyncio` for async node tests. External APIs are fully mocked -- no network calls are made during testing.

Run with:

```bash
cd backend
python -m pytest tests/ -v
```

---

## Setup and Installation

### Prerequisites

- Python 3.11 or higher
- Node.js 20 or higher
- npm 9 or higher
- Redis (optional, for semantic caching)

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

Copy the example environment file and fill in your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your keys (see the Environment Variables section below).

---

## Environment Variables

| Variable               | Required | Description                                                    |
| ---------------------- | -------- | -------------------------------------------------------------- |
| `OPENROUTER_API_KEY`   | Yes      | OpenRouter API key for all LLM calls                           |
| `TAVILY_API_KEY`       | Yes      | Tavily search API key                                          |
| `SERPER_API_KEY`       | No       | Serper Google search API key                                   |
| `NEWSAPI_KEY`          | No       | NewsAPI key for recent news                                    |
| `LANGSMITH_API_KEY`    | No       | LangSmith API key for observability                            |
| `LLM_MODEL_CHEAP`      | Yes      | Cheap tier model (default: `google/gemini-2.0-flash-exp:free`) |
| `LLM_MODEL_MID`        | Yes      | Mid tier model (default: `anthropic/claude-3.5-haiku`)         |
| `LLM_MODEL_PREMIUM`    | Yes      | Premium tier model (default: `anthropic/claude-3.5-sonnet`)    |
| `EMBEDDING_MODEL`      | No       | Embedding model (default: `text-embedding-3-small`)            |
| `REDIS_URL`            | No       | Redis connection URL (default: `redis://localhost:6379`)       |
| `LANGCHAIN_TRACING_V2` | No       | Enable LangSmith tracing (default: `true`)                     |
| `LANGCHAIN_PROJECT`    | No       | LangSmith project name                                         |

---

## Running the Application

### One-Command Launch

The `run_app.sh` script runs all backend tests first, then starts both servers:

```bash
chmod +x run_app.sh
./run_app.sh
```

This will:

1. Run the full pytest suite (61 tests). If any test fails, the script aborts.
2. Start the FastAPI backend on port 8000 with hot-reload.
3. Start the Vite dev server on port 5173.

### Manual Launch

Start each service separately:

```bash
# Terminal 1 -- Backend
cd backend
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 -- Frontend
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:5173` and the backend API at `http://localhost:8000`.

---

## API Endpoints

| Method | Path                                | Description                               |
| ------ | ----------------------------------- | ----------------------------------------- |
| `POST` | `/api/research`                     | Start a research session (SSE stream)     |
| `POST` | `/api/chat/{report_id}`             | Ask a follow-up question about a report   |
| `GET`  | `/api/reports/{report_id}/pdf`      | Download the PDF report                   |
| `GET`  | `/api/reports/{report_id}/json`     | Get the structured JSON report            |
| `GET`  | `/api/reports/{report_id}/markdown` | Get the raw Markdown                      |
| `GET`  | `/api/reports/{filename}`           | Serve any file from the outputs directory |

### Research Request Body

```json
{
  "topic": "Vector Databases",
  "depth": "deep",
  "output_format": "both"
}
```

- `depth`: `"quick"` or `"deep"` (controls query count and search intensity)
- `output_format`: `"pdf"`, `"markdown"`, or `"both"`

### SSE Event Types

| Event Type            | Emitted By               | Description                                |
| --------------------- | ------------------------ | ------------------------------------------ |
| `query_analyzing`     | `query_analyzer_hyde`    | Query analysis started                     |
| `plan_generated`      | `generate_report_plan`   | Report plan with section list              |
| `section_researching` | Section builder nodes    | Search, merge, write, critique in progress |
| `section_complete`    | `section_builder`        | A section finished all reflection loops    |
| `fact_checking`       | `fact_checker`           | Cross-referencing claims                   |
| `synthesis_writing`   | `final_synthesis_writer` | Premium LLM synthesizing final report      |
| `compiling_output`    | `output_compiler`        | Generating PDF, MD, JSON                   |
| `report_ready`        | (final event)            | Complete report with all data              |
| `error`               | (any node)               | Error occurred during processing           |

---

## Technologies Used

### Backend

| Technology | Version | Purpose                             |
| ---------- | ------- | ----------------------------------- |
| Python     | 3.11+   | Runtime                             |
| FastAPI    | 0.115+  | HTTP API framework                  |
| LangGraph  | 0.4+    | Stateful agent orchestration        |
| LangChain  | 0.3+    | LLM abstraction layer               |
| OpenRouter | --      | Unified LLM API gateway             |
| WeasyPrint | 68+     | HTML-to-PDF conversion              |
| ChromaDB   | 1.5+    | Vector store for follow-up chat RAG |
| Redis      | 7+      | Semantic cache backend              |
| LangSmith  | --      | Observability and tracing           |
| pytest     | 9+      | Test framework                      |

### Frontend

| Technology       | Version | Purpose                          |
| ---------------- | ------- | -------------------------------- |
| React            | 19      | UI framework                     |
| Vite             | 7       | Build tool and dev server        |
| react-markdown   | 10      | Markdown rendering               |
| remark-gfm       | 4       | GitHub Flavored Markdown support |
| rehype-highlight | 7       | Code syntax highlighting         |
| lucide-react     | 0.563   | Icon components                  |

### Search APIs

| Provider  | API                      | Access           |
| --------- | ------------------------ | ---------------- |
| Tavily    | Tavily Search API        | API key required |
| Serper    | Serper.dev Google API    | API key required |
| ArXiv     | ArXiv public API         | Free, no key     |
| Wikipedia | MediaWiki OpenSearch API | Free, no key     |
| NewsAPI   | NewsAPI.org              | API key required |

---

## Deployment Guide

You can deploy this project completely for **free** using Upstash (Redis), Render (Backend), and Vercel (Frontend).

### Step 1: Deploy Semantic Cache (Upstash Redis)

Since Render's free Redis tier drops data and spins down, Upstash is recommended for serverless Redis.

1. Sign up at [Upstash](https://upstash.com/).
2. Create a new **Redis Database** (Serverless, Free tier).
3. Scroll down to the connections section and copy the **Redis URL** (it should look like `rediss://default:password@endpoint:port`).

### Step 2: Deploy Backend (Render)

1. Push your code to a GitHub repository.
2. Sign in to [Render](https://render.com/) and create a new **Web Service**.
3. Connect your GitHub repository.
4. Configure the Web Service:
   - **Name**: `deep-research-backend`
   - **Root Directory**: `backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port 10000`
5. Add your **Environment Variables**:
   Under the environment variables tab, add every required key from your `.env` file:
   - `OPENROUTER_API_KEY`: Your OpenRouter Key
   - `TAVILY_API_KEY`: Your Tavily Key
   - `REDIS_URL`: The Redis URL you copied from Upstash
   - _(Add any other required models or keys like Serper/NewsAPI if you are using them)_
6. Click **Deploy Web Service**. Once the build finishes and the service is live, **copy your Render backend URL** (e.g., `https://deep-research-backend.onrender.com`).

### Step 3: Deploy Frontend (Vercel)

1. Sign in to [Vercel](https://vercel.com/) and click **Add New Project**.
2. Import the same GitHub repository.
3. In the Configuration screen:
   - **Project Name**: `deep-research-agent`
   - **Framework Preset**: Vercel should auto-detect **Vite**.
   - **Root Directory**: Click "Edit" and change it to `frontend`.
4. Open the **Environment Variables** section and add:
   - **Name**: `VITE_API_URL`
   - **Value**: Your Render backend URL (e.g., `https://deep-research-backend.onrender.com`) - _Do not add a trailing slash_.
5. Click **Deploy**. Vercel will install dependencies, build the React app, and deploy it globally.

Once Vercel finishes, open the provided URL. Your Deep Research Agent is now live!
