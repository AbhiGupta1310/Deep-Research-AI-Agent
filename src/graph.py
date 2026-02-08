from langgraph.graph import StateGraph, START, END
from src.state import ReportState, ReportStateInput, ReportStateOutput, SectionState, SectionOutputState
from src.nodes import (
    generate_report_plan,
    generate_queries,
    search_web,
    write_section,
    parallelize_section_writing,
    format_completed_sections,
    write_final_sections,
    parallelize_final_section_writing,
    compile_final_report
)

def create_section_builder_subagent():
    # Add nodes and edges
    section_builder = StateGraph(SectionState, output=SectionOutputState)
    section_builder.add_node("generate_queries", generate_queries)
    section_builder.add_node("search_web", search_web)
    section_builder.add_node("write_section", write_section)

    section_builder.add_edge(START, "generate_queries")
    section_builder.add_edge("generate_queries", "search_web")
    section_builder.add_edge("search_web", "write_section")
    section_builder.add_edge("write_section", END)
    
    return section_builder.compile()

def create_reporter_agent():
    section_builder_subagent = create_section_builder_subagent()
    
    builder = StateGraph(ReportState, input=ReportStateInput, output=ReportStateOutput)

    builder.add_node("generate_report_plan", generate_report_plan)
    builder.add_node("section_builder_with_web_search", section_builder_subagent)
    builder.add_node("format_completed_sections", format_completed_sections)
    builder.add_node("write_final_sections", write_final_sections)
    builder.add_node("compile_final_report", compile_final_report)

    builder.add_edge(START, "generate_report_plan")
    builder.add_conditional_edges("generate_report_plan", 
                                  parallelize_section_writing, 
                                  ["section_builder_with_web_search"])
    builder.add_edge("section_builder_with_web_search", "format_completed_sections")
    builder.add_conditional_edges("format_completed_sections", 
                                  parallelize_final_section_writing, 
                                  ["write_final_sections"])
    builder.add_edge("write_final_sections", "compile_final_report")
    builder.add_edge("compile_final_report", END)

    return builder.compile()

reporter_agent = create_reporter_agent()
