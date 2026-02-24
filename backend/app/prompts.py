DEFAULT_REPORT_STRUCTURE = """The report structure should focus on breaking-down the user-provided topic
                              and building a comprehensive report in markdown using the following format:

                              1. Introduction (no web search needed)
                                - Brief overview of the topic area

                              2. Main Body Sections:
                                - Each section should focus on a sub-topic of the user-provided topic
                                - Include any key concepts and definitions
                                - Provide real-world examples or case studies where applicable

                              3. Conclusion (no web search needed)
                                - Aim for 1 structural element (either a list of table) that distills the main body sections
                                - Provide a concise summary of the report

                              When generating the final response in markdown, if there are special characters in the text,
                              such as the dollar symbol, ensure they are escaped properly for correct rendering e.g $25.5 should become \\$25.5
                          """

REPORT_PLAN_QUERY_GENERATOR_PROMPT = """You are an expert technical report writer, helping to plan a report.

The report will be focused on the following topic:
{topic}

The report structure will follow these guidelines:
{report_organization}

Your goal is to generate {number_of_queries} search queries that will help gather comprehensive information for planning the report sections.

The query should:
1. Be related to the topic
2. Help satisfy the requirements specified in the report organization

Make the query specific enough to find high-quality, relevant sources while covering the depth and breadth needed for the report structure.
"""

REPORT_PLAN_SECTION_GENERATOR_PROMPT = """You are an expert technical report writer, helping to plan a report.

Your goal is to generate the outline of the sections of the report.

The overall topic of the report is:
{topic}

The report should follow this organizational structure:
{report_organization}

You should reflect on this additional context information from web searches to plan the main sections of the report:
{search_context}

Now, generate the sections of the report. Each section should have the following fields:
- Name - Name for this section of the report.
- Description - Brief overview of the main topics and concepts to be covered in this section.
- Research - Whether to perform web search for this section of the report or not.
- Content - The content of the section, which you will leave blank for now.

Consider which sections require web search.
For example, introduction and conclusion will not require research because they will distill information from other parts of the report.
"""

REPORT_SECTION_QUERY_GENERATOR_PROMPT = """Your goal is to generate targeted web search queries that will gather comprehensive information for writing a technical report section.

Topic for this section:
{section_topic}

Hypothetical ideal answer (HyDE context) for the overall report:
{hyde_context}

When generating {number_of_queries} search queries, ensure diversity by covering these angles:
1. **Factual/Data**: Queries seeking specific statistics, benchmarks, or metrics
2. **Conceptual**: Queries exploring core concepts, definitions, and theoretical frameworks
3. **Practical/Applied**: Queries for real-world examples, case studies, implementations
4. **Comparative**: Queries comparing with alternatives, competitors, or related approaches
5. **Recent/Trends**: Queries targeting recent developments (include current year markers)

Your queries should be:
- Specific enough to avoid generic results
- Technical enough to capture detailed information
- Diverse enough to cover the section from multiple angles
- Informed by the HyDE context to improve relevance
- Focused on authoritative sources (documentation, academic papers, technical blogs)"""

SECTION_WRITER_PROMPT = """You are an expert technical writer crafting one specific section of a technical report.

Title for the section:
{section_title}

Topic for this section:
{section_topic}

Guidelines for writing:

1. Technical Accuracy:
- Include specific version numbers
- Reference concrete metrics/benchmarks
- Cite official documentation
- Use technical terminology precisely

2. Length and Style:
- Strict 150-200 word limit
- No marketing language
- Technical focus
- Write in simple, clear language do not use complex words unnecessarily
- Start with your most important insight in **bold**
- Use short paragraphs (2-3 sentences max)

3. Structure:
- Use ## for section title (Markdown format)
- Only use ONE structural element IF it helps clarify your point:
  * Either a focused table comparing 2-3 key items (using Markdown table syntax)
  * Or a short list (3-5 items) using proper Markdown list syntax:
    - Use `*` or `-` for unordered lists
    - Use `1.` for ordered lists
    - Ensure proper indentation and spacing
- End with ### Sources that references the below source material formatted as:
  * List each source with title, date, and URL
  * Format: `- Title : https://source-url.com` (use the ACTUAL URL from the source context, do not use the word "URL")

4. Writing Approach:
- Include at least one specific example or case study if available
- Use concrete details over general statements
- Make every word count
- No preamble prior to creating the section content
- Focus on your single most important point

5. Use this source material obtained from web searches to help write the section:
{context}

6. Quality Checks:
- Format should be Markdown
- Exactly 150-200 words (excluding title and sources)
- Careful use of only ONE structural element (table or bullet list) and only if it helps clarify your point
- One specific example / case study if available
- Starts with bold insight
- No preamble prior to creating the section content
- Sources cited at end
- If there are special characters in the text, such as the dollar symbol,
  ensure they are escaped properly for correct rendering e.g $25.5 should become \\$25.5
"""

