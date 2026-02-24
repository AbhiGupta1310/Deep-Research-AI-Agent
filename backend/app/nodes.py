from langchain_openai import ChatOpenAI
import os
import asyncio
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.constants import Send

from .state import (
    ReportState, SectionState, Section, Sections,
    Queries, SearchQuery, CriticFeedback
)
from .models import get_cheap_llm, get_mid_llm, get_premium_llm
from .search import (
    TavilySearchProvider,
    SerperSearchProvider,
    ArxivSearchProvider,
    WikipediaSearchProvider,
    NewsSearchProvider,
)
from .search.merger import ResultMerger, format_ranked_results
from .prompts import (
    DEFAULT_REPORT_STRUCTURE,
    REPORT_PLAN_QUERY_GENERATOR_PROMPT,
    REPORT_PLAN_SECTION_GENERATOR_PROMPT,
    REPORT_SECTION_QUERY_GENERATOR_PROMPT,
    SECTION_WRITER_PROMPT,
    FINAL_SECTION_WRITER_PROMPT,
    CRITIC_AGENT_PROMPT,
    QUERY_ANALYZER_PROMPT,
    HYDE_GENERATOR_PROMPT,
)
from .cache.redis_cache import SemanticCache

# Singleton instances
_semantic_cache = SemanticCache()

# Singleton search providers
_tavily = TavilySearchProvider()
_serper = SerperSearchProvider()
_arxiv = ArxivSearchProvider()
_wikipedia = WikipediaSearchProvider()
_news = NewsSearchProvider()
_merger = ResultMerger()

# Max reflection loops per section
MAX_REFLECTION_LOOPS = 3


# ============================================================
# Node: Query Analyzer + HyDE Generator — v2.0
# ============================================================

async def query_analyzer_hyde(state: ReportState):
    """
    First node in the pipeline. Analyzes query intent, generates a
    HyDE (Hypothetical Document Embedding) anchor, and checks Redis cache.

    If cache hit: short-circuits with cached report.
    If cache miss: stores HyDE document in state for downstream search.
    """

    topic = state["topic"]
    print('--- Query Analyzer + HyDE Generation ---')

    # Step 1: Check semantic cache
    try:
        cached = await _semantic_cache.check_cache(topic)
        if cached:
            print('--- Cache HIT — returning cached report ---')
            return {
                "cache_hit": True,
                "final_report": cached.get("content", ""),
            }
    except Exception as e:
        print(f'[Cache] Error checking cache: {e}')

    # Step 2: Analyze query intent
    query_analysis_prompt = QUERY_ANALYZER_PROMPT.format(topic=topic)
    query_analysis = get_cheap_llm().invoke([
        SystemMessage(content=query_analysis_prompt),
        HumanMessage(content="Analyze this research topic.")
    ])
    analysis_text = query_analysis.content
    print(f'--- Query Analysis Complete ---')

    # Step 3: Generate HyDE document (hypothetical ideal answer)
    hyde_prompt = HYDE_GENERATOR_PROMPT.format(
        topic=topic,
        query_analysis=analysis_text,
    )
    hyde_response = get_cheap_llm().invoke([
        SystemMessage(content=hyde_prompt),
        HumanMessage(content="Generate the hypothetical ideal answer.")
    ])
    hyde_document = hyde_response.content
    print(f'--- HyDE Document Generated ({len(hyde_document)} chars) ---')

    return {
        "hyde_document": hyde_document,
        "cache_hit": False,
    }


# ============================================================
# Conditional Edge: Route After HyDE (cache check)
# ============================================================

def route_after_hyde(state: ReportState) -> str:
    """
    Route based on cache hit:
    - cache_hit=True → skip to compile_final_report
    - cache_hit=False → proceed to generate_report_plan
    """
    if state.get("cache_hit", False):
        return "compile_final_report"
    return "generate_report_plan"


# ============================================================
# Node: Generate Report Plan
# ============================================================

