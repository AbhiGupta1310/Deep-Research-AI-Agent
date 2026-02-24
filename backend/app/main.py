import sys
import os
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field
from .graph import reporter_agent
from .sse import SSEManager, EventTypes
from .output_compiler import OutputCompiler
from .chat.followup import FollowupChatHandler
from .cache.redis_cache import SemanticCache
from .cost_tracker import CostTracker
from dotenv import load_dotenv
import re
import asyncio
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from the backend root directory (one level up from app/)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path=env_path, override=True)

# Strict startup validation
missing_keys = []
if not os.getenv("OPENROUTER_API_KEY"):
    missing_keys.append("OPENROUTER_API_KEY")
if not os.getenv("TAVILY_API_KEY"):
    missing_keys.append("TAVILY_API_KEY")

if missing_keys:
    logger.critical(f"Missing required environment variables: {', '.join(missing_keys)}")
    logger.critical("Please update your .env file.")
    sys.exit(1)
else:
    logger.info("All required environment variables loaded.")

app = FastAPI(title="Deep Research Agent API v2")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Concurrency control
_research_semaphore = asyncio.Semaphore(2)

# Follow-up chat handler
_chat_handler = FollowupChatHandler()

# Semantic cache
_semantic_cache = SemanticCache()

# Output directory
_output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")


class ResearchRequest(BaseModel):
    topic: str = Field(..., max_length=500, description="Research topic (max 500 chars)")
    depth: str = Field(default="deep", description="Research depth: 'quick' or 'deep'")
    output_format: str = Field(default="both", description="Output format: 'pdf', 'markdown', or 'both'")


class ChatRequest(BaseModel):
    question: str = Field(..., max_length=1000, description="Follow-up question about the report")


@app.post("/api/research")
async def conduct_research(request: ResearchRequest):
    """
    Main research endpoint. Uses Server-Sent Events (SSE) to stream
    real-time progress updates to the frontend.
    """
    topic = request.topic
    depth = request.depth
    output_format = request.output_format
    logger.info(f"Starting research on: {topic} (depth={depth}, format={output_format})")

    # Create an SSE manager for this session
    sse_manager = SSEManager()

    async def event_stream():
        try:
            async with _research_semaphore:
                # Emit initial event
                await sse_manager.emit(
                    EventTypes.QUERY_ANALYZING,
                    "🔍 Analyzing your query...",
                )

                # Stream events from the graph
                final_report = None
                output_metadata = None

                # Run the graph and emit progress events
                async for event in reporter_agent.astream(
                    {"topic": topic},
                    config={
                        "recursion_limit": 50,
                        "metadata": {"topic": topic, "depth": depth},
                        "tags": ["v2", depth],
                    }
                ):
                    # Map graph node completions to SSE events
                    for node_name, node_output in event.items():
                        sse_event = _map_node_to_sse_event(node_name, node_output)
                        if sse_event:
                            await sse_manager.emit(**sse_event)

                        # Capture final report
                        if isinstance(node_output, dict) and 'final_report' in node_output:
                            final_report = node_output['final_report']

                        # Capture output compiler metadata
                        if isinstance(node_output, dict) and 'output_metadata' in node_output:
                            output_metadata = node_output['output_metadata']

                if not final_report:
                    await sse_manager.emit(
                        EventTypes.ERROR,
                        "❌ Failed to generate report (Agent returned no report).",
                    )
                    await sse_manager.close()
                    return

                # Build the rich completion payload
                report_id = (output_metadata or {}).get("report_id", "unknown")
                completion_data = {
                    "report_id": report_id,
                    "content": final_report,
                    "chat_enabled": (output_metadata or {}).get("chat_enabled", False),
                    # PDF
                    "pdf_filename": (output_metadata or {}).get("pdf_filename", ""),
                    "pdf_url": (output_metadata or {}).get("pdf_url", ""),
                    # Markdown
                    "markdown_content": (output_metadata or {}).get("markdown_content", final_report),
                    "markdown_url": f"/api/reports/{report_id}/markdown",
                    # JSON
                    "json_url": f"/api/reports/{report_id}/json",
                    "json_report": (output_metadata or {}).get("json_data", {}),
                    # Confidence & sources
                    "confidence_scores": (output_metadata or {}).get("confidence_scores", {}),
                    "source_count": (output_metadata or {}).get("source_count", 0),
                    "runtime_seconds": (output_metadata or {}).get("runtime_seconds", 0),
                    # Cost estimate
                    "cost_estimate_usd": CostTracker.estimate_run_cost(
                        len((output_metadata or {}).get("json_data", {}).get("sections", []))
                    ),
                }

                # Emit completion event with all data
                await sse_manager.emit(
                    EventTypes.REPORT_READY,
                    "🎉 Report ready!",
                    data=completion_data,
                )

        except Exception as e:
            logger.error(f"Error during research: {e}", exc_info=True)
            await sse_manager.emit(
                EventTypes.ERROR,
                f"❌ Error: {str(e)}",
            )
        finally:
            await sse_manager.close()

    # Start the graph execution in a background task
    # and yield SSE events as they come
    async def sse_generator():
        # Start the pipeline in a background task
        task = asyncio.create_task(event_stream())

        # Yield SSE events from the manager's queue
        async for event_data in sse_manager.stream():
            yield event_data

        # Ensure the task completes
        await task

    return EventSourceResponse(sse_generator())


