import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import datetime as dt
import logging
import os
import random
import time
import traceback
import uuid

import aiohttp
from bson.objectid import ObjectId
from fastapi import FastAPI, HTTPException
from motor import motor_asyncio
from openai import AsyncOpenAI
from prometheus_fastapi_instrumentator import Instrumentator, metrics
import pytz
from qdrant_client import AsyncQdrantClient, models

from worker.answer_preparation import get_best_tags
from worker.config import LoggingConfig
from worker.data_processing import get_tags, get_tags_statistics, join_lines, prepare_conversation_mongodb
from worker.prometheus import (
    answer_not_exact_counter,
    metric_namespace,
    new_conversation_counter,
    no_answer_counter,
    average_tag_hist,
    closest_tag_hist,
    farthest_tag_hist
)
from worker.schemas import (
    AnswerRequest,
    AnswerResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    InsertConversationRequest,
    InsertConversationResponse,
    MongoEmbeddingsRequest,
    MongoEmbeddingsResponse,
    GetEmbeddingsRequest,
    GetEmbeddingsResponse,
    GetTopKRequest,
    GetTopKResponse,
    UpsertQdrantEmbeddingsRequest,
    UpsertQdrantEmbeddingsResponse,
)
from worker.utils import (
    add_cors_middleware,
    get_mongodb_async_database,
    get_package_version,
    get_qdrant_async_client
)

logging_config = LoggingConfig()
logging.basicConfig(
    level=logging_config.level,
    stream=logging_config.stream,
    format=logging_config.format,
    style=logging_config.style,
)

VERSION = get_package_version()
logging.info(f'Worker REST API version {VERSION} starting')

app = FastAPI(title="Worker API", version=VERSION)
add_cors_middleware(app)

# Initialize MongoDB and Qdrant clients
mongodb_client = None
qdrant_client = None

@asynccontextmanager
async def lifespan(app_: FastAPI) -> AsyncGenerator:
    global mongodb_client, qdrant_client
    
    # Initialize MongoDB client
    mongodb_client = await get_mongodb_async_database()
    
    # Initialize Qdrant client
    qdrant_client = await get_qdrant_async_client()
    
    # Run at startup
    yield
    
    # Run at shutdown
    if mongodb_client:
        mongodb_client.close()
    if qdrant_client:
        await qdrant_client.close()

app.router.lifespan_context = lifespan

# Add Prometheus metrics
Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_respect_env_var=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=[".*admin.*", "/metrics"],
    env_var_name="ENABLE_METRICS",
    inprogress_name="inprogress",
    inprogress_labels=True,
).instrument(app).expose(app)

# MongoDB endpoints
@app.post("/insert_conversation")
async def insert_conversation(request: InsertConversationRequest) -> InsertConversationResponse:
    try:
        conversation_data = prepare_conversation_mongodb(request.conversation)
        result = await mongodb_client.conversations.insert_one(conversation_data)
        new_conversation_counter.inc()
        return InsertConversationResponse(success=True, message=f"Conversation inserted with ID: {result.inserted_id}")
    except Exception as e:
        error_message = f"Error inserting conversation: {str(e)}"
        logging.error(error_message)
        raise HTTPException(status_code=500, detail=error_message)

