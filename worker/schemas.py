from __future__ import annotations

from typing import List, Optional, Union

from pydantic import BaseModel, Field


class GetTopKRequest(BaseModel):
    query_embedding: List[float]
    embedding_model: str = 'text-embedding-ada-002'
    top_k: int
    with_payload: Union[bool, List[str]]
    with_vectors: bool = False
    include_ids: bool = False


class GetTopKResponse(BaseModel):
    success: bool
    ids: Optional[List[str]] = None
    tags: List[str]
    scores: List[float]
    embeddings: Optional[List[List[float]]] = None
    payload: Optional[List[dict]] = None
    message: Optional[str] = None


class UpsertQdrantEmbeddingsRequest(BaseModel):
    tags: List[str]
    embeddings: Optional[List[List[float]]] = None
    payload: Optional[List[dict]] = None
    source: str


class UpsertQdrantEmbeddingsResponse(BaseModel):
    success: bool
    message: str


class GetEmbeddingsRequest(BaseModel):
    tags: List[str]
    embedding_model: str
    llm_type: str
    source: str
    include_source: bool = False


class GetEmbeddingsResponse(BaseModel):
    success: bool
    embeddings: List[List[float]]
    llm_type: str
    embedding_model: str
    source: List[str]
    message: str


class AnswerRequest(BaseModel):
    conversation: str
    llm_type: str = Field(..., description="Type of LLM to use")
    embedding_model: str = Field(..., description="Model to use for embeddings")


class AnswerResponse(BaseModel):
    success: bool
    answer: Optional[str] = None
    message: Optional[str] = None


class EmbeddingRequest(BaseModel):
    text: str
    llm_type: str
    embedding_model: str


class EmbeddingResponse(BaseModel):
    success: bool
    embedding: Optional[List[float]] = None
    message: Optional[str] = None


class InsertConversationRequest(BaseModel):
    conversation: str
    source: str
    llm_type: str
    embedding_model: str


class InsertConversationResponse(BaseModel):
    success: bool
    message: Optional[str] = None


class MongoEmbeddingsRequest(BaseModel):
    tags: List[str]
    llm_type: str
    embedding_model: str


class MongoEmbeddingsResponse(BaseModel):
    success: bool
    embeddings: Optional[List[List[float]]] = None
    message: Optional[str] = None