def _map_node_to_sse_event(node_name: str, node_output) -> dict | None:
    """Map a LangGraph node completion to an SSE event."""
    event_map = {
        "query_analyzer_hyde": {
            "event_type": EventTypes.QUERY_ANALYZING,
            "message": "🧠 Analyzing query & generating search anchor...",
        },
        "generate_report_plan": {
            "event_type": EventTypes.PLAN_GENERATED,
            "message": "📋 Report plan generated",
        },
        "query_rewriter_expander": {
            "event_type": EventTypes.SECTION_RESEARCHING,
            "message": "🔎 Expanding search queries with HyDE...",
        },
        "multi_source_search": {
            "event_type": EventTypes.SECTION_RESEARCHING,
            "message": "🌐 Searching 5 sources in parallel...",
        },
        "result_merger_ranker": {
            "event_type": EventTypes.SECTION_RESEARCHING,
            "message": "🔀 Merging & ranking search results...",
        },
        "write_section": {
            "event_type": EventTypes.SECTION_RESEARCHING,
            "message": "✍️ Writing section draft...",
        },
        "critic_agent": {
            "event_type": EventTypes.SECTION_RESEARCHING,
            "message": "🔍 Critic evaluating section quality...",
        },
        "section_builder_with_web_search": {
            "event_type": EventTypes.SECTION_COMPLETE,
            "message": "✅ Section research complete",
        },
        "aggregator_deduplicator": {
            "event_type": EventTypes.SECTION_COMPLETE,
            "message": "📝 Aggregating sections & deduplicating sources...",
        },
        "fact_checker": {
            "event_type": EventTypes.FACT_CHECKING,
            "message": "🔬 Fact-checking claims across sources...",
        },
        "final_synthesis_writer": {
            "event_type": EventTypes.SYNTHESIS_WRITING,
            "message": "✨ Premium synthesis: writing final report...",
        },
        "output_compiler": {
            "event_type": EventTypes.COMPILING_OUTPUT,
            "message": "📄 Compiling report into PDF, Markdown & JSON...",
        },
    }

    mapping = event_map.get(node_name)
    if mapping:
        # Attach section info if available
        data = {}
        if isinstance(node_output, dict):
            if "sections" in node_output:
                section_names = []
                for s in node_output["sections"]:
                    if hasattr(s, "name"):
                        section_names.append(s.name)
                    elif isinstance(s, dict) and "name" in s:
                        section_names.append(s["name"])
                data["sections"] = section_names
                mapping["message"] = f"📋 Report plan generated ({len(section_names)} sections)"

            if "completed_sections" in node_output:
                completed = node_output["completed_sections"]
                if completed:
                    last_section = completed[-1]
                    name = last_section.name if hasattr(last_section, "name") else str(last_section)
                    mapping["message"] = f"✅ Section complete: {name}"
                    data["section_name"] = name

        return {**mapping, "data": data}

    return None


# --- Report Download Endpoints ---

@app.get("/api/reports/{filename}")
async def get_report(filename: str):
    """Download a generated report file (PDF, MD, or JSON)."""
    file_path = os.path.join(_output_dir, filename)

    # Security check for path traversal
    resolved_path = os.path.realpath(file_path)
    resolved_output_dir = os.path.realpath(_output_dir)

    if not resolved_path.startswith(resolved_output_dir):
        raise HTTPException(status_code=403, detail="Access denied")

    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Report not found")


@app.get("/api/reports/{report_id}/json")
async def get_report_json(report_id: str):
    """Return the structured JSON report for a given report ID."""
    # Search for a JSON file containing the report_id
    json_file = _find_report_file(report_id, ".json")
    if json_file and os.path.exists(json_file):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return JSONResponse(content=data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading JSON: {e}")

    raise HTTPException(status_code=404, detail=f"JSON report not found for id: {report_id}")


@app.get("/api/reports/{report_id}/markdown")
async def get_report_markdown(report_id: str):
    """Return the raw markdown content for a given report ID."""
    md_file = _find_report_file(report_id, ".md")
    if md_file and os.path.exists(md_file):
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()
            return PlainTextResponse(content=content, media_type="text/markdown")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading markdown: {e}")

    raise HTTPException(status_code=404, detail=f"Markdown report not found for id: {report_id}")


def _find_report_file(report_id: str, extension: str) -> str | None:
    """
    Find a report file by report_id. Searches the outputs directory
    for JSON files containing the matching report_id, or falls back
    to filename matching.
    """
    if not os.path.exists(_output_dir):
        return None

    # Strategy 1: Check all JSON metadata files for matching report_id
    if extension == ".json":
        for fname in os.listdir(_output_dir):
            if fname.endswith(".json") and not fname.endswith("_metadata.json"):
                fpath = os.path.join(_output_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("report_id") == report_id:
                        return fpath
                except Exception:
                    continue

    # Strategy 2: For markdown, find the JSON first, then derive the filename
    if extension == ".md":
        json_file = _find_report_file(report_id, ".json")
        if json_file:
            md_file = json_file.replace(".json", ".md")
            if os.path.exists(md_file):
                return md_file

    # Strategy 3: Direct filename match (if report_id is used as filename prefix)
    for fname in os.listdir(_output_dir):
        if report_id in fname and fname.endswith(extension):
            return os.path.join(_output_dir, fname)

    return None


# --- Follow-up Chat Endpoint ---

@app.post("/api/chat/{report_id}")
async def chat_with_report(report_id: str, request: ChatRequest):
    """Ask follow-up questions about a generated report using RAG."""
    try:
        from .models import get_mid_llm
        llm = get_mid_llm()
        result = await _chat_handler.answer_question(
            report_id=report_id,
            question=request.question,
            llm=llm,
        )
        return result
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- Health & Root ---

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "2.0"}


@app.get("/")
async def root():
    return {"message": "Deep Research Agent API v2 is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
