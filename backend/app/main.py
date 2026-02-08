import sys
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from .graph import reporter_agent
from .utils import save_as_pdf
from dotenv import load_dotenv
import re
import asyncio
import json

# Load environment variables from the backend root directory (one level up from app/)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path=env_path)

# Debug: Check if keys are loaded
if not os.getenv("OPENROUTER_API_KEY"):
    print("WARNING: OPENROUTER_API_KEY not found in environment!")
else:
    print("SUCCESS: OPENROUTER_API_KEY loaded.")

app = FastAPI(title="Deep Research Agent API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ResearchRequest(BaseModel):
    topic: str

@app.post("/api/research")
async def conduct_research(request: ResearchRequest):
    topic = request.topic
    print(f"Starting research on request: {topic}")
    
    async def event_generator():
        try:
            # Send initial valid JSON
            yield json.dumps({"status": "started", "message": "Research started..."}) + "\n"
            
            # Using astream to get states as they update
            final_report = None
            
            async for event in reporter_agent.astream({"topic": topic}, config={"recursion_limit": 50}):
                # Send progress update
                # event is a dict of the update
                # We can try to extract meaningful info
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
            
            save_as_pdf(final_report, output_path)
            
            yield json.dumps({
                "status": "completed",
                "report_url": f"/api/reports/{filename}", 
                "content": final_report,
                "filename": filename
            }) + "\n"
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@app.get("/api/reports/{filename}")
async def get_report(filename: str):
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")
    file_path = os.path.join(output_dir, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Report not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
