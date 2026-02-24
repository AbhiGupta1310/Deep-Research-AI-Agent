from typing_extensions import TypedDict
from pydantic import BaseModel, Field
import operator
from typing import Annotated, List, Optional, Literal, Dict


# ============================================================
# Pydantic Models (Structured LLM Output Schemas)
# ============================================================

class Section(BaseModel):
    """A single section of the research report."""
    name: str = Field(
        description="Name for a particular section of the report.",
    )
    description: str = Field(
        description="Brief overview of the main topics and concepts to be covered in this section.",
    )
    research: bool = Field(
        description="Whether to perform web search for this section of the report."
    )
    content: str = Field(
        default="",
        description="The content for this section.",
    )
    # v2.0 additions
    key_questions: List[str] = Field(
        default_factory=list,
        description="Key questions this section should answer.",
    )
    search_angle: str = Field(
        default="",
        description="The angle or focus for search queries (e.g., 'quantitative data', 'case studies').",
    )
    priority: str = Field(
        default="medium",
        description="Priority level for this section: 'high', 'medium', or 'low'.",
    )


class Sections(BaseModel):
    """Collection of all report sections."""
    sections: List[Section] = Field(
        description="All the Sections of the overall report.",
    )


class SearchQuery(BaseModel):
    """A single web search query."""
    search_query: str = Field(None, description="Query for web search.")


class Queries(BaseModel):
    """Collection of search queries."""
    queries: List[SearchQuery] = Field(
        description="List of web search queries.",
    )


class SourceMetadata(BaseModel):
    """Metadata for a single source result with credibility scoring."""
    url: str = Field(default="", description="Source URL.")
    domain: str = Field(default="", description="Source domain.")
    title: str = Field(default="", description="Source title.")
    credibility_score: float = Field(default=0.5, description="Domain authority score (0.0–1.0).")
    recency_score: float = Field(default=0.5, description="How recent the content is (0.0–1.0).")
    relevance_score: float = Field(default=0.5, description="Cosine similarity to HyDE doc (0.0–1.0).")
    corroboration: int = Field(default=0, description="Number of other sources making the same claim.")
    final_score: float = Field(default=0.0, description="Weighted combination of all scores.")
    publish_date: str = Field(default="", description="Publication date.")
    content: str = Field(default="", description="Source content snippet.")
    source_type: str = Field(default="", description="Provider type: tavily, serper, arxiv, wikipedia, newsapi.")


class CriticFeedback(BaseModel):
    """Structured feedback from the critic agent evaluating a section draft."""
    gaps_found: bool = Field(
        description="Whether any knowledge gaps, unsupported claims, or issues were found.",
    )
    knowledge_gaps: List[str] = Field(
        default_factory=list,
        description="List of identified knowledge gaps in the section.",
    )
    unsupported_claims: List[str] = Field(
        default_factory=list,
        description="Claims made without sufficient source support.",
    )
    outdated_data: List[str] = Field(
        default_factory=list,
        description="Data points that appear to be outdated (>12 months old).",
    )
    contradictions: List[str] = Field(
        default_factory=list,
        description="Contradictions found between different sources.",
    )
    suggested_queries: List[str] = Field(
        default_factory=list,
        description="Targeted re-search queries to fill the identified gaps.",
    )
    confidence_score: float = Field(
        default=50.0,
        description="Overall confidence in the section quality (0–100).",
    )


class SectionWithConfidence(Section):
    """Section extended with a confidence score from the critic."""
    confidence_score: float = Field(
        default=0.0,
        description="Critic-assessed confidence score (0–100).",
    )


# ============================================================
# LangGraph State Schemas
# ============================================================

class ReportStateInput(TypedDict):
    topic: str  # Report topic


class ReportStateOutput(TypedDict):
    final_report: str  # Final report
    output_metadata: dict  # Output compiler results (paths, URLs, scores)


class ReportState(TypedDict):
    topic: str                                              # Report topic
    sections: list[Section]                                 # List of report sections
    completed_sections: Annotated[list, operator.add]       # Send() API — accumulated
    report_sections_from_research: str                      # Formatted completed sections as context
    final_report: str                                       # Final compiled report
    # v2.0 additions
    hyde_document: str                                      # HyDE hypothetical ideal answer
    sub_queries: list[str]                                  # Expanded sub-queries from HyDE
    search_results: dict                                    # Per-section search results
    reflection_count: dict                                  # Per-section reflection loop counter (max 3)
    knowledge_gaps: dict                                    # Per-section gaps found by critic
    confidence_scores: dict                                 # Per-section confidence (0–100)
    fact_check_flags: list[str]                             # Flagged low-confidence claims
    sources: list[dict]                                     # Full source metadata with credibility
    cache_hit: bool                                         # Whether result was served from cache
    langsmith_run_id: str                                   # LangSmith trace ID
    output_metadata: dict                                   # Output compiler results (paths, URLs, scores)


class SectionState(TypedDict):
    section: Section                                        # Report section being worked on
    search_queries: list[SearchQuery]                       # Generated search queries
    source_str: str                                         # Formatted source content for LLM
    report_sections_from_research: str                      # Context from other completed sections
    completed_sections: list[Section]                       # Accumulated for Send() API
    # v2.0 additions
    reflection_count: int                                   # Loop counter for this section (max 3)
    knowledge_gaps: list[str]                               # Gaps identified by critic
    confidence_score: float                                 # Section confidence (0–100)
    search_results: list[dict]                              # Raw search results with metadata
    critic_feedback: CriticFeedback                         # Latest critic evaluation
    hyde_document: str                                      # HyDE context passed from parent


class SectionOutputState(TypedDict):
    completed_sections: list[Section]                       # Final output key for Send() API