async def generate_report_plan(state: ReportState):
    """Generate the overall plan for building the report."""

    topic = state["topic"]
    print('--- Generating Report Plan ---')

    report_structure = DEFAULT_REPORT_STRUCTURE
    number_of_queries = 8

    structured_llm = get_cheap_llm().with_structured_output(Queries)

    system_instructions_query = REPORT_PLAN_QUERY_GENERATOR_PROMPT.format(
        topic=topic,
        report_organization=report_structure,
        number_of_queries=number_of_queries
    )

    try:
        # Generate queries
        results = structured_llm.invoke([
            SystemMessage(content=system_instructions_query),
            HumanMessage(content='Generate search queries that will help with planning the sections of the report.')
        ])

        # Convert SearchQuery objects to strings
        query_list = [
            query.search_query if isinstance(query, SearchQuery) else str(query)
            for query in results.queries
        ]

        # Multi-source search for planning context
        all_results = []
        for query in query_list[:4]:  # Limit to 4 queries for planning
            provider_tasks = [
                _tavily.search(query, num_results=3),
                _serper.search(query, num_results=3),
            ]
            results = await asyncio.gather(*provider_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_results.extend(result)

        if not all_results:
            print("Warning: No search results returned")
            search_context = "No search results available."
        else:
            ranked = _merger.merge_and_rank(all_results, top_k=10)
            search_context = format_ranked_results(ranked, max_tokens=8000)

        # Generate sections
        system_instructions_sections = REPORT_PLAN_SECTION_GENERATOR_PROMPT.format(
            topic=topic,
            report_organization=report_structure,
            search_context=search_context
        )

        structured_llm = get_cheap_llm().with_structured_output(Sections)
        report_sections = structured_llm.invoke([
            SystemMessage(content=system_instructions_sections),
            HumanMessage(content="Generate the sections of the report. Your response must include a 'sections' field containing a list of sections. Each section must have: name, description, plan, research, and content fields.")
        ])

        print('--- Generating Report Plan Completed ---')
        return {"sections": report_sections.sections}

    except Exception as e:
        print(f"Error in generate_report_plan: {e}")
        return {"sections": []}


# ============================================================
# Node: Query Rewriter + Expander (per section) — v2.0
# ============================================================

def query_rewriter_expander(state: SectionState):
    """
    Generate diverse search queries for a section using HyDE context.
    Generates angle-based variants and selects the best ones.
    Replaces the old generate_queries() node.
    """

    section = state["section"]
    # Get HyDE document from parent state if available, else use section description
    hyde_context = state.get("hyde_document", section.description) or section.description

    print(f'--- Rewriting Queries for Section: {section.name} ---')

    number_of_queries = 5
    structured_llm = get_cheap_llm().with_structured_output(Queries)

    system_instructions = REPORT_SECTION_QUERY_GENERATOR_PROMPT.format(
        section_topic=section.description,
        hyde_context=hyde_context[:2000],  # Truncate to avoid token limits
        number_of_queries=number_of_queries,
    )

    user_instruction = "Generate diverse search queries from multiple angles for this section topic."
    search_queries = structured_llm.invoke([
        SystemMessage(content=system_instructions),
        HumanMessage(content=user_instruction)
    ])

    print(f'--- Query Rewriting for Section: {section.name} Complete ({len(search_queries.queries)} queries) ---')

    return {"search_queries": search_queries.queries}


# ============================================================
# Node: Multi-Source Search Fanout (per section) — v2.0
# ============================================================

async def multi_source_search(state: SectionState):
    """
    Fan out search queries to all 5 providers in parallel.
    Collects raw results — ranking is done by the next node (result_merger_ranker).
    """

    search_queries = state["search_queries"]
    query_strings = [
        q.search_query if isinstance(q, SearchQuery) else str(q)
        for q in search_queries
    ]
    section_name = state["section"].name

    print(f'--- Multi-Source Search for "{section_name}" ({len(query_strings)} queries) ---')

    # Fan out: run all providers in parallel for each query
    all_results = []
    for query in query_strings:
        provider_tasks = [
            _tavily.search(query, num_results=4),
            _serper.search(query, num_results=4),
            _arxiv.search(query, num_results=3),
            _wikipedia.search(query, num_results=2),
            _news.search(query, num_results=3),
        ]
        results = await asyncio.gather(*provider_tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                print(f'[MultiSourceSearch] Provider error: {result}')
                continue
            if isinstance(result, list):
                all_results.extend(result)

    print(f'--- Collected {len(all_results)} raw results for "{section_name}" ---')

    # Store raw results in state — merging/ranking happens in result_merger_ranker
    raw_dicts = []
    for r in all_results:
        if hasattr(r, 'to_dict'):
            raw_dicts.append(r.to_dict())
        elif isinstance(r, dict):
            raw_dicts.append(r)

    return {
        "search_results": raw_dicts,
    }


# ============================================================
# Node: Result Merger + Ranker (per section) — v2.0
# ============================================================

def result_merger_ranker(state: SectionState):
    """
    Merge, deduplicate, and rank search results by credibility.
    Converts raw search results into formatted source context for the writer.
    """

    section_name = state["section"].name
    raw_results = state.get("search_results", [])

    print(f'--- Result Merger & Ranker for "{section_name}" ({len(raw_results)} raw results) ---')

    if not raw_results:
        print(f'--- No results to rank for "{section_name}" ---')
        return {"source_str": "No search results available.", "search_results": []}

    # Merge, deduplicate, and rank using the ResultMerger
    ranked_sources = _merger.merge_and_rank(
        raw_results,
        hyde_document=state["section"].description,
        top_k=15,
    )

    # Format for LLM context
    source_str = format_ranked_results(ranked_sources, max_tokens=15000)

    # Convert to dicts for state storage
    search_results_dicts = [s.to_dict() for s in ranked_sources]

    print(f'--- Ranked {len(ranked_sources)} results for "{section_name}" ---')

    return {
        "source_str": source_str,
        "search_results": search_results_dicts,
    }


# ============================================================
# Node: Write Section (per section)
# ============================================================

def write_section(state: SectionState):
    """Write a section of the report using the mid-tier LLM."""

    section = state["section"]
    source_str = state["source_str"]

    print(f'--- Writing Section: {section.name} ---')

    system_instructions = SECTION_WRITER_PROMPT.format(
        section_title=section.name,
        section_topic=section.description,
        context=source_str
    )

    user_instruction = "Generate a report section based on the provided sources."
    section_content = get_mid_llm().invoke([
        SystemMessage(content=system_instructions),
        HumanMessage(content=user_instruction)
    ])

    section.content = section_content.content

    print(f'--- Writing Section: {section.name} Completed ---')

    return {"completed_sections": [section]}


# ============================================================
# Node: Critic Agent (per section) — NEW in v2.0
# ============================================================

def critic_agent(state: SectionState):
    """
    Evaluate a section draft for quality, gaps, and issues.

    Uses cheap LLM (Gemini Flash) to assess:
    - Knowledge gaps
    - Unsupported claims
    - Outdated data (>12 months)
    - Source contradictions

    Returns CriticFeedback and updates state.
    """

    section = state["section"]
    source_str = state.get("source_str", "")
    current_count = state.get("reflection_count", 0)

    print(f'--- Critic Agent Evaluating Section: {section.name} (loop {current_count + 1}/{MAX_REFLECTION_LOOPS}) ---')

    structured_llm = get_cheap_llm().with_structured_output(CriticFeedback)

    system_instructions = CRITIC_AGENT_PROMPT.format(
        section_title=section.name,
        section_content=section.content,
        source_material=source_str[:8000],  # Truncate to avoid token limits
    )

    try:
        feedback = structured_llm.invoke([
            SystemMessage(content=system_instructions),
            HumanMessage(content="Evaluate this section and provide structured feedback.")
        ])

        print(f'--- Critic Agent Result for "{section.name}": '
              f'gaps_found={feedback.gaps_found}, '
              f'confidence={feedback.confidence_score:.0f}%, '
              f'gaps={len(feedback.knowledge_gaps)}, '
              f'unsupported={len(feedback.unsupported_claims)} ---')

        return {
            "critic_feedback": feedback,
            "knowledge_gaps": feedback.knowledge_gaps,
            "confidence_score": feedback.confidence_score,
            "reflection_count": current_count + 1,
        }

    except Exception as e:
        print(f"Error in critic_agent for '{section.name}': {e}")
        # On error, approve the section as-is
        return {
            "critic_feedback": CriticFeedback(
                gaps_found=False,
                confidence_score=50.0,
            ),
            "knowledge_gaps": [],
            "confidence_score": 50.0,
            "reflection_count": current_count + 1,
        }


# ============================================================
# Conditional Edge: Should Reflect? — NEW in v2.0
# ============================================================

def should_reflect(state: SectionState) -> str:
    """
    Decide whether to loop back for more research or approve the section.

    Routes to:
    - "generate_queries" if gaps found AND reflection_count < MAX
    - "__end__" if section is approved or max loops reached
    """

    feedback = state.get("critic_feedback")
    current_count = state.get("reflection_count", 0)

    if feedback is None:
        return "__end__"

    if feedback.gaps_found and current_count < MAX_REFLECTION_LOOPS:
        section_name = state["section"].name
        print(f'--- Reflection Loop: Re-searching for "{section_name}" '
              f'(loop {current_count}/{MAX_REFLECTION_LOOPS}) ---')
        return "generate_queries"

    # Approved or max loops reached
    section_name = state["section"].name
    print(f'--- Section Approved: "{section_name}" '
          f'(confidence: {feedback.confidence_score:.0f}%, loops: {current_count}) ---')
    return "__end__"


# ============================================================
# Node: Parallelize Section Writing (fan-out)
# ============================================================

def parallelize_section_writing(state: ReportState):
    """Fan-out: kick off section builders in parallel for research sections."""

    hyde_doc = state.get("hyde_document", "")

    return [
        Send("section_builder_with_web_search",
             {"section": s, "reflection_count": 0, "hyde_document": hyde_doc})
        for s in state["sections"]
        if s.research
    ]


# ============================================================
# Utility: Format Sections
# ============================================================

def format_sections(sections: list[Section]) -> str:
    """Format a list of report sections into a single text string."""
    formatted_str = ""
    for idx, section in enumerate(sections, 1):
        formatted_str += f"""
{'='*60}
Section {idx}: {section.name}
{'='*60}
Description:
{section.description}
Requires Research:
{section.research}

Content:
{section.content if section.content else '[Not yet written]'}

"""
    return formatted_str


# ============================================================
# Node: Aggregator + Deduplicator — v2.0
# ============================================================

def aggregator_deduplicator(state: ReportState):
    """
    Aggregate completed sections, deduplicate cross-section sources,
    and compile source metadata for the final report.

    Replaces the old format_completed_sections node.
    """

    print('--- Aggregator + Deduplicator ---')
    completed_sections = state.get("completed_sections", [])

    if not completed_sections:
        print('--- Aggregator: No sections to aggregate ---')
        return {"report_sections_from_research": ""}

    # Format sections as context for the synthesis writer
    completed_report_sections = format_sections(completed_sections)

    # Aggregate and deduplicate sources across all sections
    all_sources = state.get("sources", []) or []
    seen_urls = set()
    deduped_sources = []
    for src in all_sources:
        url = src.get("url", "") if isinstance(src, dict) else getattr(src, "url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped_sources.append(src)
        elif not url:
            deduped_sources.append(src)

    print(f'--- Aggregator Complete: {len(completed_sections)} sections, '
          f'{len(deduped_sources)} unique sources (from {len(all_sources)} total) ---')

    return {
        "report_sections_from_research": completed_report_sections,
        "sources": deduped_sources,
    }


# ============================================================
# Node: Fact Checker — v2.0
# ============================================================

def fact_checker(state: ReportState):
    """
    Cross-reference factual claims across all completed sections.

    - Claims supported by 1 source only → flag as ⚠️ LOW CONFIDENCE
    - Claims corroborated by 3+ sources → mark as ✅ HIGH CONFIDENCE
    - Outputs per-section confidence scores and fact_check_flags.
    """

    report_content = state.get("report_sections_from_research", "")
    if not report_content:
        print("--- Fact Checker: No content to check, skipping ---")
        return {}

    print("--- Fact Checker: Cross-referencing claims ---")

    from .prompts import FACT_CHECKER_PROMPT

    system_instructions = FACT_CHECKER_PROMPT.format(
        report_content=report_content[:12000],  # Truncate for token limits
    )

    try:
        response = get_cheap_llm().invoke([
            SystemMessage(content=system_instructions),
            HumanMessage(content="Fact-check this report and return structured JSON feedback.")
        ])

        # Parse the JSON response
        response_text = response.content
        # Extract JSON from the response (handle markdown code blocks)
        import re
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            import json
            fact_check_result = json.loads(json_match.group())
        else:
            fact_check_result = {}

        # Extract results
        flagged_claims = fact_check_result.get("flagged_claims", [])
        section_scores = fact_check_result.get("section_scores", {})
        overall_confidence = fact_check_result.get("overall_confidence", 50)

        # Format fact check flags
        fact_flags = []
        for claim in flagged_claims:
            flag = f"[{claim.get('confidence', 'UNKNOWN')}] {claim.get('section', '?')}: {claim.get('claim', '?')} ({claim.get('issue', '?')})"
            fact_flags.append(flag)

        print(f"--- Fact Checker Complete: {len(flagged_claims)} flags, "
              f"overall confidence: {overall_confidence}% ---")

        return {
            "fact_check_flags": fact_flags,
            "confidence_scores": section_scores,
        }

    except Exception as e:
        print(f"Error in fact_checker: {e}")
        return {
            "fact_check_flags": [],
            "confidence_scores": {},
        }


# ============================================================
# Node: Final Synthesis Writer — v2.0 (Premium LLM)
# ============================================================

def final_synthesis_writer(state: ReportState):
    """
    The ONE premium LLM call. Uses Claude Sonnet 3.5 to synthesize
    all research sections into a cohesive, polished final report.

    Receives: approved sections, confidence scores, fact-check flags.
    Writes: Executive Summary, Introduction, full narrative, Conclusion.
    Replaces: write_final_sections + compile_final_report.
    """

    sections = state["sections"]
    completed_sections = {s.name: s.content for s in state.get("completed_sections", [])}
    report_content = state.get("report_sections_from_research", "")
    confidence_scores = state.get("confidence_scores", {})
    fact_check_flags = state.get("fact_check_flags", [])

    print("--- Final Synthesis Writer (Premium LLM) ---")

    # Build section content map
    research_sections = []
    non_research_sections = []
    for section in sections:
        if section.research:
            content = completed_sections.get(section.name, section.content or "")
            research_sections.append(f"## {section.name}\n{content}")
        else:
            non_research_sections.append(section)

    # Format fact check context
    fact_check_context = ""
    if fact_check_flags:
        fact_check_context = "\n\nFact-Check Flags:\n" + "\n".join(f"- {f}" for f in fact_check_flags[:10])

    confidence_context = ""
    if confidence_scores:
        confidence_context = "\n\nPer-Section Confidence Scores:\n"
        for name, score in confidence_scores.items():
            confidence_context += f"- {name}: {score}%\n"

    # Build the synthesis prompt
    from .prompts import FINAL_SYNTHESIS_PROMPT

    all_research_content = "\n\n".join(research_sections)

    non_research_names = [s.name for s in non_research_sections]
    topic = state.get("topic", "Research Report")

    system_instructions = FINAL_SYNTHESIS_PROMPT.format(
        topic=topic,
        research_sections=all_research_content[:80000],
        non_research_section_names=", ".join(non_research_names),
        fact_check_context=fact_check_context,
        confidence_context=confidence_context,
    )

    try:
        response = get_premium_llm().invoke([
            SystemMessage(content=system_instructions),
            HumanMessage(content="Synthesize the complete final report.")
        ])

        final_report = response.content

        # Escape unescaped $ symbols for Markdown rendering
        final_report = final_report.replace("\\$", "TEMP_PLACEHOLDER")
        final_report = final_report.replace("$", "\\$")
        final_report = final_report.replace("TEMP_PLACEHOLDER", "\\$")

        print(f"--- Final Synthesis Complete ({len(final_report)} chars) ---")

        return {"final_report": final_report}

    except Exception as e:
        print(f"Error in final_synthesis_writer: {e}")
        # Fallback: basic concatenation
        all_sections = "\n\n".join(
            completed_sections.get(s.name, s.content or "") for s in sections
        )
        return {"final_report": all_sections}

