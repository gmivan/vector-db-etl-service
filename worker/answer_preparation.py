import logging
from typing import List, Optional

import numpy as np


def score_miner_embedding(
    embeddings_miner: list[float] | np.ndarray, embedding_validator: list[float] | np.ndarray
) -> float:
    if not isinstance(embeddings_miner, np.ndarray):
        embeddings_miner = np.array(embeddings_miner)
    if not isinstance(embedding_validator, np.ndarray):
        embedding_validator = np.array(embedding_validator)
    # cosine similarity
    score = np.dot(embeddings_miner, embedding_validator) / (
        np.linalg.norm(embeddings_miner) * np.linalg.norm(embedding_validator)
    )
    return float(score)


def get_best_tags(tags: List[str], scores: List[float], threshold: float = 0.8) -> List[str]:
    """Get the best tags based on similarity scores."""
    if not tags or not scores:
        return []
    
    # Pair tags with their scores
    tag_scores = list(zip(tags, scores))
    
    # Sort by score in descending order
    tag_scores.sort(key=lambda x: x[1], reverse=True)
    
    # Filter tags above threshold
    best_tags = [tag for tag, score in tag_scores if score >= threshold]
    
    return best_tags


def duplicate_tags(tags: list[str]) -> list[str]:
    # TODO: change to .capitalize(), adding a dot or retrieving a synonym, etc. later
    return tags + [x + ' ' for x in tags]
