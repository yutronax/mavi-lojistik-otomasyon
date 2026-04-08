---
name: research
description: Global, cross-language research and structured documentation. Use this for deep dives into tech trends, market analysis, or solving complex technical unknowns.
---

# Global Research Skill

This skill empowers the agent to act as a world-class researcher.

## Instructions

### Step 1: Query Formulation
- Break down the main topic into 3-5 specific search queries.
- Include localized and international keywords (e.g., "Agentic AI frameworks" AND "Ajan tabanlı yapay zeka").

### Step 2: Broad Search & Filtering
- Use `search_web` to get a broad list of URLs.
- Identify the top 5 most relevant pages based on title and snippet.

### Step 3: Deep Extraction
- Use `browser_subagent` or `read_url_content` to extract full text or markdown from the top sources.
- Look for statistics, comparative tables, and contradictory opinions.

### Step 4: Synthesis & Documentation
- Compare the findings across sources.
- Resolve any discrepancies using the `self-debate` skill if needed.
- Write the final `research_report.md` artifact following the rules in `rules/research.md`.

## Output Requirements
- Must include a comparative table if comparing products or technologies.
- Must include a "Conclusion & Recommendation" section.