# Qdrant endpoints
@app.post("/get_top_k")
async def get_top_k(request: GetTopKRequest) -> GetTopKResponse:
    try:
        if not request.with_payload or isinstance(request.with_payload, list) and not 'tag' in request.with_payload:
            return GetTopKResponse(
                success=False,
                ids=[],
                tags=[],
                scores=[],
                embeddings=None,
                message='`with_payload` should be either `True` or contain "tag" attribute.',
            )
        
        search_result = await qdrant_client.search(
            collection_name=f'embeddings-{request.embedding_model}',
            query_vector=request.query_embedding,
            search_params=models.SearchParams(
                hnsw_ef=128,
                quantization=models.QuantizationSearchParams(
                    rescore=True,
                    oversampling=10.0,
                ),
                indexed_only=True,
            ),
            limit=request.top_k,
            with_payload=request.with_payload,
            with_vectors=request.with_vectors,
        )
        
        if not request.include_ids:
            ids = None
        else:
            ids = [result.id for result in search_result]
            
        payload = [result.payload for result in search_result]
        if any(p is None for p in payload):
            raise Exception(f'Strange, some results have no payload: {search_result}')
            
        tags = [p['tag'] for p in payload]
        scores = [result.score for result in search_result]
        embeddings = None
        if request.with_vectors:
            embeddings = [result.vector for result in search_result]
            
        payload_ = None
        if request.with_payload and request.with_payload != ['tag']:
            for p in payload:
                del p['tag']
            payload_ = payload

        # Observe prometheus metrics
        closest_tag_hist.observe(scores[0])
        farthest_tag_hist.observe(scores[-1])
        average_tag_hist.observe(sum(scores) / len(scores))

        return GetTopKResponse(
            success=True,
            ids=ids,
            tags=tags,
            scores=scores,
            embeddings=embeddings,
            payload=payload_,
        )
    except Exception as e:
        error_message = f'Error while getting topK embeddings: {str(e)}'
        logging.error(error_message)
        raise HTTPException(status_code=500, detail=error_message)

@app.post("/upsert_qdrant_embeddings")
async def upsert_qdrant_embeddings_handler(request: UpsertQdrantEmbeddingsRequest) -> UpsertQdrantEmbeddingsResponse:
    try:
        collection_name = f'embeddings-{request.embedding_model}'
        tags = request.tags
        n_tags = len(tags)
        
        if n_tags > 1000:
            return UpsertQdrantEmbeddingsResponse(
                success=False,
                message=f'Too many tags. Max 1000, got {n_tags}.',
            )
            
        if n_tags == 0:
            return UpsertQdrantEmbeddingsResponse(
                success=True,
                message='No tags to upsert.',
            )
            
        embeddings = request.embeddings
        if embeddings is not None:
            if n_tags != len(embeddings):
                return UpsertQdrantEmbeddingsResponse(
                    success=False,
                    message='`tags` and `embeddings` should have same length.',
                )
                
            embedding_lengths = set(len(embedding) for embedding in embeddings)
            if len(embedding_lengths) > 1:
                return UpsertQdrantEmbeddingsResponse(
                    success=False,
                    message='All embeddings should have same length.',
                )
                
            embedding_length = len(embeddings[0])
            collection_info = await qdrant_client.get_collection(collection_name)
            vectors_params = collection_info.config.params.vectors
            if vectors_params is None or not isinstance(vectors_params, models.VectorParams):
                return UpsertQdrantEmbeddingsResponse(
                    success=False,
                    message=f'Collection `{collection_name}` has no vectors or misconfigured.',
                )
                
            expected_length = vectors_params.size
            if not expected_length == embedding_length:
                return UpsertQdrantEmbeddingsResponse(
                    success=False,
                    message=f'Collection `{collection_name}` has different embedding length ({expected_length}) '
                    f'than provided in request ({embedding_length}).',
                )

        payload = request.payload
        if payload is not None:
            if n_tags != len(payload):
                return UpsertQdrantEmbeddingsResponse(
                    success=False,
                    message='`tags` and `payload` values should have same length.',
                )
                
        # Create collection if it doesn't exist
        if not await qdrant_client.collection_exists(collection_name):
            await qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_length,
                    distance=models.Distance.COSINE,
                ),
            )

        # Upsert embeddings
        points = []
        for i in range(n_tags):
            point = {
                'id': str(uuid.uuid4()),
                'vector': embeddings[i] if embeddings else None,
                'payload': {
                    'tag': tags[i],
                    **(payload[i] if payload else {})
                }
            }
            points.append(point)

        operation_info = await qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
        )

        return UpsertQdrantEmbeddingsResponse(
            success=True,
            message=f'Upserted {n_tags} tags with status: {operation_info.status}.',
        )
    except Exception as e:
        error_message = f'Error while upserting embeddings: {str(e)}'
        logging.error(error_message)
        raise HTTPException(status_code=500, detail=error_message)

