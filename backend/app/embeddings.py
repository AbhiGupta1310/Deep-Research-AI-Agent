"""
Embedding Utility.
Provides text embedding and cosine similarity functions
using OpenAI's text-embedding-3-small model.
"""

import os
from typing import List, Optional
import asyncio

import numpy as np


# Singleton OpenAI client
_openai_client = None


def _get_openai_client():
    """Lazy init OpenAI client for embeddings."""
    global _openai_client
    if _openai_client is None:
        try:
            from openai import OpenAI
            _openai_client = OpenAI(api_key=os.getenv("OPENROUTER_API_KEY"),
                                     base_url="https://openrouter.ai/api/v1")
        except ImportError:
            print("[Embeddings] openai package not installed.")
            return None
    return _openai_client


async def embed_text(text: str) -> Optional[List[float]]:
    """
    Generate an embedding vector for the given text.

    Args:
        text: The text to embed.

    Returns:
        A list of floats (embedding vector), or None if embedding fails.
    """
    client = _get_openai_client()
    if client is None:
        return None

    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    try:
        # Run the sync embedding call in a thread pool
        response = await asyncio.to_thread(
            lambda: client.embeddings.create(
                input=text[:8000],  # Truncate to avoid token limits
                model=model,
            )
        )
        return response.data[0].embedding

    except Exception as e:
        print(f"[Embeddings] Error embedding text: {e}")
        return None


async def embed_texts(texts: List[str]) -> List[Optional[List[float]]]:
    """
    Embed multiple texts in a single batch API call.
    """
    if not texts:
        return []

    client = _get_openai_client()
    if client is None:
        return [None] * len(texts)

    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # Truncate all texts to avoid token limits per item
    # Provide a fallback empty string if a text chunk is None
    truncated_texts = [text[:8000] if text else "" for text in texts]

    try:
        # Pass the entire list to the input parameter for ONE single HTTP request
        response = await asyncio.to_thread(
            lambda: client.embeddings.create(
                input=truncated_texts,
                model=model,
            )
        )
        
        # The API returns them in the exact order they were sent
        # We sort by 'index' just to be absolutely safe
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]

    except Exception as e:
        print(f"[Embeddings] Error batch embedding texts: {e}")
        # Return a list of Nones so downstream zip/enumerate doesn't break
        return [None] * len(texts)


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        vec_a: First vector.
        vec_b: Second vector.

    Returns:
        Cosine similarity score between -1.0 and 1.0.
    """
    try:
        a = np.array(vec_a)
        b = np.array(vec_b)
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))
    except Exception:
        return 0.0
