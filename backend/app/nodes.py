from langchain_openai import ChatOpenAI
import os
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.constants import Send

from .state import ReportState, SectionState, Section, Sections, Queries, SearchQuery
from .utils import run_search_queries, format_search_query_results
from .prompts import (
    DEFAULT_REPORT_STRUCTURE,
    REPORT_PLAN_QUERY_GENERATOR_PROMPT,
    REPORT_PLAN_SECTION_GENERATOR_PROMPT,
    REPORT_SECTION_QUERY_GENERATOR_PROMPT,
    SECTION_WRITER_PROMPT,
    FINAL_SECTION_WRITER_PROMPT
)

_llm = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            model=os.getenv("LLM_MODEL"),
            temperature=0,
            max_retries=2,
            timeout=60,
            default_headers={
                "HTTP-Referer": "https://github.com/abhigupta/deep_research_agent",
                "X-Title": "Deep Research Agent",
            },
            extra_body={
                "transforms": ["middle-out"] # This tells OpenRouter to auto-compress
            }
        )
    return _llm


async def generate_report_plan(state: ReportState):
    """Generate the overall plan for building the report"""
    
    topic = state["topic"]
    print('--- Generating Report Plan ---')
    
    report_structure = DEFAULT_REPORT_STRUCTURE
    number_of_queries = 8
    
    structured_llm = get_llm().with_structured_output(Queries)
    
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
        
        # Search web and ensure we wait for results
        search_docs = await run_search_queries(
            query_list,
            num_results=5, 
            include_raw_content=False
        )
        
        if not search_docs:
            print("Warning: No search results returned")
            search_context = "No search results available."
        else:
            search_context = format_search_query_results(
                search_docs, 
                include_raw_content=False
            )
            
        # Generate sections
        system_instructions_sections = REPORT_PLAN_SECTION_GENERATOR_PROMPT.format(
            topic=topic,
            report_organization=report_structure,
            search_context=search_context
        )
        
        structured_llm = get_llm().with_structured_output(Sections)
        report_sections = structured_llm.invoke([
            SystemMessage(content=system_instructions_sections),
            HumanMessage(content="Generate the sections of the report. Your response must include a 'sections' field containing a list of sections. Each section must have: name, description, plan, research, and content fields.")
        ])
        
        print('--- Generating Report Plan Completed ---')
        return {"sections": report_sections.sections}
        
    except Exception as e:
        print(f"Error in generate_report_plan: {e}")
        return {"sections": []}

def generate_queries(state: SectionState):
    """ Generate search queries for a specific report section """
    
    # Get state
    section = state["section"]
    print('--- Generating Search Queries for Section: '+ section.name +' ---')
    
    # Get configuration
    number_of_queries = 5
    
    # Generate queries 
    structured_llm = get_llm().with_structured_output(Queries)
    
    # Format system instructions
    system_instructions = REPORT_SECTION_QUERY_GENERATOR_PROMPT.format(section_topic=section.description,
                                                                       number_of_queries=number_of_queries)

    # Generate queries
    user_instruction = "Generate search queries on the provided topic."
    search_queries = structured_llm.invoke([SystemMessage(content=system_instructions),
                                     HumanMessage(content=user_instruction)])
                                     
    print('--- Generating Search Queries for Section: '+ section.name +' Completed ---')
    
    return {"search_queries": search_queries.queries}

async def search_web(state: SectionState):
    search_queries = state["search_queries"]
    print('--- Searching Web for Queries ---')
    
    query_list = [query.search_query for query in search_queries]
    # Reduce num_results if needed, but the key is max_tokens
    search_docs = await run_search_queries(search_queries, num_results=4, include_raw_content=True)
    
    # FIX: Tighten the max_tokens. 4000 is safe, but let's ensure it doesn't leak.
    # If your source_str is too big, the writer crashes.
    search_context = format_search_query_results(search_docs, max_tokens=15000, include_raw_content=True)
    
    print('--- Searching Web for Queries Completed ---')
    return {"source_str": search_context}

