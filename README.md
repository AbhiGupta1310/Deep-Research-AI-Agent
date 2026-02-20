# Deep Research AI Agent

A powerful, autonomous research agent that plans, researches, writes, and compiles comprehensive technical reports. Built with **LangGraph**, **FastAPI**, and **React**, it leverages **OpenRouter** to be completely model-agnostic.

![Deep Research Agent](https://github.com/abhigupta/deep_research_agent/assets/placeholder/screenshot.png)

## Key Features

- **Model Agnostic**: uses OpenRouter to support any LLM (e.g., Gemini 2.0 Flash, Llama 3).
- **Deep Web Research**: Integrates with [Tavily](https://tavily.com/) for high-quality, real-time web search.
- **Parallel Execution**: Uses LangGraph to research and write multiple report sections simultaneously.
- **Live Streaming**: Real-time progress updates via Server-Sent Events (SSE).
- **PDF Export**: Automatically compiles the final markdown report into a professional PDF document.
- **Modern UI**: A sleek, "Red Dark Mode" React interface for easy interaction.

## Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **OpenRouter API Key**: Sign up at [OpenRouter](https://openrouter.ai/).
- **Tavily API Key**: Sign up at [Tavily](https://tavily.com/).

## Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/abhigupta/deep_research_agent.git
    cd deep_research_agent
    ```

2.  **Configure environment variables:**
    Create a `.env` file in the `backend/` directory (or root, as it falls back).
    ```bash
    cp .env.example backend/.env
    ```
    
    Edit `backend/.env` with your keys:
    ```bash
    OPENROUTER_API_KEY=sk-or-your-key-here
    TAVILY_API_KEY=tvly-your-key-here
    LLM_MODEL=google/gemini-2.0-flash-exp:free (or your preferred model)
    ```

3.  **Install Backend Dependencies:**
    ```bash
    cd backend
    pip install -r requirements.txt
    ```

4.  **Install Frontend Dependencies:**
    ```bash
    cd ../frontend
    npm install
    ```

## Usage

You can run the full stack using the provided helper script (Mac/Linux):

```bash
./run_app.sh
```

Or run services manually:

**Backend:**
```bash
cd backend
python3 -m uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm run dev
```

Visit [http://localhost:5173](http://localhost:5173) to start researching!

## Project Structure

```text
deep_research_agent/
├── backend/                 # Python/FastAPI Backend
│   ├── app/                 # Application logic
│   │   ├── main.py          # API Entry point
│   │   ├── graph.py         # LangGraph orchestration
│   │   ├── nodes.py         # Agent nodes (planning, writing)
│   │   └── ...
│   ├── requirements.txt
│   └── .env
├── frontend/                # React/Vite Frontend
│   ├── src/                 # React components
│   └── package.json
├── assets/                  # Project images
│   └── img.png
├── pyproject.toml           # Project metadata
└── run_app.sh               # Local startup script
```


## Customization

- **Model**: Change `LLM_MODEL` in `backend/.env`.
- **UI Theme**: Edit `frontend/src/App.css` to customize the "Red Dark Mode" aesthetic.
- **Research Depth**: Modify `num_results` in `backend/app/nodes.py`.