FINAL_SECTION_WRITER_PROMPT = """You are an expert technical writer crafting a section that synthesizes information from the rest of the report.

Title for the section:
{section_title}

Topic for this section:
{section_topic}

Available report content of already completed sections:
{context}

1. Section-Specific Approach:

For Introduction:
- Use # for report title (Markdown format)
- 50-100 word limit
- Write in simple and clear language
- Focus on the core motivation for the report in 1-2 paragraphs
- Use a clear narrative arc to introduce the report
- Include NO structural elements (no lists or tables)
- No sources section needed

2.For Conclusion/Summary:
- Use ## for section title (Markdown format)
- 100-150 word limit
- For comparative reports:
    * Must include a focused comparison table using Markdown table syntax
    * Table should distill insights from the report
    * Keep table entries clear and concise
- For non-comparative reports:
    * Only use ONE structural element IF it helps distill the points made in the report:
    * Either a focused table comparing items present in the report (using Markdown table syntax)
    * Or a short list using proper Markdown list syntax:
      - Use `*` or `-` for unordered lists
      - Use `1.` for ordered lists
      - Ensure proper indentation and spacing
- End with specific next steps or implications
- No sources section needed

3. Writing Approach:
- Use concrete details over general statements
- Make every word count
- Focus on your single most important point

4. Quality Checks:
- For introduction: 50-100 word limit, # for report title, no structural elements, no sources section
- For conclusion: 100-150 word limit, ## for section title, only ONE structural element at most, no sources section
- Markdown format
- Do not include word count or any preamble in your response
- If there are special characters in the text, such as the dollar symbol,
  ensure they are escaped properly for correct rendering e.g $25.5 should become \\$25.5"""

# ============================================================
# v2.0 — Critic Agent Prompt
# ============================================================

CRITIC_AGENT_PROMPT = """You are a critical evaluator and research quality analyst. Your job is to assess a drafted report section and identify any weaknesses.

Section Title:
{section_title}

Section Content (Draft):
{section_content}

Source Material Used:
{source_material}

Evaluate the section on these criteria:

1. **Knowledge Gaps**: Are there important aspects of the topic that are NOT covered? Are there obvious questions a reader would have that remain unanswered?

2. **Unsupported Claims**: Are there any factual claims, statistics, or assertions that are NOT backed by the provided source material? Flag any claim that appears to be fabricated or unverifiable.

3. **Outdated Data**: Are there any data points, statistics, or references that appear to be more than 12 months old? Flag anything that may no longer be current.

4. **Source Contradictions**: Do any sources contradict each other? Are there conflicting data points or perspectives that are not addressed?

5. **Confidence Score**: Rate your overall confidence in this section's quality from 0 to 100:
   - 90-100: Excellent — well-sourced, comprehensive, no gaps
   - 70-89: Good — minor gaps, mostly well-supported
   - 50-69: Fair — some notable gaps or unsupported claims
   - 30-49: Poor — significant gaps, needs major revision
   - 0-29: Very Poor — mostly unsupported or incorrect

6. **Suggested Queries**: If gaps are found, suggest 2-3 targeted search queries that would help fill those specific gaps.

Set `gaps_found` to true if you identify ANY of the following:
- 2+ knowledge gaps
- 1+ unsupported claims
- 1+ outdated data points
- 1+ contradictions

Be rigorous but fair. The goal is to improve quality through targeted re-research, not to be overly critical of well-written sections."""

# ============================================================
# v2.0 — Query Analyzer + HyDE Prompts
# ============================================================

