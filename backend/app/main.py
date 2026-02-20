import sys
import os
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, validator
from .graph import reporter_agent
from .utils import save_as_pdf
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

app = FastAPI(title="Deep Research Agent API")

# CORS configuration
# NOTE: allow_origins=["*"] with allow_credentials=True is insecure. 
# For dev, we use localhost. For prod, specify the domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Concurrency control
_research_semaphore = asyncio.Semaphore(2)

class ResearchRequest(BaseModel):
    topic: str = Field(..., max_length=500, description="Research topic (max 500 chars)")

@app.post("/api/research")
async def conduct_research(request: ResearchRequest):
    topic = request.topic
    logger.info(f"Starting research on request: {topic}")
    
    async def event_generator():
        # Acquire semaphore to limit concurrent research
        try:
            async with _research_semaphore:
                # Send initial valid JSON
                yield json.dumps({"status": "started", "message": "Research started..."}) + "\n"
                
                # Using astream to get states as they update
                final_report = None
                
                async for event in reporter_agent.astream({"topic": topic}, config={"recursion_limit": 50}):
                    # Send progress update
                    # event is a dict of the update
                    yield json.dumps({"status": "progress", "data": str(list(event.keys()))}) + "\n"
                    
                    # Check for final report in values
                    for k, v in event.items():
                        if 'final_report' in v:
                            final_report = v['final_report']
                
                if not final_report:
                    yield json.dumps({"status": "error", "message": "Failed to generate report (Agent returned no report)."}) + "\n"
                    return

                # Save PDF
                # Sanitize filename
                filename = re.sub(r'[\\/*?:"<>|]', "", topic)
                filename = filename.replace(" ", "_")
                filename = f"{filename[:50]}.pdf"
                
                # Ensure outputs directory exists
                output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")
                os.makedirs(output_dir, exist_ok=True)
                
                output_path = os.path.join(output_dir, filename)
                
                # Run sync PDF generation in thread pool to avoid blocking
                await asyncio.to_thread(save_as_pdf, final_report, output_path)
                
                yield json.dumps({
                    "status": "completed",
                    "report_url": f"/api/reports/{filename}", 
                    "content": final_report,
                    "filename": filename
                }) + "\n"
                
        except Exception as e:
            logger.error(f"Error checking research: {e}", exc_info=True)
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@app.get("/api/reports/{filename}")
async def get_report(filename: str):
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")
    file_path = os.path.join(output_dir, filename)
    
    # Security check for path traversal
    resolved_path = os.path.realpath(file_path)
    resolved_output_dir = os.path.realpath(output_dir)
    
    if not resolved_path.startswith(resolved_output_dir):
         raise HTTPException(status_code=403, detail="Access denied")

    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Report not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