@app.post("/get_embeddings")
async def get_embeddings(request: GetEmbeddingsRequest) -> GetEmbeddingsResponse:
    try:
        tags = request.tags
        n_tags = len(tags)
        if not tags:
            return GetEmbeddingsResponse(
                success=False,
                embeddings=[],
                llm_type=request.llm_type,
                embedding_model=request.embedding_model,
                source=[],
                message='No tags to get embeddings for.'
            )
            
        if not all(tags):
            return GetEmbeddingsResponse(
                success=False,
                embeddings=[],
                llm_type=request.llm_type,
                embedding_model=request.embedding_model,
                source=[],
                message='Empty tags are not allowed.'
            )

        collection_name = f'embeddings-{request.embedding_model}'
        payload_keys = ['tag']
        if request.include_source:
            payload_keys.append('source')

        # Find already present tags
        search_result = await qdrant_client.scroll(
            collection_name=collection_name,
            scroll_filter=models.Filter(
                should=[
                    models.FieldCondition(
                        key='tag',
                        match=models.MatchAny(any=tags),
                    ),
                ]
            ),
            limit=n_tags * 3,
            with_payload=payload_keys,
            with_vectors=True,
            timeout=10,
        )

        # Filter unique tags
        cache = set()
        points, _ = search_result
        points_unique = []
        for point in points:
            if point.payload is None or point.payload.get('tag') in cache:
                continue
            cache.add(point.payload.get('tag'))
            points_unique.append(point)

        known_embeddings = {
            p.payload.get('tag'): {
                'vector': p.vector,
                'source': p.payload.get('source', 'unknown')
            }
            for p in points_unique
            if isinstance(p.payload, dict)
        }

        if len(known_embeddings) != len(points_unique):
            raise Exception(f'len(known_embeddings) != len(points): {len(known_embeddings)} != {len(points)}')

        if any(tag is None for tag in known_embeddings):
            raise Exception(f'Found None instead of tag in qdrant!! {points}')

        if any(v['vector'] is None for v in known_embeddings.values()):
            raise Exception(f'Found None instead of vector in qdrant!! {points}')

        new_tags_indices = [i for i in range(n_tags) if tags[i] not in known_embeddings]
        n_new_tags = len(new_tags_indices)
        logging.info(f'Found {n_new_tags} new/unknown tags in get_embeddings request.')

        if len(known_embeddings) + n_new_tags != n_tags:
            raise Exception(
                f'len(known_embeddings) + n_new_tags != n_tags: {len(known_embeddings)} + {n_new_tags} != {n_tags}'
            )

        if n_new_tags > 0:
            # Get embeddings for new tags
            new_tags = [tags[i] for i in new_tags_indices]
            try:
                openai_client = AsyncOpenAI()
                response = await openai_client.embeddings.create(
                    input=new_tags,
                    model=request.embedding_model
                )
                new_embeddings = [x.embedding for x in response.data]
            except Exception as e:
                logging.error(f'OpenAI error while getting embeddings: {e}.\nnew_tags: {new_tags}')
                return GetEmbeddingsResponse(
                    success=False,
                    embeddings=[],
                    llm_type=request.llm_type,
                    embedding_model=request.embedding_model,
                    source=[],
                    message=f'OpenAI error: {e}'
                )

            for tag, embedding in zip(new_tags, new_embeddings):
                known_embeddings[tag] = {'vector': embedding, 'source': request.source}

            # Queue new embeddings for upsert
            upsert_request = UpsertQdrantEmbeddingsRequest(
                tags=new_tags,
                embeddings=new_embeddings,
                source=request.source
            )
            await upsert_qdrant_embeddings_handler(upsert_request)

        return GetEmbeddingsResponse(
            success=True,
            embeddings=[d['vector'] for d in known_embeddings.values()],
            llm_type=request.llm_type,
            embedding_model=request.embedding_model,
            source=[d['source'] for d in known_embeddings.values()],
            message=f'New tags: {n_new_tags}/{n_tags}.',
        )
    except Exception as e:
        error_message = f'Error while getting embeddings: {str(e)}'
        logging.error(error_message)
        raise HTTPException(status_code=500, detail=error_message)

# ... rest of the existing endpoints from both workers ...