QUERY_ANALYZER_PROMPT = """You are an expert research query analyst. Analyze the user's research topic and extract structured intent.

User's Topic:
{topic}

Provide your analysis:
1. **Core Intent**: What is the user actually trying to learn or accomplish?
2. **Scope**: Is this a broad survey, a focused deep-dive, or a comparison?
3. **Domain**: What field(s) does this topic belong to? (e.g., technology, science, business, history)
4. **Output Format**: What type of report would best serve this query? (e.g., technical report, comparative analysis, tutorial, overview)
5. **Key Entities**: List the main concepts, technologies, or subjects involved.
6. **Time Sensitivity**: Is recent information critical, or is historical context more important?

Return your analysis as a concise structured summary."""

HYDE_GENERATOR_PROMPT = """You are an expert researcher. Given a research topic, generate a hypothetical "ideal answer" — a well-structured, information-rich response that represents what a perfect research report on this topic would look like.

Research Topic:
{topic}

Query Analysis:
{query_analysis}

Generate a 200-300 word hypothetical ideal answer that:
1. Covers the key aspects a comprehensive report should address
2. Includes plausible (but hypothetical) statistics, data points, and examples
3. Mentions specific technologies, methodologies, or frameworks likely relevant
4. References the types of sources that would be authoritative for this topic
5. Uses the same vocabulary and terminology the best sources would use

IMPORTANT: This is NOT a real answer — it's a "search anchor" to help find the best real sources. Make it information-dense with specific terms that would appear in high-quality search results.

Do NOT include disclaimers about this being hypothetical. Write it as if it were a real expert summary."""

# ============================================================
# v2.0 — Fact Checker Prompt
# ============================================================

FACT_CHECKER_PROMPT = """You are a rigorous fact-checker reviewing a compiled research report. Your job is to cross-reference claims against the source material and flag issues.

Report Sections:
{report_content}

Instructions:

1. **Identify Key Claims**: Extract the most important factual claims, statistics, and assertions from each section.

2. **Cross-Reference**: For each claim, check:
   - Is it supported by the source material cited in the section?
   - Is it corroborated by multiple sources or only one?
   - Does it contradict any other claim in the report?

3. **Flag Issues**: For each problematic claim, provide:
   - The claim text
   - The section it appears in
   - The issue type: UNSUPPORTED, SINGLE_SOURCE, CONTRADICTED, or OUTDATED
   - A confidence level: LOW (⚠️), MEDIUM, or HIGH (✅)

4. **Per-Section Confidence**: Rate each section's factual reliability from 0 to 100.

5. **Overall Assessment**: Provide a brief summary of the report's factual quality.

Return your response as a JSON object with this structure:
{{
  "flagged_claims": [
    {{"claim": "...", "section": "...", "issue": "...", "confidence": "LOW"}}
  ],
  "section_scores": {{
    "Section Name": 75
  }},
  "overall_summary": "...",
  "overall_confidence": 80
}}"""

# ============================================================
# v2.0 — Final Synthesis Prompt (Premium LLM)
# ============================================================

FINAL_SYNTHESIS_PROMPT = """You are a world-class research report writer. Synthesize the following researched sections into a polished, cohesive final report.

Topic: {topic}

Researched Sections:
{research_sections}

Sections you need to write from scratch (using the researched content as context): {non_research_section_names}
{fact_check_context}
{confidence_context}

Your task:

1. **Write an Executive Summary** (3-5 bullet key takeaways) at the very top, prefixed with `# {topic}`

2. **Write an Introduction** (~100 words):
   - Scope the report based on what was actually researched
   - Set reader expectations
   - Use a clear narrative arc

3. **Integrate Research Sections**:
   - Include ALL researched sections in their original order
   - Smooth transitions between sections
   - Fix any inconsistencies between sections
   - Ensure the narrative flows logically

4. **Write a Conclusion** (~150 words):
   - Distill the most important findings
   - Include 1 structural element (table or list) summarizing key points
   - End with forward-looking insights or implications

5. **Quality Standards**:
   - Professional, technical tone
   - No marketing language
   - If fact-check flags were provided, acknowledge any limitations
   - Ensure all $ symbols are escaped as \\$ for Markdown rendering
   - Use proper Markdown formatting throughout
   - Include a Sources section at the very end compiling all cited sources

The final output should be a complete, publication-ready Markdown document."""