def write_section(state: SectionState):
    """ Write a section of the report """
    
    # Get state
    section = state["section"]
    source_str = state["source_str"]
    
    print('--- Writing Section : '+ section.name +' ---')
    
    # Format system instructions
    system_instructions = SECTION_WRITER_PROMPT.format(section_title=section.name,
                                                       section_topic=section.description,
                                                       context=source_str)
                                                       
    # Generate section
    user_instruction = "Generate a report section based on the provided sources."
    section_content = get_llm().invoke([SystemMessage(content=system_instructions),
                                  HumanMessage(content=user_instruction)])
                                  
    # Write content to the section object
    section.content = section_content.content
    
    print('--- Writing Section : '+ section.name +' Completed ---')
    
    # Write the updated section to completed sections
    return {"completed_sections": [section]}

def parallelize_section_writing(state: ReportState):
    """ This is the "map" step when we kick off web research for some sections of the report in parallel and then write the section"""
    
    # Kick off section writing in parallel via Send() API for any sections that require research
    return [
        Send("section_builder_with_web_search", # name of the subagent node
             {"section": s}) 
            for s in state["sections"] 
              if s.research
    ]

def format_sections(sections: list[Section]) -> str:
    """ Format a list of report sections into a single text string """
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

def format_completed_sections(state: ReportState):
    """ Gather completed sections from research and format them as context for writing the final sections """
    
    print('--- Formatting Completed Sections ---')
    
    # List of completed sections
    completed_sections = state["completed_sections"]
    
    # Format completed section to str to use as context for final sections
    completed_report_sections = format_sections(completed_sections)
    
    print('--- Formatting Completed Sections is Done ---')
    
    return {"report_sections_from_research": completed_report_sections}

def write_final_sections(state: SectionState):
    """ Write the final sections of the report, which do not require web search and use the completed sections as context"""
    
    # Get state
    section = state["section"]
    completed_report_sections = state["report_sections_from_research"]
    safe_context = completed_report_sections[:100000]
    
    print('--- Writing Final Section: '+ section.name + ' ---')
    
    # Format system instructions
    system_instructions = FINAL_SECTION_WRITER_PROMPT.format(section_title=section.name,
                                                             section_topic=section.description,
                                                             context=safe_context)
    
    # Generate section
    user_instruction = "Craft a report section based on the provided sources."
    section_content = get_llm().invoke([SystemMessage(content=system_instructions),
                                  HumanMessage(content=user_instruction)])
                                  
    # Write content to section
    section.content = section_content.content
    
    print('--- Writing Final Section: '+ section.name + ' Completed ---')
    
    # Write the updated section to completed sections
    return {"completed_sections": [section]}

def parallelize_final_section_writing(state: ReportState):
    """ Write any final sections using the Send API to parallelize the process """
    
    # Kick off section writing in parallel via Send() API for any sections that do not require research
    return [
        Send("write_final_sections", 
             {"section": s, "report_sections_from_research": state["report_sections_from_research"]}) 
                 for s in state["sections"] 
                    if not s.research
    ]

def compile_final_report(state: ReportState):
    """ Compile the final report """
    
    # Get sections
    sections = state["sections"]
    completed_sections = {s.name: s.content for s in state["completed_sections"]}
    
    print('--- Compiling Final Report ---')
    
    # Update sections with completed content while maintaining original order
    for section in sections:
        section.content = completed_sections[section.name]
    
    # Compile final report
    all_sections = "\n\n".join([s.content for s in sections])
    # Escape unescaped $ symbols to display properly in Markdown
    formatted_sections = all_sections.replace("\\$", "TEMP_PLACEHOLDER")  # Temporarily mark already escaped $
    formatted_sections = formatted_sections.replace("$", "\\$")  # Escape all $
    formatted_sections = formatted_sections.replace("TEMP_PLACEHOLDER", "\\$")  # Restore originally escaped $

# Now escaped_sections contains the properly escaped Markdown text


    print('--- Compiling Final Report Done ---')
    
    return {"final_report": formatted_sections}
