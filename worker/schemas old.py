from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field


class GetTopKRequest(BaseModel):
    query_embedding: list[float]
    embedding_model: str = 'text-embedding-ada-002'
    top_k: Annotated[int, Field(ge=1, le=1000)] = 15
    with_payload: bool | list[str] = ['tag', 'source']
    with_vectors: bool = False
    include_ids: bool = False


class GetTopKResponse(BaseModel):
    success: bool = False
    ids: list[int | str] | None = None
    tags: list[str]
    scores: list[float]
    embeddings: list[list[float]] | None = None
    payload: list[dict[str, Any]] | None = None
    message: str | None = None


class UpsertQdrantEmbeddingsRequest(BaseModel):
    tags: list[str]
    embedding_model: str = 'text-embedding-ada-002'
    embeddings: list[list[float]] | None = None
    payload: list[dict[str, Any]] | None = None  # [{'datetimes': 'something'}, ...}, etc.
    source: str = 'unknown'


class UpsertQdrantEmbeddingsResponse(BaseModel):
    success: bool = False
    message: str | None = None


class GetEmbeddingsRequest(BaseModel):
    tags: list[str]
    llm_type: str = 'openai'
    embedding_model: str = 'text-embedding-ada-002'
    include_source: bool = False
    source: str = 'unknown'


class GetEmbeddingsResponse(BaseModel):
    success: bool = False
    embeddings: list[list[float]]
    llm_type: str = 'openai'
    embedding_model: str = 'text-embedding-ada-002'
    source: list[str] | None = None
    message: str | None = None
