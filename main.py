import asyncio
import os
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown as RichMarkdown
from src.graph import reporter_agent
from src.utils import save_as_pdf
import re


# Load environment variables
load_dotenv()

async def run_agent(topic: str):
    print(f"Starting research on topic: {topic}")
    
    config = {"recursion_limit": 50}
    
    events = reporter_agent.astream(
        {'topic': topic},
        config,
        stream_mode="values",
    )

    async for event in events:
        for k, v in event.items():
            if k == 'final_report':
                print('='*50)
                print('Final Report:')
                md = RichMarkdown(v)
                Console().print(md)
                
                # Save as PDF
                # Sanitize filename
                filename = re.sub(r'[\\/*?:"<>|]', "", topic)
                filename = filename.replace(" ", "_")
                filename = f"{filename[:50]}.pdf"
                
                print(f"\nGeneratng PDF report: {filename}")
                save_as_pdf(v, filename)
                
                return v

if __name__ == "__main__":
    if not os.getenv("OPENROUTER_API_KEY"):
        print("Error: OPENROUTER_API_KEY not found in environment variables.")
        print("Please set it in .env file or environment.")
        exit(1)
    
    if not os.getenv("TAVILY_API_KEY"):
        print("Error: TAVILY_API_KEY not found in environment variables.")
        print("Please set it in .env file or environment.")
        exit(1)

    print("Enter the topic for the report: ", end="", flush=True)
    try:
        topic = input()
    except EOFError:
        print("\nNo input provided. Exiting.")
        exit(1)
        
    if not topic.strip():
        print("Topic cannot be empty.")
        exit(1)
        
    asyncio.run(run_agent(topic))
