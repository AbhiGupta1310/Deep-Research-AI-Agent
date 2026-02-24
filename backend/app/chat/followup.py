"""
Follow-up Chat Handler.
RAG-based Q&A over generated reports using ChromaDB for retrieval.
"""

import uuid
from typing import List, Dict, Any, Optional

try:
    import chromadb
except ImportError:
    chromadb = None


class FollowupChatHandler:
    """
    Handles follow-up questions about a generated report.
    
    Flow:
    1. After report generation, chunk report → embed → store in ChromaDB.
    2. User asks a question → embed → retrieve top-3 chunks → Claude Haiku answers.
    """

    def __init__(self):
        self._chroma_client = None

    def _get_chroma_client(self):
        """Lazy init ChromaDB client."""
        if self._chroma_client is None:
            if chromadb is None:
                print("[FollowupChat] chromadb package not installed. Chat disabled.")
                return None
            self._chroma_client = chromadb.Client()
        return self._chroma_client

    async def embed_report(self, report_id: str, report_content: str) -> bool:
        """
        Chunk and embed a report into a ChromaDB collection.

        Args:
            report_id: Unique identifier for the report/research session.
            report_content: Full markdown report content.

        Returns:
            True if successfully embedded, False otherwise.
        """
        client = self._get_chroma_client()
        if client is None:
            return False

        try:
            # Create or get collection for this report
            collection = client.get_or_create_collection(
                name=f"report_{report_id}",
                metadata={"hnsw:space": "cosine"},
            )

            # Chunk the report by sections (split on ## headers)
            chunks = self._chunk_report(report_content)

            if not chunks:
                return False

            # Add chunks to collection (ChromaDB handles embedding internally)
            ids = [f"chunk_{i}" for i in range(len(chunks))]
            collection.add(
                documents=chunks,
                ids=ids,
                metadatas=[{"chunk_index": i} for i in range(len(chunks))],
            )

            print(f"[FollowupChat] Embedded {len(chunks)} chunks for report {report_id}")
            return True

        except Exception as e:
            print(f"[FollowupChat] Error embedding report: {e}")
            return False

    async def answer_question(
        self,
        report_id: str,
        question: str,
        llm=None,
    ) -> Dict[str, Any]:
        """
        Answer a follow-up question about a report using RAG.

        Args:
            report_id: Report identifier to search within.
            question: User's follow-up question.
            llm: LLM instance to use for answering (Claude Haiku 3.5).

        Returns:
            Dict with 'answer' and 'sources' fields.
        """
        client = self._get_chroma_client()
        if client is None:
            return {"answer": "Chat feature is not available.", "sources": []}

        try:
            # Get the collection
            collection = client.get_collection(name=f"report_{report_id}")

            # Retrieve top-3 relevant chunks
            results = collection.query(
                query_texts=[question],
                n_results=3,
            )

            retrieved_chunks = results.get("documents", [[]])[0]

            if not retrieved_chunks:
                return {
                    "answer": "I couldn't find relevant information in the report to answer your question.",
                    "sources": [],
                }

            # Build context from retrieved chunks
            context = "\n\n---\n\n".join(retrieved_chunks)

            if llm is None:
                return {
                    "answer": "LLM not configured for chat.",
                    "sources": retrieved_chunks,
                }

            # Generate answer using LLM
            from langchain_core.messages import HumanMessage, SystemMessage

            response = llm.invoke([
                SystemMessage(content=(
                    "You are a helpful research assistant. Answer the user's question "
                    "based ONLY on the following context from a research report. "
                    "If the context doesn't contain enough information, say so.\n\n"
                    f"Context:\n{context}"
                )),
                HumanMessage(content=question),
            ])

            return {
                "answer": response.content,
                "sources": retrieved_chunks,
            }

        except Exception as e:
            print(f"[FollowupChat] Error answering question: {e}")
            return {"answer": f"Error: {str(e)}", "sources": []}

    def _chunk_report(self, content: str, max_chunk_size: int = 1000) -> List[str]:
        """
        Split report content into chunks by section headers.
        Falls back to paragraph-based splitting if no headers found.
        """
        chunks = []

        # Try splitting by ## headers first
        sections = content.split("\n## ")
        if len(sections) > 1:
            for i, section in enumerate(sections):
                if i > 0:
                    section = "## " + section
                section = section.strip()
                if section:
                    # If section is too large, sub-chunk by paragraphs
                    if len(section) > max_chunk_size:
                        paragraphs = section.split("\n\n")
                        current_chunk = ""
                        for para in paragraphs:
                            if len(current_chunk) + len(para) > max_chunk_size and current_chunk:
                                chunks.append(current_chunk.strip())
                                current_chunk = para
                            else:
                                current_chunk += "\n\n" + para
                        if current_chunk.strip():
                            chunks.append(current_chunk.strip())
                    else:
                        chunks.append(section)
        else:
            # Fallback: split by double newlines (paragraphs)
            paragraphs = content.split("\n\n")
            current_chunk = ""
            for para in paragraphs:
                if len(current_chunk) + len(para) > max_chunk_size and current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = para
                else:
                    current_chunk += "\n\n" + para
            if current_chunk.strip():
                chunks.append(current_chunk.strip())

        return chunks

    @staticmethod
    def generate_report_id() -> str:
        """Generate a unique report ID."""
        return str(uuid.uuid4())[:8]
