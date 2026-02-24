"""
ArXiv Search Provider — Academic papers and research.
Uses the arxiv Python library for free API access.
"""

from typing import List, Dict, Any
import asyncio


class ArxivSearchProvider:
    """Search provider using the ArXiv API for academic papers and research."""

    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search ArXiv for academic papers.

        Args:
            query: Search query string.
            num_results: Maximum number of results to return.

        Returns:
            List of standardized search result dicts.
        """
        try:
            import arxiv

            client = arxiv.Client()
            search = arxiv.Search(
                query=query,
                max_results=num_results,
                sort_by=arxiv.SortCriterion.Relevance,
            )

            # Run the sync arxiv search in a thread pool to avoid blocking
            results_list = await asyncio.to_thread(
                lambda: list(client.results(search))
            )

            results = []
            for paper in results_list:
                results.append({
                    "url": paper.entry_id,
                    "title": paper.title,
                    "content": paper.summary,
                    "raw_content": paper.summary,  # ArXiv provides abstracts
                    "domain": "arxiv.org",
                    "publish_date": paper.published.strftime("%Y-%m-%d") if paper.published else "",
                    "source_type": "arxiv",
                })
            return results

        except ImportError:
            print("[ArxivSearch] 'arxiv' package not installed. Run: pip install arxiv")
            return []
        except Exception as e:
            print(f"[ArxivSearch] Error searching for '{query}': {e}")
            return []
