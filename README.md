# Deep Research AI Agent

A powerful, autonomous research agent that plans, researches, writes, and compiles comprehensive technical reports. Built with **LangGraph** and **LangChain**, it leverages **OpenRouter** to be completely model-agnostic, allowing you to use the best LLM for your needs (e.g., Gemini 2.0 Flash, Llama 3, Claude 3.5 Sonnet).

## Key Features

- **Model Agnostic**: uses OpenRouter to support any LLM. Easily switch models via environment variables.
- **Deep Web Research**: Integrates with [Tavily](https://tavily.com/) for high-quality, real-time web search.
- **Parallel Execution**: Uses LangGraph to research and write multiple report sections simultaneously.
- **PDF Export**: Automatically compiles the final markdown report into a professional PDF document.
- **Smart Context Management**: Implements token management and context compression to handle large research datasets without crashing.

## Prerequisites

- **Python 3.10+**
- **OpenRouter API Key**: Sign up at [OpenRouter](https://openrouter.ai/).
- **Tavily API Key**: Sign up at [Tavily](https://tavily.com/).

## Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/abhigupta/deep_research_agent.git
    cd deep_research_agent
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *Note: If you use `uv`, you can run `uv pip install -r requirements.txt`.*

3.  **Configure environment variables:**
    Create a `.env` file in the root directory (or copy `.env.example`).
    ```bash
    cp .env.example .env
    ```
    
    Edit `.env` and add your keys:
    ```bash
    # Required
    OPENROUTER_API_KEY=sk-or-your-key-here
    TAVILY_API_KEY=tvly-your-key-here
    
    # Optional - Default is google/gemini-2.0-flash-lite:free
    LLM_MODEL=google/gemini-2.0-flash-lite:free
    ```

## Usage

Run the agent from the root directory:

```bash
python main.py
```
*(Or `uv run main.py` if you are using uv)*

1.  Enter the **topic** you want to research (e.g., "AI Agents", "Quantum Computing", "The Future of Renewable Energy").
2.  The agent will:
    - Generate a comprehensive report plan.
    - Research each section in parallel using web searches.
    - Write detailed sections based on the research.
    - Compile a final report in Markdown.
    - Save the report as a **PDF** (e.g., `Topic_Name.pdf`) in the same folder.

## Project Structure

- **`main.py`**: Entry point for the application.
- **`src/`**:
    - **`graph.py`**: Defines the orchestration logic using LangGraph.
    - **`nodes.py`**: Contains the core logic for each step (planning, searching, writing).
    - **`prompts.py`**: System prompts for the LLM to ensure high-quality output.
    - **`utils.py`**: Utilities for Tavily search, result formatting, and PDF generation.
    - **`state.py`**: Pydantic models and TypedDicts defining the agent's state.

## Customization

You can adjust parameters in `src/nodes.py` and `src/utils.py` to tune performance:
- **Model**: Change `LLM_MODEL` in `.env` to try different models.
- **Search Depth**: Modify `num_results` in `search_web` node.
- **Context Limit**: Adjust `max_tokens` in `src/utils.py` to control how much research context represents.

## License

MIT
